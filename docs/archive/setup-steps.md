---
title: Write-Blocker Methodology
author: Jon Martin
date: 2026-03-14
---

## 1. Initial System Provisioning

The write-blocker workstation is built on the Raspberry Pi 4 platform for its low power profile and hardware consistency. This section covers the "bare metal" setup before applying forensic configurations.

### 1.1. Imaging the Media
Using the [Raspberry Pi Imager](https://www.raspberrypi.com/software/){target="_blank"}, flash the OS with the following parameters:

- **Device:** Raspberry Pi 4 (or whatever you're using)
- **Operating System:** Raspberry Pi OS Lite (64-bit)
  - **Note**: If you're sure you won't need desktop software, you could:
    - Select "Raspberry Pi OS Lite" from the "Raspberry Pi OS (other) submenu.
- **Storage:** High-endurance microSD card (min 16GB)
- **OS Customization:**
  - **Hostname:** SomethingCleverHere
  - **User/Pass:** [Secure credentials set]
  - **SSH:** Enabled via Public Key Authentication only (you could adjust, if needed).
  - **Locale:** Set to your local time zone and language (e.g., `en_UK.UTF-8`).
  - **Connectivity:** Ethernet (Preferred) or WiFi (if required for initial update).
  - **Raspberry Pi Connect:** Off, but could be enabled if you need.

### 1.2. Initial Environment Setup
Once the Pi has booted, SSH into the machine:
`ssh user@<pi-ip-address> -i /path/to/your/key`

Elevate to root to perform system-wide configurations:
`sudo su -`

You _may_ need to configure your locale.  If so, it should prompt you and you would:

- `dpkg-reconfigure locales` and choose the right language

Now, let's make sure we start from a fully updated system:

- Install any package upgrades: `apt-get update; apt-get upgrade`
- If desired, install unattended-upgrades for automatic security updates:
  - Using your preferred editor (nano, vi, etc.), edit `/etc/apt/apt.conf.d/50unattended-upgrades`
  - Edit that file to block all but security updates, like this:
  
```
  Unattended-Upgrade::Origins-Pattern {
          // Codename based matching:
          // This will follow the migration of a release through different
          // archives (e.g. from testing to stable and later oldstable).
          // Software will be the latest available for the named release,
          // but the Debian release itself will not be automatically upgraded.
  //      "origin=Debian,codename=${distro_codename}-updates";
  //      "origin=Debian,codename=${distro_codename}-proposed-updates";
  //      "origin=Debian,codename=${distro_codename},label=Debian";
          "origin=Debian,codename=${distro_codename},label=Debian-Security";
          "origin=Debian,codename=${distro_codename}-security,label=Debian-Security";
  //      "o=Debian Backports,n=${distro_codename}-backports,l=Debian Backports";
  
          // Archive or Suite based matching:
          // Note that this will silently match a different release after
          // migration to the specified archive (e.g. testing becomes the
          // new stable).
  //      "o=Debian,a=stable";
  //      "o=Debian,a=stable-updates";
  //      "o=Debian,a=proposed-updates";
  //      "o=Debian Backports,a=stable-backports,l=Debian Backports";
  };
```

Unattended-upgrades is often best served by also using `needrestart` to alert you when an update is pending. It's useful either way, though, so let's install it here:

- `apt-get install needrestart`


## 2. Write-Blocker Architecture
Protection is enforced across three distinct layers of the Linux stack:

| Layer | Component | Mechanism |
| :--- | :--- | :--- |
| **Kernel** | `udev` | Sets physical block device to `RO` mode via `blockdev` |
| **Virtual** | `loopback` | Maps media to a read-only virtual device node |
| **Mount** | `vfs` | Enforces `ro` and `noatime` flags during mounting |

## 3. Implementation
We're going to start by adding a rule to `udev` that sets any mounted device under /dev/sd* to readonly:

- Let's edit `/etc/udev/rules.d/10-write-blocker.rules` and insert:

```
# Set the hardware block device to Read-Only
SUBSYSTEM=="block", KERNEL=="sd[a-z]*", ACTION=="add|change", RUN+="/sbin/blockdev --setro /dev/%k"

# Tell udisks and other tools to ignore this device entirely
SUBSYSTEM=="block", KERNEL=="sd[a-z]*", ENV{UDISKS_IGNORE}="1"
```

Let's verify that the rule works and is formatted correctly:

- `udevadm verify 10-write-blocker.rules`  (if good, proceed to next step)
- `udevadm control --reload-rules; udevadm trigger`

### 3.1. Preventing Automounts in other ways...
Let's start by preventing `udisks2` from automounting filesystems:

- `systemctl stop udisks2; systemctl mask udisks2`

If you're using the version of Raspberry Pi OS that has a desktop setup, then let's make sure GNOME's tools won't automount things, too:

- Create this directory: `mkdir -p /etc/dconf/db/local.d`
- Edit `/etc/dconf/db/local.d/00-disable-automount` and Insert:

```
[org/gnome/desktop/media-handling]
automount=false
automount-open=false

[org/gnome/settings-daemon/plugins/media-keys]
automount=false
```

Let's lock that directory:

- Create this directory: `mkdir -p /etc/dconf/db/local.d/locks`
- Edit `/etc/dconf/db/local.d/locks/automount` and insert:

```
/org/gnome/desktop/media-handling/automount
/org/gnome/desktop/media-handling/automount-open
/org/gnome/settings-daemon/plugins/media-keys/automount
```

- Update the config database:
  - `dconf update`


## 4. Let's try to break stuff
This whole thing only matters if we can prove that the drives aren't writable.  So, let's take a test USB (one that can be completely ruined, if we mess up!) and plug it in:

- Start by finding the device: `lsblk -o NAME,SIZE,FSTYPE,SERIAL`

My ouptut looks like this:
```
root@Thoth:~/test# lsblk -o NAME,SIZE,FSTYPE,SERIAL
NAME         SIZE FSTYPE SERIAL
loop0        1.8G swap
loop1        233G
└─loop1p1    233G vfat
sda          233G        04017223065f4a9869b013057f1ca937141c69c547f54548cf8736364e2ffcfc228600000000000000000000bb34b44e000c1b1895558107b42d3809
└─sda1       233G vfat
mmcblk0     29.5G        0x35656a1e
├─mmcblk0p1  512M vfat
└─mmcblk0p2   29G ext4
zram0        1.8G swap
```

So, it's /dev/sda (ignore loop1... that's a spoiler for later!)

Let's make sure that the device is being treated as read-only by using `cat /sys/block/sda/ro`  
  - If the response is `1`, then it's read-only.  If it's `0`, then it's not.
  
We're going to add an extra layer of safety by using `losetup` to create a virtual loopback device to access `/dev/sda`. Later on, this is probably something you'd want to build into a forensics workflow:

- First, setup the device: `losetup -r --find --partscan /dev/sda`
- Now, make the mount directory: `mkdir -p /mnt/forensic_disk`
- Next, we'll mount it. (If this fails to find the device, use the lsblk command above to find it... I'll assume `loop1p1`): `mount -o ro,noatime /dev/loop1p1 /mnt/forensic_disk`

Note: If you're using vfat, then that last command might be:
`mount -t vfat -o ro,noatime,noload /dev/loop1p1 /mnt/forensic_disk`

For ext4, it might be:
`mount -t ext4 -o ro,noatime,noload /dev/loop1p1 /mnt/forensic_disk`

Ok, at this point, we should have a virtual, read-only interface to our physical, kernel-protected device.  Let's prove it!

### 4.1. Testing

Let's start by making a baseline hash of the first 100MB of our device so we can compare later:

- `dd if=/dev/sda bs=1M count=100 | sha256sum > head.sha256`

Now, let's make a hash of the last 100MB:

- `dd if=/dev/sda bs=1M skip=$(($(blockdev --getsize64 /dev/sda) / 1024 / 1024 - 100)) | sha256sum > tail.sha256`

Ok, great, let's try modifying our disk.  For my tests, I tried:

- `touch /mnt/forensic_disk/test_file.txt`

This immediately returned: `touch: cannot touch '/mnt/forensic_disk/test_file.txt': Read-only file system`

Next, I tried ``rm /mnt/forensic_disk/some_existing_file` (in my case, some_existing_file was 'SampleData.xlsx'):

This also returned: `rm: cannot remove '/mnt/forensic_disk/SampleData.xlsx': Read-only file system`

Now, I want to prove that atimes aren't being modified.  For this, I chose another file and ran ``stat /mnt/forensic_disk/any_file.txt` (in my case, I chose 'SanDiskMemoryZone_QuickStartGuide.pdf')

The output for this one is:
```
File: /mnt/forensic_disk/SanDiskMemoryZone_QuickStartGuide.pdf
Size: 497832    	Blocks: 1024       IO Block: 32768  regular file
Device: 259,0	Inode: 1385        Links: 1
Access: (0755/-rwxr-xr-x)  Uid: (    0/    root)   Gid: (    0/    root)
Access: 2021-11-23 16:00:00.000000000 -0800
Modify: 2021-10-25 11:25:00.000000000 -0700
Change: 2021-10-25 11:25:00.000000000 -0700
Birth: 2021-11-24 09:59:45.360000000 -0800
```

Now, I try interacting with it by using `cat /mnt/forensic_disk/SanDiskMemoryZone_QuickStartGuide.pdf > /dev/null`

After this, I run the same stat command from above and compare:
```
File: /mnt/forensic_disk/SanDiskMemoryZone_QuickStartGuide.pdf
Size: 497832    	Blocks: 1024       IO Block: 32768  regular file
Device: 259,0	Inode: 1385        Links: 1
Access: (0755/-rwxr-xr-x)  Uid: (    0/    root)   Gid: (    0/    root)
Access: 2021-11-23 16:00:00.000000000 -0800
Modify: 2021-10-25 11:25:00.000000000 -0700
Change: 2021-10-25 11:25:00.000000000 -0700
Birth: 2021-11-24 09:59:45.360000000 -0800
```

Hooray! No change!

But let's make sure by running those two hash commands again (with a slight change):

- `dd if=/dev/sda bs=1M count=100 | sha256sum > head2.sha256`
- `dd if=/dev/sda bs=1M skip=$(($(blockdev --getsize64 /dev/sda) / 1024 / 1024 - 100)) | sha256sum > tail2.sha256`

Now, let's compare them and make sure there's no change.  (If this next command returns no output, there's no change):

`diff head.sha256 head2.sha256`

Also, compare the tails:

`diff tail.sha256 tail2.sha256`

In both cases, I had no changes! :)

## 5. Let's make the mounted devices available as shares
At this stage, we have a working appliance that will take any mounted device and ensure it is read-only.  However, we need to make those shares available, or this was all just a fun wander through Debian.  In this step, we'll configure samba to create read-only shares of our mounted filesystem.  In step 6, we'll then configure the networking that will allow this Raspberry Pi to create and manage a local-only network over a 'dumb' switch.  

Let's start by creating a script to mount things (safely) that you plug into the raspberry pi:

- In your preferred editor, edit `/usr/local/bin/auto-ingest.sh`:
- Insert this into that file:

```bash
#!/bin/bash
# Forensic Ingest Script
DEVICE_NODE="$1"
if [ -z "$DEVICE_NODE" ]; then echo "Usage: $0 <device_node>"; exit 1; fi

DEVICE="/dev/$DEVICE_NODE"
MOUNT_POINT="/mnt/forensic_disk"

# Define Full Paths
BLOCKDEV="/sbin/blockdev"
LOSETUP="/usr/sbin/losetup"
MOUNT="/usr/bin/mount"
UMOUNT="/usr/bin/umount"
MKDIR="/usr/bin/mkdir"
MOUNTPOINT="/usr/bin/mountpoint"

# 1. Forensic Zero-Check
$BLOCKDEV --setro "$DEVICE"

# 2. Cleanup
$UMOUNT -l "$MOUNT_POINT" 2>/dev/null
$LOSETUP -D

# 3. Setup Loopback
LOOP_DEV=$($LOSETUP -r --find --partscan --show "$DEVICE")

# 4. Attempt Mount
$MKDIR -p "$MOUNT_POINT"

# Determine if we should use noload (ext4/xfs only)
TARGET_DEV="${LOOP_DEV}p1"
if [ ! -b "$TARGET_DEV" ]; then TARGET_DEV="$LOOP_DEV"; fi

FSTYPE=$(/usr/bin/lsblk -no FSTYPE "$TARGET_DEV")

if [[ "$FSTYPE" == "ext4" || "$FSTYPE" == "xfs" ]]; then
    MOUNT_OPTS="ro,noatime,noload"
else
    # vfat/ntfs/exfat don't support 'noload'
    MOUNT_OPTS="ro,noatime"
fi

$MOUNT -o "$MOUNT_OPTS" "$TARGET_DEV" "$MOUNT_POINT"

# 5. Final Confirmation
if $MOUNTPOINT -q "$MOUNT_POINT"; then
    exit 0
else
    exit 1
fi
```

Next, update the `/etc/udev/rules.d/10-write-blocker.rules` to this:
```bash
# 1. Hardware Level: Force Read-Only immediately (This works fine)
SUBSYSTEM=="block", KERNEL=="sd[a-z]", ACTION=="add", RUN+="/sbin/blockdev --setro /dev/%k"

# 2. Automation Level: Trigger the Systemd service instead of the script
SUBSYSTEM=="block", KERNEL=="sd[a-z]", ACTION=="add", TAG+="systemd", ENV{SYSTEMD_WANTS}="auto-ingest@%k.service"

# 3. Cleanup Level
SUBSYSTEM=="block", KERNEL=="sd[a-z]", ACTION=="remove", RUN+="/usr/bin/umount -l /mnt/forensic_disk"
SUBSYSTEM=="block", KERNEL=="sd[a-z]", ACTION=="remove", RUN+="/usr/sbin/losetup -D"
```

- Save that and exit
- Make sure it's executable: `chmod +x /usr/local/bin/auto-ingest.sh`

Almost there, but we need to create the helper service that will run our mounting script:

- Edit `/etc/systemd/system/auto-ingest@.service`
- Insert this and save:
```bash
[Unit]
Description=Forensic Ingest on %I

[Service]
Type=oneshot
ExecStart=/usr/bin/bash /usr/local/bin/auto-ingest.sh %I
# This ensures the mount is visible to the whole system
MountFlags=shared

[Install]
WantedBy=multi-user.target
```
- Run `systemctl daemon-reload`
- Run `udevadm control --reload-rules`

Finally, let's make one more adjustment to ensure the shares won't be invisible when mounted:

- `mkdir -p /etc/systemd/system/systemd-udevd.service.d/`
- `echo -e "[Service]\nMountFlags=shared" | sudo tee /etc/systemd/system/systemd-udevd.service.d/override.conf`
- `systemctl daemon-reload`
- `systemctl restart systemd-udevd`

Now, let's install samba...

### 5.1. Installing Samba

Begin by installing the samba server via apt:

- `apt-get install samba -y`

Once that is installed, we can update the samba configuration to serve our `/mnt/forensic_disk` directory.  To do this:

- Edit `/etc/samba/smb.conf` in your editor of choice
- Append this block to the end:

```
[Forensic Disk]
   comment = Read-Only Forensic Ingest
   path = /mnt/forensic_disk
   browseable = yes
   read only = yes
   guest ok = yes
   force user = root
```

- Next, restart samba: `systemctl restart samba`

### 5.2. Making sure the share is active
We'll want to make sure our share works.  To do this (without needing to connect to it remotely, as we haven't set that up yet):

- Install smbclient so we can view shares: `apt-get install smbclient`
- Once installed, run `smbclient -L localhost`  (Hit enter when prompted for a password)

If successful, you should see:
```

	Sharename       Type      Comment
	---------       ----      -------
	print$          Disk      Printer Drivers
	Forensic Disk   Disk      Read-Only Forensic Ingest
	IPC$            IPC       IPC Service (Samba 4.22.8-Debian-4.22.8+dfsg-0+deb13u1)
	nobody          Disk      Home Directories
```
	
Assuming that's working as expected, let's move on to setting up a network with our dumb switch.
	
## 6. Create a control interface for unmounting disks without SSH
For ease of use, we're going to create a simple (likely ugly) web interface so that local users can unmount drives without logging in over SSH.

### 6.1. Creating the python app
Let's start by preparing a place for this to live on our system:

- `mkdir -p /var/www/control`

Next, let's add the script that will handle our unmounting (and eventually some log display)

Edit `/var/www/control/app.py` and insert:
```python
from flask import Flask, render_template_string
import subprocess
import os

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Thoth Control Panel</title>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 40px; background: #f0f2f5; }
        .container { background: white; padding: 30px; border-radius: 12px; display: inline-block; text-align: left; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 80%; max-width: 600px; }
        .btn { background: #e74c3c; color: white; padding: 15px 30px; border: none; border-radius: 8px; cursor: pointer; width: 100%; font-size: 1.1em; }
        pre { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 0.85em; }
        h2 { border-bottom: 2px solid #eee; padding-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Forensic Station</h2>
        <form action="/eject" method="post">
            <button type="submit" class="btn">UNMOUNT & EJECT DRIVE</button>
        </form>

        <h3>Last Ingest Log:</h3>
        <pre>{{ log_content }}</pre>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    # If you added a log line to your auto-ingest script, we display it here
    log_path = "/tmp/thoth_debug.log"
    content = "No logs found. Plug in a device to start."
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            content = f.read()
    return render_template_string(HTML_PAGE, log_content=content)

@app.route('/eject', methods=['POST'])
def eject():
    subprocess.run(["/usr/bin/umount", "-l", "/mnt/forensic_disk"])
    subprocess.run(["/usr/sbin/losetup", "-D"])
    # Clear the log on eject so the next person starts fresh
    if os.path.exists("/tmp/thoth_debug.log"):
        os.remove("/tmp/thoth_debug.log")
    return "<h2>Drive Ejected.</h2><p>Safe to swap hardware.</p><br><a href='/'>Back</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
```

Create a systemd service to run the control interface

- Edit `/etc/systemd/system/web-control.service`
- Insert this:
```bash
[Unit]
Description=Web Ejector UI
After=network.target

[Service]
ExecStart=/usr/bin/python3 /var/www/control/app.py
WorkingDirectory=/var/www/control
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```
- Enable it by running `systemctl daemon-reload` and then `systemctl enable --now web-control.service`

### 6.2 Try it out.

- To access the control interface, visit http://the_address_of_the_pi in your web browser (after the next section, the address will be http://192.168.99.50).  You should see this:
![](./resources/images/web-control.png)

- Assuming you've got a mounted drive, pressing the button should yield:
  - ![](./resources/images/ejected.png)

Ok, cool.  But a web service and shares are only useful if we have a way to access them, so...

## 7. Creating a local-only network
The goal is to make the share accessible to forensic workstations, but only over a local-only network via ethernet.  To achieve this, we'll use:

- A 'dumb' ethernet switch.
- ...luck?

### 7.1. Assign the Pi a static IP address
We'll want to make sure that we always know where the Pi is on our local network, so let's set it up with a static IP (this is also important for our DHCP server). We'll also tell the Pi to hand out addresses to other clients on its switch, so they can access it.

- Create the shared connection
`nmcli connection add type ethernet con-name Forensic-Net ifname eth0 ipv4.method shared ipv4.addresses 192.168.99.50/24`

- Ensure it starts automatically
`nmcli connection modify Forensic-Net connection.autoconnect yes`

- Bring it up
`nmcli connection up Forensic-Net`

At this stage, you probably just got disconnected.  It's cool, and expected!

- Plug your computer into the switch via ethernet (and turn off your Wi-Fi)
- You can SSH into the Pi by using `ssh user@192.168.99.50 -i /path/to/your/key`
- You should be able to access the control interface via: http://192.168.99.50/

To be continued...???
