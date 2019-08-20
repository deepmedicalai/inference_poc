#!/bin/bash -eu

#REPO=${REPO:-cimryan}
#BRANCH=${BRANCH:-master}
HEADLESS_SETUP=${HEADLESS_SETUP:-false}
USE_LED_FOR_SETUP_PROGRESS=true
CONFIGURE_ARCHIVING=${CONFIGURE_ARCHIVING:-true}
ARCHIVE_SYSTEM=${ARCHIVE_SYSTEM:-cifs}
UPGRADE_PACKAGES=${UPGRADE_PACKAGES:-true}
DMAI_EDGE_HOSTNAME=${DMAI_EDGE_HOSTNAME:-"dmai-edge-0001"}
#export campercent=${campercent:-50}   #usage is removed

MAIN_SERVER_URL=${MAIN_SERVER_URL:-"http://172.20.10.4:5000"}
MAIN_SERVER_APIKEY=${MAIN_SERVER_APIKEY:-"edge0001-key"}

# internal settings
BACKINGFILES_MOUNTPOINT=/backingfiles
MUTABLE_MOUNTPOINT=/mutable
G_MASS_STORAGE_CONF_FILE_NAME=/etc/modprobe.d/g_mass_storage.conf

export INSTALL_DIR=${INSTALL_DIR:-/root/bin}

function setup_progress () {
  local setup_logfile=/boot/deepmedicalai-headless-setup.log
  if [ $HEADLESS_SETUP = "true" ]
  then
    echo "$( date ) : $1" >> "$setup_logfile"
  fi
    echo $1
}

if ! [ $(id -u) = 0 ]
then
  setup_progress "STOP: Run sudo -i."
  exit 1
fi

function headless_setup_populate_variables () {
  # Pull in the conf file variables to make avail to this script and subscripts
  if [ -e /boot/deepmedicalai_setup_variables.conf ] && [ $HEADLESS_SETUP = "true" ]
  then
    #loads config to current script
    source /boot/deepmedicalai_setup_variables.conf
  fi
}


function headless_setup_mark_setup_failed () {
  if [ $HEADLESS_SETUP = "true" ]
  then
    setup_progress "ERROR: Setup Failed."
    touch /boot/DEEPMEDICALAI_EDGE_SETUP_FAILED
  fi
}

function headless_setup_mark_setup_success () {
  if [ $HEADLESS_SETUP = "true" ]
  then

    if [ -e /boot/DEEPMEDICALAI_EDGE_SETUP_FAILED ]
    then
      rm /boot/DEEPMEDICALAI_EDGE_SETUP_FAILED
    fi

    rm /boot/DEEPMEDICALAI_EDGE_SETUP_STARTED
    touch /boot/DEEPMEDICALAI_EDGE_SETUP_FINISHED
    # This sed shouldn't be needed, but double checking just to be sure. 
    sed -i'.bak' -e "s/TEMPARCHIVESERVER/$archiveserver/g" /etc/rc.local
    setup_progress "Main setup completed. Remounting file systems read only."
  fi
}

function headless_setup_progress_flash () {
  if [ $USE_LED_FOR_SETUP_PROGRESS = "true" ] && [ $HEADLESS_SETUP = "true" ]
  then
    /etc/stage_flash $1
  fi
}

function setup_led_off () {

  if [ $USE_LED_FOR_SETUP_PROGRESS = "true" ] && [ $HEADLESS_SETUP = "true" ]
  then
    echo "none" | sudo tee /sys/class/leds/led0/trigger > /dev/null
    echo 1 | sudo tee /sys/class/leds/led0/brightness > /dev/null
  fi
}

function setup_led_on () {

  if [ $USE_LED_FOR_SETUP_PROGRESS = "true" ] && [ $HEADLESS_SETUP = "true" ]
  then
    echo 0 | sudo tee /sys/class/leds/led0/brightness > /dev/null
  fi
}

function check_variable () {
  local var_name="$1"
  if [ -z "${!var_name+x}" ]
  then
    setup_progress "STOP: Define the variable $var_name like this: export $var_name=value"
    exit 1
  fi
}


function check_available_space () {
  #moved from `verify-configuration.sh`
  setup_progress "Verifying that there is sufficient space available on the MicroSD card..."

  local available_space="$( parted -m /dev/mmcblk0 u b print free | tail -1 | cut -d ":" -f 4 | sed 's/B//g' )"

  if [ "$available_space" -lt  4294967296 ]
  then
    setup_progress "STOP: The MicroSD card is too small."
    exit 1
  fi

  setup_progress "There is sufficient space available."
}

function verify_configuration () {
  #get_script /tmp verify-configuration.sh setup/pi
  #/tmp/verify-configuration.sh
  # moved function "check_available_space" from `verify-configuration.sh`
  check_available_space
}

# function get_script () {
#   local local_path="$1"
#   local name="$2"
#   local remote_path="${3:-}"
  
#   curl --fail -o "$local_path/$name" https://raw.githubusercontent.com/"$REPO"/teslausb/"$BRANCH"/"$remote_path"/"$name"
#   # wget -O "$local_path/$name" https://raw.githubusercontent.com/"$REPO"/teslausb/"$BRANCH"/"$remote_path"/"$name"
#   chmod +x "$local_path/$name"
#   setup_progress "Downloaded $local_path/$name ..."
# }

function ensure_script(){
  #custom version of `get_script`. It does not download file but ensures that it has necessary permission
  local local_path="$1"
  local name="$2"
  chmod +x "$local_path/$name"
  setup_progress "Enabled $local_path/$name ..."
}

# will not use as files are integrated
# function get_ancillary_setup_scripts () {
#   get_script /tmp create-backingfiles-partition.sh setup/pi
#   get_script /tmp create-backingfiles.sh setup/pi
#   get_script /tmp make-root-fs-readonly.sh setup/pi
#   get_script /root configure.sh setup/pi
# }

function fix_cmdline_txt_modules_load ()
{
  setup_progress "Fixing the modules-load parameter in /boot/cmdline.txt..."
  cp /boot/cmdline.txt ~
  cat ~/cmdline.txt | sed 's/ modules-load=dwc2,g_ether/ modules-load=dwc2/' > /boot/cmdline.txt
  rm ~/cmdline.txt
  setup_progress "Fixed cmdline.txt."
}



function create_backingfiles_partition_internal() {
  #paramaters are global already
  #BACKINGFILES_MOUNTPOINT="$1"
  #MUTABLE_MOUNTPOINT="$2"

  setup_progress "Checking existing partitions..."
  PARTITION_TABLE=$(parted -m /dev/mmcblk0 unit B print)
  DISK_LINE=$(echo "$PARTITION_TABLE" | grep -e "^/dev/mmcblk0:")
  DISK_SIZE=$(echo "$DISK_LINE" | cut -d ":" -f 2 | sed 's/B//' )

  ROOT_PARTITION_LINE=$(echo "$PARTITION_TABLE" | grep -e "^2:")
  LAST_ROOT_PARTITION_BYTE=$(echo "$ROOT_PARTITION_LINE" | sed 's/B//g' | cut -d ":" -f 3)

  FIRST_BACKINGFILES_PARTITION_BYTE="$(( $LAST_ROOT_PARTITION_BYTE + 1 ))"
  LAST_BACKINGFILES_PARTITION_DESIRED_BYTE="$(( $DISK_SIZE - (100 * (2 ** 20)) - 1))"

  ORIGINAL_DISK_IDENTIFIER=$( fdisk -l /dev/mmcblk0 | grep -e "^Disk identifier" | sed "s/Disk identifier: 0x//" )

  setup_progress "Modifying partition table for backing files partition..."
  BACKINGFILES_PARTITION_END_SPEC="$(( $LAST_BACKINGFILES_PARTITION_DESIRED_BYTE / 1000000 ))M"
  parted -a optimal -m /dev/mmcblk0 unit B mkpart primary ext4 "$FIRST_BACKINGFILES_PARTITION_BYTE" "$BACKINGFILES_PARTITION_END_SPEC"

  setup_progress "Modifying partition table for mutable (writable) partition for script usage..."
  MUTABLE_PARTITION_START_SPEC="$BACKINGFILES_PARTITION_END_SPEC"
  parted  -a optimal -m /dev/mmcblk0 unit B mkpart primary ext4 "$MUTABLE_PARTITION_START_SPEC" 100%

  NEW_DISK_IDENTIFIER=$( fdisk -l /dev/mmcblk0 | grep -e "^Disk identifier" | sed "s/Disk identifier: 0x//" )

  setup_progress "Writing updated partitions to fstab and /boot/cmdline.txt"
  sed -i "s/${ORIGINAL_DISK_IDENTIFIER}/${NEW_DISK_IDENTIFIER}/g" /etc/fstab
  sed -i "s/${ORIGINAL_DISK_IDENTIFIER}/${NEW_DISK_IDENTIFIER}/" /boot/cmdline.txt

  setup_progress "Formatting new partitions..."
  mkfs.ext4 -F /dev/mmcblk0p3
  mkfs.ext4 -F /dev/mmcblk0p4

  echo "/dev/mmcblk0p3 $BACKINGFILES_MOUNTPOINT ext4 auto,rw,noatime 0 2" >> /etc/fstab
  echo "/dev/mmcblk0p4 $MUTABLE_MOUNTPOINT ext4 auto,rw 0 2" >> /etc/fstab
}



function add_drive () {
  local name="$1"
  local label="$2"
  local size="$3"

  local filename="$4"
  echo "Allocating ${size}K for $filename..."
  fallocate -l "$size"K "$filename"
  mkfs.vfat "$filename" -F 32 -n "$label"

  local mountpoint=/mnt/"$name"

  mkdir "$mountpoint"
  echo "$filename $mountpoint vfat noauto,users,umask=000 0 0" >> /etc/fstab
}

function create_deepmedicalai_directory () {
  # added to use variables
  local name="$1"
  local mountpoint=/mnt/"$name"
  local mountdir="$mountpoint"/AnalizeThis

  mount "$mountpoint"
  mkdir "$mountdir"
  umount "$mountpoint"
}

function create_backingfiles_internal() {
  #moved from `create-backingfiles.sh`

  #CAM_PERCENT becomes local
  local dmai_disk_percent=50


  FREE_1K_BLOCKS="$(df --output=avail --block-size=1K $BACKINGFILES_MOUNTPOINT/ | tail -n 1)"


  ONE_DISK_SIZE="$(( $FREE_1K_BLOCKS * $dmai_disk_percent / 100 ))"
  ONE_DISK_FILE_NAME="$BACKINGFILES_MOUNTPOINT/dmai1_disk.bin"
  add_drive "dmai1" "DMAI1" "$ONE_DISK_SIZE" "$ONE_DISK_FILE_NAME"

  if [ "$dmai_disk_percent" -lt 100 ]
  then
    TWO_DISK_SIZE="$(df --output=avail --block-size=1K $BACKINGFILES_MOUNTPOINT/ | tail -n 1)"
    TWO_DISK_FILE_NAME="$BACKINGFILES_MOUNTPOINT/dmai2_disk.bin"
    add_drive "dmai2" "DMAI2" "$TWO_DISK_SIZE" "$TWO_DISK_FILE_NAME"
    echo "options g_mass_storage file=$TWO_DISK_FILE_NAME,$ONE_DISK_FILE_NAME removable=1,1 ro=0,0 stall=0 iSerialNumber=123456" > "$G_MASS_STORAGE_CONF_FILE_NAME"
  else
    echo "options g_mass_storage file=$ONE_DISK_FILE_NAME removable=1 ro=0 stall=0 iSerialNumber=123456" > "$G_MASS_STORAGE_CONF_FILE_NAME"
  fi

  create_deepmedicalai_directory "dmai1"
  #added to have folder on both mounts
  create_deepmedicalai_directory "dmai2"
}


function create_usb_drive_backing_files () {
  if [ ! -e "$BACKINGFILES_MOUNTPOINT" ]
  then
    mkdir "$BACKINGFILES_MOUNTPOINT"
  fi

  if [ ! -e "$MUTABLE_MOUNTPOINT" ]
  then
    mkdir "$MUTABLE_MOUNTPOINT"
  fi
  
  if [ ! -e /dev/mmcblk0p3 ]
  then
    setup_progress "Starting to create backing files partition..."
    #/tmp/create-backingfiles-partition.sh "$BACKINGFILES_MOUNTPOINT" "$MUTABLE_MOUNTPOINT"
    #use copied internal implementation. No parameters are passed as these are global already
    create_backingfiles_partition_internal
  fi
  
  if ! findmnt --mountpoint $BACKINGFILES_MOUNTPOINT
  then
    setup_progress "Mounting the partition for the backing files..."
    mount $BACKINGFILES_MOUNTPOINT
    setup_progress "Mounted the partition for the backing files."
  fi

  if [ ! -e $BACKINGFILES_MOUNTPOINT/*.bin ]
  then
    setup_progress "Creating backing disk files."
    #/tmp/create-backingfiles.sh "$campercent" "$BACKINGFILES_MOUNTPOINT"
    #use copies internal implementation. No parameters are passed as there are global alread
    create_backingfiles_internal
  fi
}

function configure_hostname () {
  # Headless image already has hostname set
  if [ ! $HEADLESS_SETUP = "true" ]
  then
    setup_progress "Configuring the hostname..."

    local new_host_name="$DMAI_EDGE_HOSTNAME"
    cp /etc/hosts ~
    sed "s/raspberrypi/$new_host_name/g" ~/hosts > /etc/hosts
    rm ~/hosts

    cp /etc/hostname ~
    sed "s/raspberrypi/$new_host_name/g" ~/hostname > /etc/hostname
    setup_progress "Configured the hostname."
    rm ~/hostname
  fi
}

function make_root_fs_readonly () {
  #/tmp/make-root-fs-readonly.sh
  make_root_fs_readonly_internal
}

function update_package_index () {
  setup_progress "Updating package index files..."
  apt-get update
}

function upgrade_packages () {
  if [ "$UPGRADE_PACKAGES" = true ]
  then
    setup_progress "Upgrading installed packages..."
    apt-get --assume-yes upgrade
  else
    setup_progress "Skipping package upgrade."
  fi
}

function install_rc_local () {
    local install_home="$1"

    if grep -q archiveloop /etc/rc.local
    then
        echo "Skipping rc.local installation"
        return
    fi

    echo "Configuring /etc/rc.local to run the archive scripts at startup..."
    echo "#!/bin/bash -eu" > ~/rc.local
    echo "archiveserver=\"${archiveserver}\"" >> ~/rc.local
    echo "install_home=\"${install_home}\"" >> ~/rc.local
    cat << 'EOF' >> ~/rc.local
LOGFILE=/tmp/rc.local.log

function log () {
  echo "$( date )" >> "$LOGFILE"
  echo "$1" >> "$LOGFILE"
}

log "Launching archival script..."
"$install_home"/archiveloop "$archiveserver" &
log "All done"
exit 0
EOF

    cat ~/rc.local > /etc/rc.local
    rm ~/rc.local
    echo "Installed rc.local."
}


function check_archive_configs () {
    echo -n "Checking archive configs: "

    case "$ARCHIVE_SYSTEM" in
        rsync)
            check_variable "RSYNC_USER"
            check_variable "RSYNC_SERVER"
            check_variable "RSYNC_PATH"
            export archiveserver="$RSYNC_SERVER"
            ;;
        rclone)
            check_variable "RCLONE_DRIVE"
            check_variable "RCLONE_PATH"
            export archiveserver="8.8.8.8" # since it's a cloud hosted drive we'll just set this to google dns    
            ;;
        cifs)
            check_variable "sharename"
            check_variable "shareuser"
            check_variable "sharepassword"
            check_variable "archiveserver"
            ;;
        none)
            ;;
        *)
            echo "STOP: Unrecognized archive system: $ARCHIVE_SYSTEM"
            exit 1
            ;;
    esac
    
    echo "done"
}

function get_archive_module () {

    case "$ARCHIVE_SYSTEM" in
        rsync)
            echo "run/rsync_archive"
            ;;
        rclone)
            echo "run/rclone_archive"
            ;;
        cifs)
            echo "run/cifs_archive"
            ;;
        *)
            echo "Internal error: Attempting to configure unrecognized archive system: $ARCHIVE_SYSTEM"
            exit 1
            ;;
    esac
}

function check_pushover_configuration () {
    if [ ! -z "${pushover_enabled+x}" ]
    then
        if [ ! -n "${pushover_user_key+x}" ] || [ ! -n "${pushover_app_key+x}"  ]
        then
            echo "STOP: You're trying to setup Pushover but didn't provide your User and/or App key."
            echo "Define the variables like this:"
            echo "export pushover_user_key=put_your_userkey_here"
            echo "export pushover_app_key=put_your_appkey_here"
            exit 1
        elif [ "${pushover_user_key}" = "put_your_userkey_here" ] || [  "${pushover_app_key}" = "put_your_appkey_here" ]
        then
            echo "STOP: You're trying to setup Pushover, but didn't replace the default User and App key values."
            exit 1
        fi
    fi
}

function configure_pushover () {
    if [ ! -z "${pushover_enabled+x}" ]
    then
        echo "Enabling pushover"
        echo "export pushover_enabled=true" > /root/.deepMedicalAIPushoverCredentials
        echo "export pushover_user_key=$pushover_user_key" >> /root/.deepMedicalAIPushoverCredentials
        echo "export pushover_app_key=$pushover_app_key" >> /root/.deepMedicalAIPushoverCredentials
    else
        echo "Pushover not configured."
    fi
}

function install_archive_scripts () {
    local install_path="$1"
    local archive_module="$2"

    echo "Installing base archive scripts into $install_path"
    ensure_script $install_path archiveloop
    ensure_script $install_path remountfs_rw
    ensure_script $install_path lookup-ip-address.sh

    echo "Installing archive module scripts"
    ensure_script $install_path verify-archive-configuration.sh 
    ensure_script $install_path configure-archive.sh
    ensure_script $install_path archive-clips.sh 
    ensure_script $install_path connect-archive.sh 
    ensure_script $install_path disconnect-archive.sh 
    ensure_script $install_path write-archive-configs-to.sh 
    ensure_script $install_path archive-is-reachable.sh 

    echo "Installing main server communication scripts"
    ensure_script $install_path main-server-ready-for-transfer.sh
    ensure_script $install_path main-server-status-notifier.sh
    ensure_script $install_path main-server-complete-notified.sh

}

function install_pushover_scripts() {
    local install_path="$1"
    echo "Installing pushover scripts"
    ensure_script $install_path send-pushover
}

function check_pushover_configuration () {
    if [ ! -z "${pushover_enabled+x}" ]
    then
        if [ ! -n "${pushover_user_key+x}" ] || [ ! -n "${pushover_app_key+x}"  ]
        then
            echo "STOP: You're trying to setup Pushover but didn't provide your User and/or App key."
            echo "Define the variables like this:"
            echo "export pushover_user_key=put_your_userkey_here"
            echo "export pushover_app_key=put_your_appkey_here"
            exit 1
        elif [ "${pushover_user_key}" = "put_your_userkey_here" ] || [  "${pushover_app_key}" = "put_your_appkey_here" ]
        then
            echo "STOP: You're trying to setup Pushover, but didn't replace the default User and App key values."
            exit 1
        fi
    fi
}

function configure_mainserver_connector () {
  echo "Enabling main server connector"
  echo "export MAIN_SERVER_CONFIGURED=true" > /root/.deepMedicalAIMainServerCredentials
  echo "export MAIN_SERVER_URL=$MAIN_SERVER_URL" >> /root/.deepMedicalAIMainServerCredentials
  echo "export MAIN_SERVER_APIKEY=$MAIN_SERVER_APIKEY" >> /root/.deepMedicalAIMainServerCredentials  
}


function check_and_configure_pushover () {
  check_pushover_configuration
	configure_pushover
}

function configure_internal(){
  if [ "$ARCHIVE_SYSTEM" = "none" ]
  then
      echo "Skipping archive configuration."
      exit 0
  fi

  if ! [ $(id -u) = 0 ]
  then
      echo "STOP: Run sudo -i."
      exit 1
  fi

  if [ ! -e "$INSTALL_DIR" ]
  then
      #expected that INSTALL_DIR is created before and scripts are moved there
      #mkdir "$INSTALL_DIR"
      echo "STOP: It is expected that $INSTALL_DIR is present and has necessary scripts."
      exit 1
  fi

  #echo "Getting files from $REPO:$BRANCH"

  configure_mainserver_connector

  check_and_configure_pushover
  install_pushover_scripts "$INSTALL_DIR"

  check_archive_configs

  archive_module="$( get_archive_module )"
  echo "Using archive module: $archive_module"

  install_archive_scripts $INSTALL_DIR $archive_module
  "$INSTALL_DIR"/verify-archive-configuration.sh
  "$INSTALL_DIR"/configure-archive.sh

  install_rc_local "$INSTALL_DIR"

}

# Adapted from https://github.com/adafruit/Raspberry-Pi-Installer-Scripts/blob/master/read-only-fs.sh

function append_cmdline_txt_param() {
  local toAppend="$1"
  sed -i "s/\'/ ${toAppend}/g" /boot/cmdline.txt >/dev/null
}

function make_root_fs_readonly_internal() {
  echo "Removing unwanted packages..."
  apt-get remove -y --force-yes --purge triggerhappy logrotate dphys-swapfile
  apt-get -y --force-yes autoremove --purge
  # Replace log management with busybox (use logread if needed)
  echo "Installing ntp and busybox-syslogd..."
  apt-get -y --force-yes install ntp busybox-syslogd; dpkg --purge rsyslog

  echo "Configuring system..."
    
  # Add fastboot, noswap and/or ro to end of /boot/cmdline.txt
  append_cmdline_txt_param fastboot
  append_cmdline_txt_param noswap
  append_cmdline_txt_param ro

  # Move fake-hwclock.data to /mutable directory so it can be updated
  if ! findmnt --mountpoint /mutable
  then
      echo "Mounting the mutable partition..."
      mount /mutable
      echo "Mounted."
  fi
  if [ ! -e "/mutable/etc" ]
  then
      mkdir -p /mutable/etc
  fi

  if [ ! -L "/etc/fake-hwclock.data" ] && [ -e "/etc/fake-hwclock.data" ]
  then
      echo "Moving fake-hwclock data"
      mv /etc/fake-hwclock.data /mutable/etc/fake-hwclock.data
      ln -s /mutable/etc/fake-hwclock.data /etc/fake-hwclock.data
  fi

  # Create a configs directory for others to use
  if [ ! -e "/mutable/configs" ]
  then
      mkdir -p /mutable/configs
  fi

  # Move /var/spool to /tmp
  rm -rf /var/spool
  ln -s /tmp /var/spool

  # Change spool permissions in var.conf (rondie/Margaret fix)
  sed -i "s/spool\s*0755/spool 1777/g" /usr/lib/tmpfiles.d/var.conf >/dev/null

  # Move dhcpd.resolv.conf to tmpfs
  mv /etc/resolv.conf /tmp/dhcpcd.resolv.conf
  ln -s /tmp/dhcpcd.resolv.conf /etc/resolv.conf

  # Update /etc/fstab
  # make /boot read-only
  # make / read-only
  # tmpfs /var/log tmpfs nodev,nosuid 0 0
  # tmpfs /var/tmp tmpfs nodev,nosuid 0 0
  # tmpfs /tmp     tmpfs nodev,nosuid 0 0
  sed -i -r "s@(/boot\s+vfat\s+\S+)@\1,ro@" /etc/fstab
  sed -i -r "s@(/\s+ext4\s+\S+)@\1,ro@" /etc/fstab
  echo "" >> /etc/fstab
  echo "tmpfs /var/log tmpfs nodev,nosuid 0 0" >> /etc/fstab
  echo "tmpfs /var/tmp tmpfs nodev,nosuid 0 0" >> /etc/fstab
  echo "tmpfs /tmp    tmpfs nodev,nosuid 0 0" >> /etc/fstab
}


export -f setup_progress
export HEADLESS_SETUP

update_package_index

headless_setup_populate_variables

# If USE_LED_FOR_SETUP_PROGRESS = true. 
setup_led_off

# Flash for stage 2 headless (verify requested configuration)
headless_setup_progress_flash 1

setup_progress "Verifying that the requested configuration is valid..."

verify_configuration

# Flash for Stage 3 headless (grab scripts)
headless_setup_progress_flash 2

setup_progress "Downloading additional setup scripts."

#no need
#get_ancillary_setup_scripts

pushd ~

fix_cmdline_txt_modules_load

echo "" >> /etc/fstab

# Flash for stage 4 headless (Create backing files)
headless_setup_progress_flash 3

create_usb_drive_backing_files

configure_hostname

# Flash for stage 5 headless (Mark success, FS readonly)
headless_setup_progress_flash 4

headless_setup_mark_setup_success

if [ "$CONFIGURE_ARCHIVING" = true ]
then
  #/root/configure.sh
  configure_internal
fi

make_root_fs_readonly

upgrade_packages

# If USE_LED_FOR_SETUP_PROGRESS = true. 
setup_led_on

setup_progress "All done."