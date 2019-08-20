#!/usr/bin/env bash
set -ex

TF_VERSION="2.0.0b1"
PYTHON_VERSION="37"
cd ~
mkdir -p tf2 && pushd tf2

wget "https://github.com/PINTO0309/Tensorflow-bin/raw/master/tensorflow-${TF_VERSION}-cp${PYTHON_VERSION}-cp${PYTHON_VERSION}m-linux_armv7l.whl"
sudo pip3 uninstall tensorflow
sudo -H pip3 install "tensorflow-${TF_VERSION}-cp${PYTHON_VERSION}-cp${PYTHON_VERSION}m-linux_armv7l.whl"

popd
