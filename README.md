# pi-write-blocker-scripts

Note: This is still experimental.  At the moment, it's in heavy development.  I would not use this for _any_ serious purpose without serious testing!

### General Notes

This readme has the latest version of the setup instructions for the Write Blocker appliance. The historical (much more manual) setup instructions are found in [docs/archive/setup-steps.md](docs/archive/setup-steps.md).

### Setup

The general flow for setting this up is:
- Use the Raspberry Pi imager to configure your SD card
- Login and download this repository
- Run the setup script
- Reboot and connect over your private LAN switch
- Begin using the appliance

#### Using the imager to configure your SD card

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
  - **Locale:** Set to your local time zone and language (e.g., `en_GB.UTF-8`).
  - **Connectivity:** Ethernet (Preferred) or WiFi (if required for initial update).
  - **Raspberry Pi Connect:** Off, but could be enabled if you need.

Once the image is finished verifying, you can insert it into the raspberry pi, connect it to your network, and then boot it up.

#### Login and Initial Setup

Upon first logging in, you might discover that there is an issue with your locales settings.  It will alert you (probably loudly).  To remedy this:

- `sudo dpkg-reconfigure locales`
  - Select `en_GB.UTF-8 UTF-8`
  - Select `en_US.UTF-8 UTF-8`
  - Confirm Choices
  - For default locale, select: `en_US.UTF-8`  (I get it, but fewer things complain.)
  - Confirm choices and exit the menu
- Install git: `sudo apt-get update; sudo apt-get install git -y`

Once completed, get the helper scripts:
- `git clone https://github.com/jdmartin/rpi-write-blocker.git`
- `cd rpi-write-blocker`

Run setup (at the end of this process, which is only slightly interactive, the Pi will reboot):

`./setup.sh`

#### Connecting over the private LAN

At this stage, you probably just got disconnected.  It's cool, and expected!

- Plug your computer into the switch via ethernet (and turn off your Wi-Fi)
- You can SSH into the Pi by using `ssh user@192.168.99.50 -i /path/to/your/key`
- You should be able to access the control interface via: http://192.168.99.50/

<hr>

## Testing the Appliance and Validating the Setup

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

Now, let's make sure our web control works.

- `ls -al /mnt/forensic_disk` (should see whatever's on the device)
- Visit web control [http://192.168.99.50](http://192.168.99.50), eject
ls -al /mnt/forensic_disk (should no longer see files)
