"""Original VGG16+RPN+horizontal BiLSTM CTPN, not a GRU variant."""
import torch
from torch import nn
class CTPN(nn.Module):
    def __init__(self):
        super().__init__();channels=[64,64,128,128,256,256,256,512,512,512,512,512,512,512]
        self.convs=nn.ModuleList([nn.Conv2d(3 if i==0 else channels[i-1],c,3,padding=1) for i,c in enumerate(channels)])
        self.brnn=nn.LSTM(512,128,bidirectional=True,batch_first=True);self.context=nn.Linear(256,512)
        self.classifier=nn.Linear(512,20);self.regression=nn.Linear(512,40)
    def forward(self,x):
        for i,conv in enumerate(self.convs):
            x=torch.relu(conv(x))
            if i in [1,3,6,9]:x=nn.functional.max_pool2d(x,2,2)
        n,c,h,w=x.shape;x,_=self.brnn(x.permute(0,2,3,1).reshape(n*h,w,c))
        x=self.context(x)  # The original graph has NO ReLU here.
        return self.classifier(x).reshape(n,h,w,10,2).softmax(-1).reshape(n,h,w,20),self.regression(x).reshape(n,h,w,40)
