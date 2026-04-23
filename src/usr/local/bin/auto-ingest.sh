#!/usr/bin/env bash
# Forensic Ingest Script
DEVICE_NODE="$1"
if [ -z "$DEVICE_NODE" ]; then echo "Usage: $0 <device_node>"; exit 1; fi

DEVICE="/dev/$DEVICE_NODE"
MOUNT_POINT="/mnt/forensic_disk"
INFO_FILE="/tmp/.current_mount.info"

# Define Full Paths
UDEVADM="/usr/bin/udevadm"
BLOCKDEV="/sbin/blockdev"
LOSETUP="/usr/sbin/losetup"
MOUNT="/usr/bin/mount"
UMOUNT="/usr/bin/umount"
MKDIR="/usr/bin/mkdir"
MOUNTPOINT="/usr/bin/mountpoint"

# SAFETY: Never ingest the boot or root partitions
if [[ "$DEVICE_NODE" == "mmcblk0"* ]]; then
    echo "Access denied: Target is system storage."
    exit 1
fi

# 1. Forensic Zero-Check
$BLOCKDEV --setro "$DEVICE"

# 2. Cleanup
$UMOUNT -l "$MOUNT_POINT" 2>/dev/null
$LOSETUP -D

# 3. Setup Loopback
LOOP_DEV=$($LOSETUP -r --find --partscan --show "$DEVICE")

# --- SAFETY: Wait for kernel to create partition nodes ---
$UDEVADM settle --timeout=5

# 4. Attempt Mount
$MKDIR -p "$MOUNT_POINT"

# 4. Dynamic Partition Detection
# This finds the first partition (p1 or 1) regardless of the naming convention
TARGET_DEV=$(lsblk -lnpo NAME "$LOOP_DEV" | grep -vE "^$LOOP_DEV$" | head -n1)

# Fallback: If no partitions are found, attempt to mount the raw loop device (Superfloppy)
if [ -z "$TARGET_DEV" ]; then
    TARGET_DEV="$LOOP_DEV"
fi

FSTYPE=$(/usr/bin/lsblk -no FSTYPE "$TARGET_DEV")

if [[ "$FSTYPE" == "ext4" || "$FSTYPE" == "xfs" ]]; then
    MOUNT_OPTS="ro,noatime,noload"
else
    # vfat/ntfs/exfat don't support 'noload'
    MOUNT_OPTS="ro,noatime"
fi

$MOUNT -o "$MOUNT_OPTS" "$TARGET_DEV" "$MOUNT_POINT"

if $MOUNTPOINT -q "$MOUNT_POINT"; then
    # Only write the info file if we actually succeeded
    echo "PHYS_DEV=$DEVICE" > "$INFO_FILE"
    echo "LOOP_DEV=$LOOP_DEV" >> "$INFO_FILE"
    chmod 666 "$INFO_FILE"

    # 2. NEW: Refresh Network Shares so clients see the disk immediately
    /usr/sbin/exportfs -ar             # Reloads NFS exports
    /usr/bin/smbcontrol all reload-config  # Tells Samba to Refresh

    exit 0
else
    # Cleanup loop if mount failed
    $LOSETUP -d "$LOOP_DEV"
    exit 1
fi
