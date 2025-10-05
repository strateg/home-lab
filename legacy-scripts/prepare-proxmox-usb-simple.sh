#!/bin/bash
# Proxmox VE 9 USB Preparation - Simple Method
#
# This script creates a bootable USB with answer file on a separate partition
# Works around the read-only ISO9660 limitation
#
# Usage: sudo ./prepare-proxmox-usb-simple.sh /dev/sdX path/to/proxmox.iso
#
# WARNING: This will ERASE all data on the target USB drive!

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
    exit 1
fi

USB_DEVICE="$1"
ISO_FILE="$2"

# Validate inputs
if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: $USB_DEVICE is not a valid block device${NC}"
    exit 1
fi

if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: $ISO_FILE not found${NC}"
    exit 1
fi

if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda (system disk)${NC}"
    exit 1
fi

# Confirm
echo -e "${YELLOW}WARNING: This will ERASE all data on $USB_DEVICE${NC}"
echo ""
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Unmount any mounted partitions
umount "${USB_DEVICE}"* 2>/dev/null || true

echo ""
echo -e "${GREEN}Step 1: Creating partition table...${NC}"

# Create new GPT partition table with two partitions:
# 1. Large partition for ISO (dd'd iso image)
# 2. Small FAT32 partition for answer file

# Get USB size in MB
USB_SIZE_MB=$(lsblk -b -d -n -o SIZE "$USB_DEVICE" | awk '{print int($1/1024/1024)}')
echo "USB size: ${USB_SIZE_MB}MB"

# Partition 1: ISO partition (take all but last 100MB)
ISO_PART_END=$((USB_SIZE_MB - 100))

# Clear partition table
sgdisk -Z "$USB_DEVICE" >/dev/null 2>&1 || wipefs -a "$USB_DEVICE"

echo ""
echo -e "${GREEN}Step 2: Writing Proxmox ISO to first part of USB...${NC}"

# Write ISO directly to device (creates hybrid ISO partition)
dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=sync conv=fsync
sync
sleep 2

echo ""
echo -e "${GREEN}Step 3: Creating answer file partition at end of USB...${NC}"

# Get the end sector of the ISO
ISO_END_SECTOR=$(sgdisk -E "$USB_DEVICE" 2>/dev/null || parted "$USB_DEVICE" unit s print | grep "Disk" | awk '{print $3}' | sed 's/s//')

# Create a small partition at the end for answer file (100MB)
# This won't interfere with the ISO
sgdisk -n 0:-100M:0 -t 0:0700 -c 0:"ANSWERFILE" "$USB_DEVICE" 2>/dev/null || {
    # Alternative using parted
    ANSWER_PART_START=$((USB_SIZE_MB - 100))
    parted -s "$USB_DEVICE" mkpart primary fat32 ${ANSWER_PART_START}MiB 100%
}

# Wait for kernel
partprobe "$USB_DEVICE"
sleep 2

# Find answer partition (should be last one)
ANSWER_PART=$(lsblk -ln -o NAME "$USB_DEVICE" | tail -1)
if [[ "$ANSWER_PART" == $(basename "$USB_DEVICE") ]]; then
    # Try with partition number
    ANSWER_PART="${USB_DEVICE}3"
    if [ ! -b "$ANSWER_PART" ]; then
        ANSWER_PART="${USB_DEVICE}2"
    fi
else
    ANSWER_PART="/dev/$ANSWER_PART"
fi

echo "Answer partition: $ANSWER_PART"

# Format answer partition as FAT32
echo "Creating FAT32 filesystem..."
mkfs.vfat -F 32 -n ANSWERFILE "$ANSWER_PART"
sync
sleep 1

echo ""
echo -e "${GREEN}Step 4: Copying answer file to answer partition...${NC}"

# Mount answer partition
MOUNT_POINT="/mnt/proxmox-answer-$$"
mkdir -p "$MOUNT_POINT"

if mount "$ANSWER_PART" "$MOUNT_POINT"; then
    echo -e "${GREEN}Mounted answer partition${NC}"

    # Copy answer file
    if [ -f "proxmox-auto-install-answer.toml" ]; then
        cp "proxmox-auto-install-answer.toml" "$MOUNT_POINT/answer.toml"
        echo "✓ Answer file copied"
    else
        echo -e "${YELLOW}Warning: proxmox-auto-install-answer.toml not found${NC}"
    fi

    # Copy post-install script
    if [ -f "proxmox-post-install.sh" ]; then
        cp "proxmox-post-install.sh" "$MOUNT_POINT/"
        echo "✓ Post-install script copied"
    fi

    # Create readme
    cat > "$MOUNT_POINT/README.txt" <<EOF
Proxmox VE 9 Unattended Installation USB

This USB contains:
- Proxmox VE 9 ISO (bootable)
- answer.toml (auto-install configuration)
- proxmox-post-install.sh (post-install script)

To use:
1. Boot from this USB
2. At boot menu, press 'e' to edit boot options
3. Add to kernel line:
   auto-install-cfg=/dev/disk/by-label/ANSWERFILE/answer.toml

Or let it boot normally and install manually, then:
1. Mount this partition after install
2. Run proxmox-post-install.sh

Created: $(date)
EOF

    # List files
    echo ""
    echo "Files on answer partition:"
    ls -lh "$MOUNT_POINT"

    sync
    umount "$MOUNT_POINT"
    rmdir "$MOUNT_POINT"
else
    echo -e "${RED}Error: Could not mount answer partition${NC}"
    rmdir "$MOUNT_POINT"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}USB preparation complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Your USB now contains:"
echo "  ✓ Bootable Proxmox VE 9 installer"
echo "  ✓ Answer file for unattended install"
echo "  ✓ Post-install configuration script"
echo ""
echo -e "${BLUE}To boot with auto-install:${NC}"
echo "1. Insert USB into Dell XPS L701X"
echo "2. Press F12 and select USB"
echo "3. At GRUB menu, press 'e' to edit"
echo "4. Add this to the linux line:"
echo "   ${YELLOW}auto-install-cfg=/dev/disk/by-label/ANSWERFILE/answer.toml${NC}"
echo "5. Press F10 or Ctrl+X to boot"
echo ""
echo -e "${BLUE}Alternative - Manual mode:${NC}"
echo "Boot normally, install manually, then mount ANSWERFILE partition"
echo "and run proxmox-post-install.sh for configuration"
echo ""
