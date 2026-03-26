#!/usr/bin/env bash

set -euo pipefail

install-required-software () {
    apt-get update;
    apt-get install \
        needrestart \
        samba \
        smbclient \
        unattended-upgrades -y
}

setup-unattended-uprades () {
    mkdir -p /etc/apt/apt.conf.d;
    cp ./src/etc/apt/apt.conf.d/52unattended-upgrades-local /etc/apt/apt.conf.d/
}

setup-udev-rules () {
    mkdir -p /etc/udev/rules.d;
    cp ./src/etc/udev/rules.d/10-write-blocker.rules /etc/udev/rules.d/
}

setup-dconf-locks () {
    mkdir -p /etc/dconf/db/local.d/locks;
    cp ./src/etc/dconf/db/local.d/00-disable-automount /etc/dconf/db/local.d/00-disable-automount;
    cp ./src/etc/dconf/db/local.d/locks/automount /etc/dconf/db/local.d/locks/automount;
    dconf update
}

setup-auto-ingest-script () {
    mkdir -p /usr/local/bin;
    mkdir -p /etc/systemd/system/systemd-udevd.service.d;
    cp ./src/usr/local/bin/auto-ingest.sh /usr/local/bin/auto-ingest.sh;
    cp ./src/etc/systemd/system/auto-ingest@.service /etc/systemd/system/auto-ingest@.service;
    cp ./src/etc/systemd/system/systemd-udevd.service.d/override.conf /etc/systemd/system/systemd-udevd.service.d/override.conf
    chmod +x /usr/local/bin/auto-ingest.sh;
    systemctl daemon-reload;
    systemctl enable --now auto-ingest@.service;
    systemctl restart systemd-udevd;
    udevadm control --reload-rules
}

setup-samba-share () {
    mkdir -p /etc/samba;
    cat ./src/etc/samba/smb.conf.local >> /etc/samba/smb.conf;
    systemctl restart samba;
}

setup-web-control () {
    mkdir -p /var/www/control;
    cp ./src/var/www/control/app.py /var/www/control/;
    cp ./src/etc/systemd/system/web-control.service /etc/systemd/system/web-control.service;
    systemctl daemon-reload;
    systemctl enable --now web-control.service;
}

setup-local-only-network () {
    nmcli connection add type ethernet \
        con-name Forensic-Net \
        ifname eth0 \
        ipv4.method shared \
        ipv4.addresses 192.168.99.50/24;

    nmcli connection modify Forensic-Net \
        connection.autoconnect yes;

    nmcli connection up Forensic-Net;
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
