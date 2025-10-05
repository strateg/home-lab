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
echo -e "${GREEN}Step 2: Detecting USB partitions...${NC}"

# Wait for kernel to update partition table
sleep 3
partprobe "$USB_DEVICE" 2>/dev/null || true
sleep 2

# Show partition table for debugging
echo "Partition table:"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE

# Find the EFI partition (usually vfat/fat32)
USB_PART=""
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ -b "$part" ]; then
        FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")
        echo "Checking $part: filesystem=$FSTYPE"
        if [[ "$FSTYPE" == "vfat" ]] || [[ "$FSTYPE" == "iso9660" ]]; then
            USB_PART="$part"
            echo -e "${GREEN}Found mountable partition: $USB_PART ($FSTYPE)${NC}"
            break
        fi
    fi
done

if [ -z "$USB_PART" ]; then
    echo -e "${YELLOW}No vfat partition found, trying partition 2...${NC}"
    if [ -b "${USB_DEVICE}2" ]; then
        USB_PART="${USB_DEVICE}2"
    elif [ -b "${USB_DEVICE}p2" ]; then
        USB_PART="${USB_DEVICE}p2"
    elif [ -b "${USB_DEVICE}1" ]; then
        USB_PART="${USB_DEVICE}1"
    elif [ -b "${USB_DEVICE}p1" ]; then
        USB_PART="${USB_DEVICE}p1"
    else
        echo -e "${RED}Error: Could not find any partition on USB${NC}"
        exit 1
    fi
fi

# Create mount point
MOUNT_POINT="/mnt/proxmox-usb-$$"
mkdir -p "$MOUNT_POINT"

# Try to mount with different filesystem types
echo "Attempting to mount $USB_PART..."
if mount -t vfat "$USB_PART" "$MOUNT_POINT" 2>/dev/null; then
    echo -e "${GREEN}Mounted $USB_PART as vfat${NC}"
elif mount -t iso9660 "$USB_PART" "$MOUNT_POINT" 2>/dev/null; then
    echo -e "${YELLOW}Warning: Mounted as iso9660 (read-only)${NC}"
    echo -e "${YELLOW}ISO filesystem is read-only. We'll remount it as read-write...${NC}"
    umount "$MOUNT_POINT"
    # For ISO9660, we need to extract, modify, and recreate
    echo -e "${YELLOW}This method won't work with iso9660. Need to use alternative approach.${NC}"
    rmdir "$MOUNT_POINT"

    echo ""
    echo -e "${BLUE}Alternative: Manual answer file placement${NC}"
    echo "The Proxmox ISO is read-only. You need to:"
    echo "1. Create a separate small FAT32 partition on the USB"
    echo "2. Copy answer.toml to that partition"
    echo "3. Boot and manually specify: auto-install-cfg=/dev/disk/by-label/ANSWERFILE/answer.toml"
    echo ""
    echo "Or use the automatic method below..."

    # Use isohybrid method - add answer file to ISO
    echo -e "${GREEN}Step 2b: Using alternative method - extracting and modifying ISO...${NC}"

    WORK_DIR="/tmp/proxmox-iso-$$"
    mkdir -p "$WORK_DIR"

    echo "Extracting ISO contents (this may take a few minutes)..."
    xorriso -osirrox on -indev "$ISO_FILE" -extract / "$WORK_DIR" 2>/dev/null || {
        echo -e "${RED}Error: xorriso not installed. Installing...${NC}"
        apt-get update && apt-get install -y xorriso
        xorriso -osirrox on -indev "$ISO_FILE" -extract / "$WORK_DIR"
    }

    # Copy answer file
    echo "Copying answer file..."
    cp "proxmox-auto-install-answer.toml" "$WORK_DIR/answer.toml" 2>/dev/null || {
        echo -e "${YELLOW}Warning: answer file not found in current directory${NC}"
    }

    # Copy post-install script
    cp "proxmox-post-install.sh" "$WORK_DIR/" 2>/dev/null || true

    # Recreate ISO with answer file
    echo "Creating modified ISO..."
    MODIFIED_ISO="/tmp/proxmox-modified-$$.iso"
    xorriso -as mkisofs \
        -o "$MODIFIED_ISO" \
        -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin \
        -c boot/isolinux/boot.cat \
        -b boot/isolinux/isolinux.bin \
        -no-emul-boot -boot-load-size 4 -boot-info-table \
        -eltorito-alt-boot \
        -e boot/grub/efi.img \
        -no-emul-boot -isohybrid-gpt-basdat \
        "$WORK_DIR" 2>/dev/null || {
        echo -e "${RED}Error creating modified ISO${NC}"
        rm -rf "$WORK_DIR"
        exit 1
    }

    # Write modified ISO to USB
    echo "Writing modified ISO to USB..."
    dd if="$MODIFIED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=sync
    sync

    # Cleanup
    rm -rf "$WORK_DIR" "$MODIFIED_ISO"

    echo -e "${GREEN}Modified ISO written to USB${NC}"
    echo -e "${GREEN}Answer file included in ISO${NC}"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}USB drive preparation complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Boot parameter: auto-install-cfg=partition"
    exit 0
else
    echo -e "${RED}Error: Could not mount USB partition${NC}"
    echo "Partition info:"
    blkid "$USB_PART"
    rmdir "$MOUNT_POINT"
    exit 1
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
