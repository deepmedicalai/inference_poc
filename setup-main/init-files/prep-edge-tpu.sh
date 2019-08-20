#!/usr/bin/env bash

PYTHON_VERSION="37"
cd ~
mkdir -p edge && pushd edge

wget https://dl.google.com/coral/edgetpu_api/edgetpu_api_latest.tar.gz -O edgetpu_api.tar.gz --trust-server-names

tar xzf edgetpu_api.tar.gz

popd