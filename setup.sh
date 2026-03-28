#!/usr/bin/env bash

set -euo pipefail

install-required-software () {
    sudo apt-get update;
    sudo apt-get upgrade;
    sudo apt-get install \
        needrestart \
        python3-flask \
        samba \
        smbclient \
        unattended-upgrades -y;
    sudo apt-get autoremove;
}

disable-wifi-and-bluetooth () {
    CONFIG_PATH="/boot/firmware/config.txt"
    [ ! -f "$CONFIG_PATH" ] && CONFIG_PATH="/boot/config.txt"

    echo "Hardening network interfaces..."

    # Append to config if not already present
    grep -q "dtoverlay=disable-wifi" "$CONFIG_PATH" || echo "dtoverlay=disable-wifi" | sudo tee -a "$CONFIG_PATH" > /dev/null
    grep -q "dtoverlay=disable-bt" "$CONFIG_PATH" || echo "dtoverlay=disable-bt" | sudo tee -a "$CONFIG_PATH" > /dev/null

    # Disable services
    sudo systemctl mask bluetooth.service;
    sudo systemctl mask hciuart.service;

    echo "Hardware vectors disabled. Reboot required for changes to take effect."
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
    sudo systemctl restart systemd-udevd;

    RULES_FILE="/etc/udev/rules.d/10-write-blocker.rules"

    # 1. Run the verification and capture the output
    if sudo udevadm verify "$RULES_FILE"; then
        echo "[SUCCESS] Rule syntax is valid."

        # 2. Reload the daemon to pick up the new file
        sudo udevadm control --reload-rules

        # 3. Trigger ONLY block devices to minimize system noise
        # This is cleaner for forensic logs than a full system trigger
        sudo udevadm trigger --subsystem-match=block --action=add

        echo "[CONFIRMED] Write-blocker rules applied to block subsystem."
    else
        echo "----------------------------------------------------------"
        echo "CRITICAL ERROR: udev rule verification failed!"
        echo "The write-blocker has NOT been updated."
        echo "----------------------------------------------------------"
        exit 1
    fi
}

setup-samba-share () {
    sudo mkdir -p /etc/samba;
    cat ./src/etc/samba/smb.conf.local | sudo tee -a /etc/samba/smb.conf;
    sudo systemctl restart samba;

    echo " "
    echo "Let's verify that the samba share is correctly setup.  Hit enter went prompted for a password (it's blank)"
    echo " "
    smbclient -L localhost;

    echo " "
    read -rp "Did you see 'Forensic Disk in the output? (Y/N): " confirm

    case confirm in
        Yy)
            echo " "
            echo "Great! Moving on..."
            ;;
        Nn)
            exit 1
        *)
            echo "Please choose Y or N"
            ;;
    esac
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

    echo " "
    echo "Congrats on making it this far!  In about twenty seconds, we'll restart the system."
    echo " "
    echo "If everything goes well, after the reboot, you'll be able to ssh user@192.168.99.50 -i /path/to/your/key"
    echo " "

    sleep 20;

    sudo nmcli connection up Forensic-Net;
    sudo systemctl reboot
}

install-required-software;
disable-wifi-and-bluetooth;
setup-unattended-uprades;
setup-udev-rules;
setup-dconf-locks;
setup-auto-ingest-script;
setup-samba-share;
setup-web-control;
setup-local-only-network;
