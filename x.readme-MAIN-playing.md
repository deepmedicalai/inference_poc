

Python 3.7.2 is installed

Addinf CIFS:
https://www.raspberrypi.org/documentation/remote-access/samba.md


Instructions
https://wiki.samba.org/index.php/Setting_up_Samba_as_a_Standalone_Server

just 
```
sudo /etc/init.d/smbd start
```


Helped for Mac to connect
https://derflounder.wordpress.com/2011/08/11/connecting-to-an-smb-server-from-the-command-line-in-os-x/



GDCM
```
apt install -y python-vtk6 libvtk6-dev cmake-curses-gui checkinstall swig
apt install -y python-vtk6 libvtk6-dev cmake-curses-gui checkinstall swig libpython3.7-dev

mkdir gdcm && cd gdcm && git clone --branch release git://git.code.sf.net/p/gdcm/gdcm

mkdir build && cd build


cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS=-fPIC -DCMAKE_CXX_FLAGS=-fPIC -DGDCM_BUILD_SHARED_LIBS:BOOL=ON -DGDCM_WRAP_PYTHON=ON PYTHON_EXECUTABLE=/usr/local/bin/python3.7 PYTHON_INCLUDE_DIR=/usr/local/lib/python3.7/site-packages/ GDCM_BUILD_SHARED_LIBS=ON GDCM_USE_VTK=ON ../gdcm


```



Example of docker Not Alpine with cv2

https://github.com/janza/docker-python3-opencv






creating virtual environment
https://www.pyimagesearch.com/2018/09/26/install-opencv-4-on-your-raspberry-pi/







install_dep
```
#!/usr/bin/env bash
set -ex

sudo apt-get purge -y libreoffice*
sudo apt-get clean
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get dist-upgrade -y
sudo apt-get autoremove -y
# For some reason I couldn't install libgtk2.0-dev or libgtk-3-dev without running the 
# following line
# See https://www.raspberrypi.org/forums/viewtopic.php?p=1254646#p1254665 for issue and resolution
sudo apt-get install -y devscripts debhelper cmake libldap2-dev libgtkmm-3.0-dev libarchive-dev \
                        libcurl4-openssl-dev intltool
sudo apt-get install -y build-essential cmake pkg-config libjpeg-dev libtiff5-dev libjasper-dev \
                        libavcodec-dev libavformat-dev libswscale-dev libv4l-dev \
                        libxvidcore-dev libx264-dev libgtk2.0-dev libgtk-3-dev \
                        libatlas-base-dev libblas-dev libeigen{2,3}-dev liblapack-dev \
                        gfortran python2.7-dev python3-dev
sudo pip2 install -U pip
sudo pip3 install -U pip
#sudo pip2 install numpy
#sudo pip3 install numpy
```



```
wget https://bootstrap.pypa.io/get-pip.py
sudo python3 get-pip.py
```

```
sudo pip install virtualenv virtualenvwrapper
sudo rm -rf ~/get-pip.py ~/.cache/pip
```


```
$ echo -e "\n# virtualenv and virtualenvwrapper" >> ~/.profile
$ echo "export WORKON_HOME=$HOME/.virtualenvs" >> ~/.profile
$ echo "export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3" >> ~/.profile
$ echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.profile
```

```
$ source ~/.profile
```

Increase swap file
```
$ sudo dphys-swapfile swapoff
$ sudo sed -i 's:CONF_SWAPSIZE=.*:CONF_SWAPSIZE=2048:g' /etc/dphys-swapfile
$ sudo /etc/init.d/dphys-swapfile stop
$ sudo /etc/init.d/dphys-swapfile start
```

```
mkvirtualenv cv -p python3
```

```
workon cv
```

install numpy
```
pip install numpy
```

build file

```
#!/usr/bin/env bash
set -ex

PYTHON_BIN="/usr/bin/python3"
echo $PYTHON_BIN
OPENCV_VERSION=4.1.0
pushd ~/opencv/opencv-$OPENCV_VERSION
mkdir -p build
pushd build
RPI_VERSION=$(awk '{print $3}' < /proc/device-tree/model)
if [[ $RPI_VERSION -ge 4 ]]; then
  NUM_JOBS=$(nproc)
else
  NUM_JOBS=1 # Earlier versions of the Pi don't have sufficient RAM to support compiling with multi$
fi

# -D ENABLE_PRECOMPILED_HEADERS=OFF
# is a fix for https://github.com/opencv/opencv/issues/14868

# -D OPENCV_EXTRA_EXE_LINKER_FLAGS=-latomic
# is a fix for https://github.com/opencv/opencv/issues/15192

cmake -D CMAKE_BUILD_TYPE=RELEASE \
      -D CMAKE_INSTALL_PREFIX=/usr/local \
      -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib-$OPENCV_VERSION/modules \
      -D OPENCV_ENABLE_NONFREE=ON \
      -D BUILD_PERF_TESTS=OFF \
      -D BUILD_TESTS=OFF \
      -D BUILD_DOCS=OFF \
      -D BUILD_EXAMPLES=OFF \
      -D ENABLE_PRECOMPILED_HEADERS=OFF \
      -D WITH_TBB=ON \
      -D WITH_OPENMP=ON \
      -D OPENCV_EXTRA_EXE_LINKER_FLAGS=-latomic \
      -D PYTHON3_EXECUTABLE=$(which python3) \
      -D PYTHON_EXECUTABLE=$(which python3) \
      -D PYTHON_DEFAULT_EXECUTABLE=$(which python3) \
      -D BUILD_NEW_PYTHON_SUPPORT=ON \
      -D INSTALL_PYTHON_EXAMPLES=OFF \
      -D BUILD_opencv_python3=ON \
      -D HAVE_opencv_python3=ON \
      ..
make -j "$NUM_JOBS"
popd; popd

```



Take a second now to ensure that the `Interpreter`  points to the correct Python 3 binary. Also check that numpy  points to our `NumPy` package which is installed inside the virtual environment.


```
$ sudo make install
$ sudo ldconfig
```


Return swap file
```
$ sudo dphys-swapfile swapoff
$ sudo sed -i 's:CONF_SWAPSIZE=.*:CONF_SWAPSIZE=100:g' /etc/dphys-swapfile
$ sudo /etc/init.d/dphys-swapfile stop
$ sudo /etc/init.d/dphys-swapfile start
```

Set ls
```
cd ~/.virtualenvs/cv/lib/python3.7/site-packages/
$ ln -s /usr/local/lib/python3.7/site-packages/cv2/python-3.7/cv2.cpython-37m-arm-linux-gnueabihf.so cv2.so cv2.so
$ cd ~
```