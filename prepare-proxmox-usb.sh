#!/bin/bash
# Proxmox VE 9 Unattended Installation USB Preparation Script
#
# This script prepares a bootable USB drive with Proxmox VE 9 ISO
# and adds the auto-install answer file for unattended installation
#
# Usage: sudo ./prepare-proxmox-usb.sh /dev/sdX path/to/proxmox.iso
#
# WARNING: This will ERASE all data on the target USB drive!

set -e  # Exit on any error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}"
   echo "Usage: sudo $0 /dev/sdX path/to/proxmox.iso"
   exit 1
fi

# Check arguments
if [ "$#" -ne 2 ]; then
    echo -e "${RED}Error: Invalid number of arguments${NC}"
    echo "Usage: sudo $0 /dev/sdX path/to/proxmox.iso"
    echo ""
    echo "Example: sudo $0 /dev/sdb proxmox-ve_9.0-1.iso"
    exit 1
fi

USB_DEVICE="$1"
ISO_FILE="$2"

# Validate USB device
if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: $USB_DEVICE is not a valid block device${NC}"
    exit 1
fi

# Validate ISO file
if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: $ISO_FILE not found${NC}"
    exit 1
fi

# Safety check - don't allow /dev/sda (usually system disk)
if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda (system disk)${NC}"
    echo "Please specify a USB drive (e.g., /dev/sdb, /dev/sdc)"
    exit 1
fi

# Confirm with user
echo -e "${YELLOW}WARNING: This will ERASE all data on $USB_DEVICE${NC}"
echo ""
lsblk "$USB_DEVICE"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo -e "${GREEN}Step 1: Writing Proxmox ISO to USB drive...${NC}"
dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=sync
sync

echo ""
echo -e "${GREEN}Step 2: Mounting USB partition to add answer file...${NC}"

# Wait for kernel to update partition table
sleep 2
partprobe "$USB_DEVICE" 2>/dev/null || true
sleep 1

# Find the ESP (EFI System Partition) on the USB
# Proxmox ISO creates a partition with FAT filesystem
USB_PART="${USB_DEVICE}2"  # Usually the second partition is the ESP

# Create mount point
MOUNT_POINT="/mnt/proxmox-usb-$$"
mkdir -p "$MOUNT_POINT"

# Try to mount
if mount "$USB_PART" "$MOUNT_POINT" 2>/dev/null; then
    echo -e "${GREEN}Mounted $USB_PART to $MOUNT_POINT${NC}"
else
    # Try first partition if second fails
    USB_PART="${USB_DEVICE}1"
    if mount "$USB_PART" "$MOUNT_POINT" 2>/dev/null; then
        echo -e "${GREEN}Mounted $USB_PART to $MOUNT_POINT${NC}"
    else
        echo -e "${RED}Error: Could not mount USB partition${NC}"
        rmdir "$MOUNT_POINT"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}Step 3: Copying answer file to USB...${NC}"

# Copy answer file to root of USB
ANSWER_FILE="proxmox-auto-install-answer.toml"
if [ -f "$ANSWER_FILE" ]; then
    cp "$ANSWER_FILE" "$MOUNT_POINT/answer.toml"
    echo -e "${GREEN}Answer file copied to USB${NC}"
else
    echo -e "${YELLOW}Warning: $ANSWER_FILE not found in current directory${NC}"
    echo "You'll need to manually copy it to the USB root as 'answer.toml'"
fi

# Copy post-install script if it exists
POST_INSTALL="proxmox-post-install.sh"
if [ -f "$POST_INSTALL" ]; then
    cp "$POST_INSTALL" "$MOUNT_POINT/"
    echo -e "${GREEN}Post-install script copied to USB${NC}"
fi

# Sync and unmount
sync
umount "$MOUNT_POINT"
rmdir "$MOUNT_POINT"

echo ""
echo -e "${GREEN}Step 4: Modifying bootloader for auto-install...${NC}"

# Mount again to modify grub config
MOUNT_POINT="/mnt/proxmox-usb-$$"
mkdir -p "$MOUNT_POINT"
mount "$USB_PART" "$MOUNT_POINT"

# Modify grub.cfg to add auto-install boot option
GRUB_CFG="$MOUNT_POINT/boot/grub/grub.cfg"
if [ -f "$GRUB_CFG" ]; then
    # Backup original
    cp "$GRUB_CFG" "$GRUB_CFG.backup"

    # Add auto-install entry at the beginning (before timeout)
    # The auto-install uses the answer file from the root of the USB
    sed -i '/^set timeout/i \
menuentry "Proxmox VE (Auto Install)" {\n\
    linux /boot/linux26 auto-install-cfg=/dev/disk/by-label/PROXMOX/answer.toml splash=silent\n\
    initrd /boot/initrd.img\n\
}\n' "$GRUB_CFG"

    # Set default to auto-install and reduce timeout
    sed -i 's/^set timeout=.*/set timeout=5/' "$GRUB_CFG"
    sed -i 's/^set default=.*/set default=0/' "$GRUB_CFG"

    echo -e "${GREEN}Bootloader configured for auto-install${NC}"
else
    echo -e "${YELLOW}Warning: Could not find grub.cfg, auto-install may need manual boot parameter${NC}"
fi

# Sync and unmount
sync
umount "$MOUNT_POINT"
rmdir "$MOUNT_POINT"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}USB drive preparation complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Insert USB drive into Dell XPS L701X"
echo "2. Boot from USB (press F12 during boot)"
echo "3. Select 'Proxmox VE (Auto Install)' from menu"
echo "4. Installation will proceed automatically"
echo "5. After reboot, run post-install configuration"
echo ""
echo -e "${YELLOW}IMPORTANT: Review and change the root password in answer.toml before use!${NC}"
echo ""
