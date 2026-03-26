#!/usr/bin/env bash
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
