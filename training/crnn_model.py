"""Seven convolution layers and two bidirectional LSTMs, classic CRNN."""
import torch
from torch import nn
class BidirectionalLSTM(nn.Module):
    def __init__(self,n_in,n_hidden,n_out):
        super().__init__();self.rnn=nn.LSTM(n_in,n_hidden,bidirectional=True);self.embedding=nn.Linear(n_hidden*2,n_out)
    def forward(self,x):
        x,_=self.rnn(x);return self.embedding(x)
class CRNN(nn.Module):
    def __init__(self,n_classes,n_hidden=256):
        super().__init__();cnn=nn.Sequential();channels=[64,128,256,256,512,512,512]
        for i,c in enumerate(channels):
            cnn.add_module(f'conv{i}',nn.Conv2d(1 if i==0 else channels[i-1],c,2 if i==6 else 3,padding=0 if i==6 else 1))
            if i in [2,4,6]:cnn.add_module(f'batchnorm{i}',nn.BatchNorm2d(c))
            cnn.add_module(f'relu{i}',nn.ReLU(inplace=True))
            if i in [0,1]:cnn.add_module(f'pooling{i}',nn.MaxPool2d(2,2))
            if i in [3,5]:cnn.add_module(f'pooling{2 if i==3 else 3}',nn.MaxPool2d((2,2),(2,1),(0,1)))
        self.cnn=cnn;self.rnn=nn.Sequential(BidirectionalLSTM(512,n_hidden,n_hidden),BidirectionalLSTM(n_hidden,n_hidden,n_classes))
    def forward(self,x):return self.rnn(self.cnn(x).squeeze(2).permute(2,0,1)).log_softmax(2)
