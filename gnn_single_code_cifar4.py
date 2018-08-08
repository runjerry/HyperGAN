import os
import sys
import time
import argparse
import numpy as np
from glob import glob
from scipy.misc import imshow
from comet_ml import Experiment
import torch
import torchvision
from torchvision import datasets, transforms
from torch import nn
from torch import autograd
from torch import optim
from torch.nn import functional as F
import pprint

import ops
import plot
import utils
import netdef
import datagen
import matplotlib.pyplot as plt


def load_args():

    parser = argparse.ArgumentParser(description='param-wgan')
    parser.add_argument('-z', '--dim', default=64, type=int, help='latent space width')
    parser.add_argument('-ze', '--ze', default=300, type=int, help='encoder dimension')
    parser.add_argument('-g', '--gp', default=10, type=int, help='gradient penalty')
    parser.add_argument('-b', '--batch_size', default=32, type=int)
    parser.add_argument('-e', '--epochs', default=200000, type=int)
    parser.add_argument('-s', '--model', default='small2', type=str)
    parser.add_argument('-d', '--dataset', default='cifar', type=str)
    parser.add_argument('-l', '--layer', default='all', type=str)
    parser.add_argument('-zd', '--depth', default=2, type=int, help='latent space depth')
    parser.add_argument('--nfe', default=64, type=int)
    parser.add_argument('--nfgc', default=64, type=int)
    parser.add_argument('--nfgl', default=64, type=int)
    parser.add_argument('--nfd', default=128, type=int)
    parser.add_argument('--beta', default=1000, type=int)
    parser.add_argument('--resume', default=False, type=bool)
    parser.add_argument('--comet', default=False, type=bool)
    parser.add_argument('--gan', default=False, type=bool)
    parser.add_argument('--use_wae', default=False, type=bool)
    parser.add_argument('--use_x', default=False, type=bool, help='sample from real layers')
    parser.add_argument('--val_iters', default=10, type=bool)

    args = parser.parse_args()
    return args


class Encoder(nn.Module):
    def __init__(self, args):
        super(Encoder, self).__init__()
        for k, v in vars(args).items():
            setattr(self, k, v)
        self.name = 'Encoder'
        self.linear1 = nn.Linear(self.ze, 300)
        self.linear2 = nn.Linear(300, 300)
        self.linear3 = nn.Linear(300, 512)
        self.bn1 = nn.BatchNorm1d(300)
        self.bn2 = nn.BatchNorm1d(300)
        self.relu = nn.LeakyReLU(inplace=True)

    def forward(self, x):
        #print ('E in: ', x.shape)
        x = x.view(self.batch_size, -1) #flatten filter size
        x = self.relu(self.bn1(self.linear1(x)))
        x = self.relu(self.bn2(self.linear2(x)))
        x = self.linear3(x)
        # x = self.relu(self.linear3(x))
        x = x.view(-1, 4, 128)
        # print (x.shape)
        w1 = x[:, 0]
        w2 = x[:, 1]
        w3 = x[:, 2]
        w4 = x[:, 3]
        #print ('E out: ', x.shape)
        return w1, w2, w3, w4


""" Convolutional (3 x 64 x 3 x 3) """
class GeneratorW1(nn.Module):
    def __init__(self, args):
        super(GeneratorW1, self).__init__()
        for k, v in vars(args).items():
            setattr(self, k, v)
        self.name = 'GeneratorW1'
        self.linear1 = nn.Linear(128, 256)
        self.linear2 = nn.Linear(256, 256)
        self.linear3 = nn.Linear(256, 1728)
        self.bn1 = nn.BatchNorm1d(256)
        self.bn2 = nn.BatchNorm1d(256)
        self.bn3 = nn.BatchNorm1d(1024)
        self.relu = nn.LeakyReLU(inplace=True)

    def forward(self, x):
        #print ('W1 in: ', x.shape)
        x = self.relu(self.bn1(self.linear1(x)))
        x = self.relu(self.bn2(self.linear2(x)))
        x = self.relu(self.linear3(x))
        #x = self.linear4(x)
        x = x.view(-1, 64, 3, 3, 3)
        #print ('W1 out: ', x.shape)
        return x


""" Convolutional (128 x 64 x 3 x 3) """
class GeneratorW2(nn.Module):
    def __init__(self, args):
        super(GeneratorW2, self).__init__()
        for k, v in vars(args).items():
            setattr(self, k, v)
        self.name = 'GeneratorW2'
        self.linear1 = nn.Linear(128, 256)
        self.linear2 = nn.Linear(256, 1600)
        self.linear3 = nn.Linear(1600, 1600)
        self.linear4 = nn.Linear(1600, 73728)
        self.bn1 = nn.BatchNorm1d(256)
        self.bn2 = nn.BatchNorm1d(1600)
        self.bn3 = nn.BatchNorm1d(1600)
        self.relu = nn.LeakyReLU(inplace=True)

    def forward(self, x):
        #print ('W2 in: ', x.shape)
        x = self.relu(self.bn1(self.linear1(x)))
        x = self.relu(self.bn2(self.linear2(x)))
        x = self.relu(self.bn3(self.linear3(x)))
        x = self.linear4(x)
        x = x.view(-1, 128, 64, 3, 3)
        #print ('W2 out: ', x.shape)
        return x


""" Linear (128 x 8196) """
class GeneratorW3(nn.Module):
    def __init__(self, args):
        super(GeneratorW3, self).__init__()
        for k, v in vars(args).items():
            setattr(self, k, v)
        self.name = 'GeneratorW3'
        self.linear1 = nn.Linear(128, 256)
        self.linear2 = nn.Linear(256, 256)
        self.linear3 = nn.Linear(256, 128*128*8*8)
        self.bn1 = nn.BatchNorm1d(256)
        self.bn2 = nn.BatchNorm1d(256)
        self.relu = nn.LeakyReLU(inplace=True)

    def forward(self, x):
        #print ('W3 in : ', x.shape)
        x = self.relu(self.bn1(self.linear1(x)))
        x = self.relu(self.bn2(self.linear2(x)))
        x = self.linear3(x)
        x = x.view(-1, 128, 128*8*8)
        # x = self.linear_out(x)
        #print ('W3 out: ', x.shape)
        return x


class GeneratorW4(nn.Module):
    def __init__(self, args):
        super(GeneratorW4, self).__init__()
        for k, v in vars(args).items():
            setattr(self, k, v)
        self.name = 'GeneratorW4'
        self.linear1 = nn.Linear(128, 256)
        self.linear2 = nn.Linear(256, 256)
        self.linear3 = nn.Linear(256, 128*10)
        self.bn1 = nn.BatchNorm1d(256)
        self.bn2 = nn.BatchNorm1d(256)
        self.relu = nn.LeakyReLU(inplace=True)

    def forward(self, x):
        #print ('W3 in : ', x.shape)
        x = self.relu(self.bn1(self.linear1(x)))
        x = self.relu(self.bn2(self.linear2(x)))
        x = self.linear3(x)
        x = x.view(-1, 10, 128)
        # x = self.linear_out(x)
        #print ('W3 out: ', x.shape)
        return x


class DiscriminatorZ(nn.Module):
    def __init__(self, args):
        super(DiscriminatorZ, self).__init__()
        for k, v in vars(args).items():
            setattr(self, k, v)
        
        self.name = 'Discriminator_wae'
        self.linear0 = nn.Linear(self.lcd*self.lcd*10, self.lcd*self.lcd)
        self.linear1 = nn.Linear(self.lcd*self.lcd, 256)
        #self.linear1 = nn.Linear(self.dim, 256)
        self.linear2 = nn.Linear(256, 1)
        self.relu = nn.LeakyReLU(.2, inplace=True)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # print ('Dz in: ', x.shape)
        x = x.view(self.batch_size, -1)
        if x.shape[-1] > self.lcd*self.lcd:
            x = self.relu(self.linear0(x))
        x = self.relu(self.linear1(x))
        x = self.linear2(x)
        x = self.sigmoid(x)
        # print ('Dz out: ', x.shape)
        return x


def sample_x(args, gen, id, grad=True):
    if type(gen) is list:
        res = []
        for i, g in enumerate(gen):
            data = next(g)
            x = (torch.tensor(data, requires_grad=grad)).cuda()
            res.append(x.view(*args.shapes[i]))
    else:
        data = next(gen)
        x = torch.tensor(data, requires_grad=grad).cuda()
        res = x.view(*args.shapes[id])
    return res


def sample_z(args, grad=True):
    z = torch.randn(args.batch_size, args.dim, requires_grad=grad).cuda()
    return z


def sample_z_like(shape, grad=True):
    z = torch.randn(*shape, requires_grad=grad).cuda()
    return z
 

def train_ae(args, netG, netE, x):
    netG.zero_grad()
    netE.zero_grad()
    x_encoding = netE(x)
    x_fake = ops.gen_layer(args, netG, x_encoding)
    # fake = netG(encoding)
    x_fake = x_fake.view(*args.shapes[args.id])
    ae_loss = F.mse_loss(x_fake, x)
    return ae_loss, x_fake


def train_wadv(args, netDz, netE, x, z):
    netDz.zero_grad()
    z_fake = netE(x).view(args.batch_size, -1)
    Dz_real = netDz(z)
    Dz_fake = netDz(z_fake)
    Dz_loss = -(torch.mean(Dz_real) - torch.mean(Dz_fake))
    Dz_loss.backward()


def load_cifar():
    transform_train = transforms.Compose([
    transforms.RandomCrop(32, padding=4),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
    ])  
    transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
    ])  
    trainset = torchvision.datasets.CIFAR10(root='./data', train=True,
                        download=True,
                        transform=transform_train)
    trainloader = torch.utils.data.DataLoader(trainset, batch_size=32,
                          shuffle=True,
                          num_workers=2)
    testset = torchvision.datasets.CIFAR10(root='./data', train=False,
                       download=True,
                       transform=transform_test)
    testloader = torch.utils.data.DataLoader(testset, batch_size=32,
                         shuffle=False, num_workers=2)
    return trainloader, testloader


# hard code the two layer net
def train_clf(args, Z, data, target, val=False):
    """ calc classifier loss """
    data, target = data.cuda(), target.cuda()
    def moments(x):
        m = x.detach().view(x.shape[1], -1)
        m.requires_grad = False
        return (torch.mean(m, 1), torch.var(m, 1))

    out = F.conv2d(data, Z[0], stride=1, padding=1)
    mean, var = moments(out)
    out = F.batch_norm(out, mean, var)
    out = F.relu(out)
    out = F.max_pool2d(out, 2, 2)
    out = F.conv2d(out, Z[1], stride=1, padding=1)
    mean, var = moments(out)
    out = F.batch_norm(out, mean, var)
    out = F.relu(out)
    out = F.max_pool2d(out, 2, 2)
    out = out.view(-1, 128*8*8)
    out = F.linear(out, Z[2])
    out = F.relu(out)
    out = F.linear(out, Z[3])
    loss = F.cross_entropy(out, target)
    correct = None
    if val:
        pred = out.data.max(1, keepdim=True)[1]
        correct = pred.eq(target.data.view_as(pred)).long().cpu().sum()
    # (clf_acc, clf_loss), (oa, ol) = ops.clf_loss(args, Z)
    return (correct, loss)


def cov(x, y):
    mean_x = torch.mean(x, dim=0, keepdim=True)
    mean_y = torch.mean(y, dim=0, keepdim=True)
    cov_x = torch.matmul((x-mean_x).transpose(0, 1), x-mean_x)
    cov_x /= 999
    cov_y = torch.matmul((y-mean_y).transpose(0, 1), y-mean_y)
    cov_y /= 999
    cov_loss = F.mse_loss(cov_y, cov_x)
    return cov_loss


def free_params(module: nn.Module):
    for p in module.parameters():
        p.requires_grad = True


def frozen_params(module: nn.Module):
    for p in module.parameters():
        p.requires_grad = False


def train(args):
    
    torch.manual_seed(8734)
    
    netE = Encoder(args).cuda()
    W1 = GeneratorW1(args).cuda()
    W2 = GeneratorW2(args).cuda()
    W3 = GeneratorW3(args).cuda()
    W4 = GeneratorW4(args).cuda()
    print (netE, W1, W2, W3)

    optimizerE = optim.Adam(netE.parameters(), lr=3e-4, betas=(0.5, 0.9), weight_decay=1e-4)
    optimizerW1 = optim.Adam(W1.parameters(), lr=5e-4, betas=(0.5, 0.9), weight_decay=1e-4)
    optimizerW2 = optim.Adam(W2.parameters(), lr=5e-4, betas=(0.5, 0.9), weight_decay=1e-4)
    optimizerW3 = optim.Adam(W3.parameters(), lr=5e-4, betas=(0.5, 0.9), weight_decay=1e-4)
    optimizerW4 = optim.Adam(W4.parameters(), lr=5e-4, betas=(0.5, 0.9), weight_decay=1e-4)
    
    best_test_acc, best_test_loss = 0.95, 0.001
    args.best_loss, args.best_acc = best_test_loss, best_test_acc
    if args.resume:
        netE, optimizerE = load_model(args, netE, optimizerE, 'single_code1', m1)
        W1, optimizerW1 = load_model(args, W1, optimizerW1, 'single_code1', m2)
        W2, optimizerW2 = load_model(args, W2, optimizerW2, 'single_code1', m3)
        W3, optimizerW3, stats = load_model(args, W3, optimizerW3, 'single_code1', m4)
        W4, optimizerW3, stats = load_model(args, W3, optimizerW4, 'single_code1', m4)
        best_test_acc, best_test_loss = stats
        print ('==> resumeing models at ', stats)

    cifar_train, cifar_test = load_cifar()
    if args.use_x:
        base_gen = datagen.load(args)
        w1_gen = utils.inf_train_gen(base_gen[0])
        w2_gen = utils.inf_train_gen(base_gen[1])
        w3_gen = utils.inf_train_gen(base_gen[2])
        w4_gen = utils.inf_train_gen(base_gen[2])

    one = torch.FloatTensor([1]).cuda()
    mone = (one * -1).cuda()
   
    for _ in range(1000):
        for batch_idx, (data, target) in enumerate(cifar_train):

            netE.zero_grad()
            W1.zero_grad()
            W2.zero_grad()
            W3.zero_grad()
            if args.use_x:
                x, x2, x3 = sample_x(args, [w1_gen, w2_gen, w3_gen], 0)
            z = sample_z_like((args.batch_size, args.ze,))
            w1_code, w2_code, w3_code, w4_code = netE(z)
            w1_out, w2_out = [], []
            l1 = W1(w1_code)
            l2 = W2(w2_code)
            l3 = W3(w2_code)
            l4 = W4(w4_code.contiguous().view(args.batch_size, -1))
            
            for (z1, z2, z3, z4) in zip(l1, l2, l3, l4):
                correct, loss = train_clf(args, [z1, z2, z3, z4], data, target, val=True)
                scaled_loss = (1000*loss) #+ z1_loss + z2_loss + z3_loss
                scaled_loss.backward(retain_graph=True)
            optimizerE.step()
            optimizerW1.step()
            optimizerW2.step()
            optimizerW3.step()
            optimizerW4.step()
            loss = loss.item()
                
            if batch_idx % 50 == 0:
                acc = (correct / 1) 
                norm_z1 = np.linalg.norm(z1.data)
                norm_z2 = np.linalg.norm(z2.data)
                print ('**************************************')
                print ('Acc: {}, Loss: {}'.format(acc, loss))
                print ('Filter norm: ', norm_z1)
                print ('Linear norm: ', norm_z2)
                print ('**************************************')
            if batch_idx % 100 == 0:
                test_acc = 0.
                test_loss = 0.
                for i, (data, y) in enumerate(cifar_test):
                    z = sample_z_like((args.batch_size, args.ze,))
                    w1_code, w2_code, w3_code, w4_code = netE(z)
                    l1 = W1(w1_code)
                    l2 = W2(w2_code)
                    l3 = W3(w3_code)
                    l4 = W4(w4_code.contiguous().view(args.batch_size, -1))
                    min_loss_batch = 10.
                    z_test = [l1[0], l2[0], l3[0], l4[0]]
                    for (z1, z2, z3, z4) in zip(l1, l2, l3, l4):
                        correct, loss = train_clf(args, [z1, z2, z3, z4], data, y, val=True)
                        if loss.item() < min_loss_batch:
                            min_loss_batch = loss.item()
                            z_test = [z1, z2, z3, z4]
                        test_acc += correct.item()
                        test_loss += loss.item()
                #y_acc, y_loss = utils.test_samples(args, z_test, train=True)
                test_loss /= len(cifar_test.dataset) * 32
                test_acc /= len(cifar_test.dataset) * 32
                print ('Test Accuracy: {}, Test Loss: {}'.format(test_acc, test_loss))
                # print ('FC Accuracy: {}, FC Loss: {}'.format(y_acc, y_loss))
                if test_loss < best_test_loss or test_acc > best_test_acc:
                    print ('==> new best stats, saving')
                    if test_loss < best_test_loss:
                        best_test_loss = test_loss
                        args.best_loss = test_loss
                    if test_acc > best_test_acc:
                        best_test_acc = test_acc
                        args.best_acc = test_acc
                    utils.save_model(args, netE, optimizerE, 'single_code1', test_acc)
                    utils.save_model(args, W1, optimizerW1, 'single_code1', test_acc)
                    utils.save_model(args, W2, optimizerW2, 'single_code1', test_acc)
                    utils.save_model(args, W3, optimizerW3, 'single_code1', test_acc)
                    utils.save_model(args, W4, optimizerW3, 'single_code1', test_acc)

                #print ('FC Accuracy: {}, FC Loss: {}'.format(y_acc, y_loss))


if __name__ == '__main__':

    args = load_args()
    modeldef = netdef.nets()[args.model]
    pprint.pprint (modeldef)
    # log some of the netstat quantities so we don't subscript everywhere
    args.stat = modeldef
    args.shapes = modeldef['shapes']
    args.lcd = modeldef['base_shape']
    # why is a running product so hard in python
    args.gcd = int(np.prod([*args.shapes[0]]))
    train(args)
