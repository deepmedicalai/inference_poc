import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

# relevance model
class RelevanceNet(nn.Module):
    def __init__(self):
        super(RelevanceNet, self).__init__()
        self.conv1 = nn.Conv2d(1,32,5)   #kernel size (5,5)>> (None, 44, 44, 32) 
        self.dropout1 = nn.Dropout(p=0.5)
        
        self.conv2 = nn.Conv2d(32,64,5) #kernel size (5,5) >>  (None, 18, 18, 64)  
        self.conv2_bn = nn.BatchNorm2d(64)
        self.dropout2 = nn.Dropout(p=0.5)
        #self.conv3 = nn.Conv2d(64,128,3) #kernel size (3,3)
        self.fc1 = nn.Linear(9*9*64,256)  #if 28x28, then 4*4
        self.dense1_bn = nn.BatchNorm1d(256)
        self.fc2 = nn.Linear(256,5)  
        
        #self.fc3 = nn.Linear(256,5)
        
    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.max_pool2d(x,2) #F.max_pool2d(x,2,2)   (None, 22, 22, 32)
        
        x = self.dropout1(x)
        x = F.relu(self.conv2_bn(self.conv2(x)))   #(None, 18, 18, 64)  Adding normalization
        
        x = F.max_pool2d(x,2)  #F.max_pool2d(x,2,2)   (None, 9, 9, 64) 
        x = self.dropout2(x)
        #x = F.relu(self.conv3(x))
        x = x.view(-1, 9*9*64)
        x = F.relu(self.dense1_bn(self.fc1(x)))
        #x = F.relu(self.fc2(x))
        x = self.fc2(x)
        return F.log_softmax(x, dim=1)

# segmentation model
class UNet(nn.Module):
    def __init__(self, n_channels=1, n_classes=2):
        super(UNet, self).__init__()
        self.inc = down(1, 32)
        self.down1 = down(32, 64)
        self.down2 = down(64, 128)
        self.down3 = down(128, 256)
        self.down4 = down(256, 512)
        self.up1 = up(512, 512)
        self.up2 = up(512 + 256, 256)
        self.up3 = up(256 + 128, 128)
        self.up4 = up(128 + 64, 64)
        self.outc = outconv(64 + 32, 1)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)
        x = self.up1(x5, x4)
        x = self.up2(x, x3)
        x = self.up3(x, x2)
        x = self.up4(x, x1)
        x = self.outc(x)
        return torch.tanh(x)

class down(nn.Module):
    def __init__(self, in_ch, out_ch):
        super(down, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, stride=2, padding=1),
            nn.InstanceNorm2d(out_ch),
            nn.LeakyReLU())
        
    def forward(self, x):
        x = self.conv(x)
        return x


class up(nn.Module):
    def __init__(self, in_ch, out_ch):
        super(up, self).__init__()
        self.conv = nn.Sequential(
            nn.ConvTranspose2d(in_ch, out_ch, 2, stride=2, padding=0),
            nn.InstanceNorm2d(out_ch),
            nn.Dropout(p=0.5),
            nn.ReLU())

    def forward(self, x1, x2):
        x = self.conv(x1)
        x = torch.cat([x2, x], dim=1)
        return x


class outconv(nn.Module):
    def __init__(self, in_ch, out_ch):
        super(outconv, self).__init__()
        self.conv = nn.ConvTranspose2d(in_ch, out_ch, 2, stride=2, padding=0)

    def forward(self, x):
        x = self.conv(x)
        return x     



def conv3D_output_size(img_size, padding, kernel_size, stride):
    # compute output shape of conv3D
    outshape = (np.floor((img_size[0] + 2 * padding[0] - (kernel_size[0] - 1) - 1) / stride[0] + 1).astype(int),
                np.floor((img_size[1] + 2 * padding[1] - (kernel_size[1] - 1) - 1) / stride[1] + 1).astype(int),
                np.floor((img_size[2] + 2 * padding[2] - (kernel_size[2] - 1) - 1) / stride[2] + 1).astype(int))
    return outshape

class CNN3D(nn.Module):
    def __init__(self, num_classes=2, num_frames=30, width=128, height=128):  
        super(CNN3D, self).__init__()

        self.ch1, self.ch2, self.ch3 = 32, 64, 128
        self.k1, self.k2 = (5, 5, 5), (3, 3, 3)  # 3d kernel size
        self.s1, self.s2 = (2, 2, 2), (2, 2, 2)  # 3d strides
        self.pd1, self.pd2 = (0, 0, 0), (0, 0, 0)  # 3d padding
        
        self.conv1_outshape = conv3D_output_size((num_frames, width, height), self.pd1, self.k1, self.s1)
        self.conv2_outshape = conv3D_output_size(self.conv1_outshape, self.pd2, self.k2, self.s2)
        self.conv3_outshape = conv3D_output_size(self.conv2_outshape, self.pd2, self.k2, self.s2)
        
        self.conv1 = nn.Conv3d(in_channels=1, out_channels=self.ch1, kernel_size=self.k1, stride=self.s1,
                               padding=self.pd1)
        self.bn1 = nn.BatchNorm3d(self.ch1)
        self.conv2 = nn.Conv3d(in_channels=self.ch1, out_channels=self.ch2, kernel_size=self.k2, stride=self.s2,
                               padding=self.pd2)
        self.bn2 = nn.BatchNorm3d(self.ch2)
        self.conv3 = nn.Conv3d(in_channels=self.ch2, out_channels=self.ch3, kernel_size=self.k2, stride=self.s2,
                       padding=self.pd2)
        self.bn3 = nn.BatchNorm3d(self.ch3)
        self.relu = nn.ReLU(inplace=True)
        self.drop = nn.Dropout3d(0.2)
        self.pool = nn.MaxPool3d(2)
        self.fc1 = nn.Linear(self.ch3*self.conv3_outshape[0]*self.conv3_outshape[1]*self.conv3_outshape[2], 256)  # fully connected hidden layer
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, num_classes)  # fully connected layer, output = multi-classes
    
    
    def forward(self, x_3d):
        # Conv 1
        x = self.conv1(x_3d)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.drop(x)

        # Conv 2
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu(x)
        x = self.drop(x)
        
        # Conv 3
        x = self.conv3(x)
        x = self.bn3(x)
        x = self.relu(x)
        x = self.drop(x)
        
        # FC 1 and 2
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = F.dropout(x, 0.2, training=self.training)
        x = self.fc3(x)
        return F.log_softmax(x, dim=1)