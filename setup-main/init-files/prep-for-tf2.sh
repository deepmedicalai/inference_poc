#!/usr/bin/env bash

echo "Getting necessary updates for TF2"

sudo apt-get install -y libhdf5-dev libc-ares-dev libeigen3-dev
sudo pip3 install keras_applications==1.0.7 --no-deps
sudo pip3 install keras_preprocessing==1.0.9 --no-deps
sudo pip3 install h5py==2.9.0
sudo apt-get install -y openmpi-bin libopenmpi-dev
sudo apt-get install -y libatlas-base-dev
pip3 install -U --user six wheel mock
sudo apt update;sudo apt upgrade

echo "Necessary updates for TF2 - completed"
