# Installation


## Initialize Rasbian

Use this video: https://www.youtube.com/watch?v=xhZjpYQImck

Disk id: disk2s1
More correct: https://www.raspberrypi.org/documentation/installation/installing-images/mac.md
We need `disk2` not `disk2s1`


Using Disk Utility: unmount
better cmd: `diskutil unmountDisk /dev/disk2`


Download Rasbian

https://www.raspberrypi.org/downloads/raspbian/

Run copy data to SD card

```
sudo dd bs=1m if=../images/2019-07-10-raspbian-buster-full.img of=/dev/rdisk2 conv=sync
```

Note: When initially the above command failed with `dd: /dev/rdisk2: Permission denied`

There was a meachnical lock on SD card. Cleared. reinserted. Run to check permissions:
```
ls -l /dev/disk2
```

Had to unmount again and then `dd` started without problem

Overall, copy of 4GB took about 80 seconds on 32 SanDisk card



## Enabling SSH

Source: https://www.youtube.com/watch?v=Ct9XwyYvmbU

```
cd /Volumes
ls
```
You should see `boot` 

```
cd boot
ls
```

Create SSH by creating file `ssh` without extension

```
touch ssh
ls
```
 
## Supplemental configuration

```
nano wpa_supplicant.conf
```

Here you enter like this:
```
country=us
update_config=1
ctrl_interface=/var/run/wpa_supplicant

network={
 scan_ssid=1
 ssid="MyNetworkSSID"
 psk="Pa55w0rd1234"
}
```

Note: `scan_ssid=1` in network if SSID is hidden
Note 2: Svae and Exit ==> Ctrl+X, then Y, then Enter

## Enabling DWC2

```
nano config.txt
```

Add in the end:
```

#Custom
dtoverlay=dwc2
```

Finally, open up the `cmdline.txt`. Be careful with this file, it is very picky with its formatting! Each parameter is seperated by a single space (it does not use newlines). Insert `modules-load=dwc2,g_ether` after `rootwait`. 




### Properly ejecting

```
cd ~
diskutil unmountDisk disk2
```

Detach your SD disk

Note: `cd ~` goes to home directory, so we can unmount disk and it is not "in use"

## Starting Raspberry Pi Zero W

Use USB to Micro (use USB port on RPi, it will power it up)

Use:
```
ssh pi@raspberrypi.local
```
Default pwd: `raspberry`


Good source: https://www.youtube.com/watch?v=upY4Fusi4zI


## Tools and useful cmds

### Check free memory

```
free -m
```

### Check disk space
```
df -h
```

## Installing DaemoinTools

https://isotope11.com/blog/manage-your-services-with-daemontools

```
sudo mkdir -p /package
sudo chmod 1755 /package
cd /package

sudo wget http://cr.yp.to/daemontools/daemontools-0.76.tar.gz
sudo tar -xpf daemontools-0.76.tar.gz
sudo rm -f daemontools-0.76.tar.gz
cd admin/daemontools-0.76
sudo package/install
```

### Starting Daemon
```
sudo apt-get install csh
csh -cf '/command/svscanboot &'
```

### Starting Daemon on Startup
```
sudo sed -i "1 a\csh -cf '/command/svscanboot &'" /etc/rc.local
sudo chmod +x /etc/rc.local
```

### Making services
```
mkdir /services
```

## Install Node.js On A Raspberry Pi Zero W Without NodeSource
Source: https://www.youtube.com/watch?v=qeHpXVUwI08

Go to nodejs.org/dist
find latest node (10.0.16 as of now)
look for 'arm6l' (L as lucky) >copy url for .qz
example: `https://nodejs.org/dist/v10.16.0/node-v10.16.0-linux-armv6l.tar.gz`


While SSH
```
cd /package
sudo curl -o nodejs.tar.qz https://nodejs.org/dist/v10.16.0/node-v10.16.0-linux-armv6l.tar.gz
```

Unzip it
```
sudo tar -xzf nodejs.tar.qz
sudo rm nodejs.tar.qz
```

Copy to user
```
sudo cp -r node-v10.16.0-linux-armv6l/* /usr/local/
```

Verify
```
node -v
```
should show `v10.16.0`

### Troubleshooting of DaemonTools

Fails on `package/install`.
Fix: https://kadirsert.blogspot.com/2012/10/gcc-compile-error-on-linux-when.html
Had to to 
```
cd src
sudo nano conf-cc
```


## Troubleshooting

### There was no Wifi. As conf was missing
`wpa_supplicant.conf` was missing

Fix in SSH:
```
cd /
cd boot
sudo touch wpa_supplicant.conf 
sudo nano wpa_supplicant.conf
```
then 
```
sudo reboot
```

Actually, it is normal that ssh and wpa_supplicant.conf files are disappearing. Welcome to Linux
