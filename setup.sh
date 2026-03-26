#!/usr/bin/env bash

set -euo pipefail

install-required-software () {
    sudo apt-get update;
    sudo apt-get install \
        needrestart \
        samba \
        smbclient \
        unattended-upgrades -y
}

setup-unattended-uprades () {
    sudo mkdir -p /etc/apt/apt.conf.d;
    sudo cp ./src/etc/apt/apt.conf.d/52unattended-upgrades-local /etc/apt/apt.conf.d/
}

setup-udev-rules () {
    sudo mkdir -p /etc/udev/rules.d;
    sudo cp ./src/etc/udev/rules.d/10-write-blocker.rules /etc/udev/rules.d/;
    sudo systemctl stop udisks2;
    sudo systemctl mask udisks2;
}

setup-dconf-locks () {
    sudo mkdir -p /etc/dconf/db/local.d/locks;
    sudo cp ./src/etc/dconf/db/local.d/00-disable-automount /etc/dconf/db/local.d/00-disable-automount;
    sudo cp ./src/etc/dconf/db/local.d/locks/automount /etc/dconf/db/local.d/locks/automount;
    sudo dconf update;
}

setup-auto-ingest-script () {
    sudo mkdir -p /usr/local/bin;
    sudo mkdir -p /etc/systemd/system/systemd-udevd.service.d;
    sudo cp ./src/usr/local/bin/auto-ingest.sh /usr/local/bin/auto-ingest.sh;
    sudo cp ./src/etc/systemd/system/auto-ingest@.service /etc/systemd/system/auto-ingest@.service;
    sudo cp ./src/etc/systemd/system/systemd-udevd.service.d/override.conf /etc/systemd/system/systemd-udevd.service.d/override.conf
    sudo chmod +x /usr/local/bin/auto-ingest.sh;
    sudo systemctl daemon-reload;
    sudo systemctl enable --now auto-ingest@.service;
    sudo systemctl restart systemd-udevd;
    sudo udevadm control --reload-rules;
}

setup-samba-share () {
    sudo mkdir -p /etc/samba;
    sudo cat ./src/etc/samba/smb.conf.local >> /etc/samba/smb.conf;
    sudo systemctl restart samba;
}

setup-web-control () {
    sudo mkdir -p /var/www/control;
    sudo cp ./src/var/www/control/app.py /var/www/control/;
    sudo cp ./src/etc/systemd/system/web-control.service /etc/systemd/system/web-control.service;
    sudo systemctl daemon-reload;
    sudo systemctl enable --now web-control.service;
}

setup-local-only-network () {
    sudo nmcli connection add type ethernet \
        con-name Forensic-Net \
        ifname eth0 \
        ipv4.method shared \
        ipv4.addresses 192.168.99.50/24;

    sudo nmcli connection modify Forensic-Net \
        connection.autoconnect yes;

    sudo nmcli connection up Forensic-Net;
}

install-required-software;
setup-unattended-uprades;
setup-udev-rules;
setup-dconf-locks;
setup-auto-ingest-script;
setup-samba-share;
setup-web-control;
setup-local-only-network;

echo " "
echo "If you made it this far, it's probably a good idea to reboot!"
echo " "
echo "If everything goes well, you'll be able to ssh user@192.168.99.50 -i /path/to/your/key"
echo " "
