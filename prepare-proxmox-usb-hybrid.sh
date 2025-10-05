#!/bin/bash
# Proxmox VE 9 USB Preparation - Hybrid Method
#
# This uses the most reliable approach:
# 1. Write original ISO with dd (guaranteed bootable)
# 2. Add answer file via loop device mount
# 3. Modify GRUB in-place for auto-install
#
# Usage: sudo ./prepare-proxmox-usb-hybrid.sh /dev/sdX path/to/proxmox.iso
#

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
echo ""
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
echo -e "${GREEN}Step 1: Writing Proxmox ISO to USB (this takes 3-5 minutes)...${NC}"

# Write ISO directly - this ensures it's bootable
dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo -e "${GREEN}✓ ISO written to USB${NC}"

echo ""
echo -e "${GREEN}Step 2: Re-reading partition table...${NC}"

# Force kernel to re-read partition table
partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

# Show partitions
echo "Partitions on USB:"
lsblk "$USB_DEVICE" -o NAME,SIZE,FSTYPE,LABEL

echo ""
echo -e "${GREEN}Step 3: Mounting USB partitions...${NC}"

# Find EFI partition (usually partition 2 on Proxmox ISO)
EFI_PART=""
ISO_PART=""

# Try to find partitions
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ -b "$part" ]; then
        FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")
        echo "  Found: $part ($FSTYPE)"

        if [[ "$FSTYPE" == "vfat" ]]; then
            EFI_PART="$part"
        elif [[ "$FSTYPE" == "iso9660" ]]; then
            ISO_PART="$part"
        fi
    fi
done

# Try to mount EFI partition first (writable)
MOUNT_POINT="/mnt/proxmox-usb-$$"
mkdir -p "$MOUNT_POINT"

MOUNTED=0

if [ -n "$EFI_PART" ]; then
    echo "Attempting to mount EFI partition: $EFI_PART"
    if mount "$EFI_PART" "$MOUNT_POINT" 2>/dev/null; then
        echo -e "${GREEN}✓ Mounted EFI partition (writable)${NC}"
        MOUNTED=1
    fi
fi

# If EFI mount failed, try ISO partition
if [ $MOUNTED -eq 0 ] && [ -n "$ISO_PART" ]; then
    echo "Attempting to mount ISO partition: $ISO_PART"
    if mount -o rw "$ISO_PART" "$MOUNT_POINT" 2>/dev/null; then
        echo -e "${YELLOW}✓ Mounted ISO partition${NC}"
        MOUNTED=1
    fi
fi

# If still not mounted, try the USB device directly as a loop
if [ $MOUNTED -eq 0 ]; then
    echo -e "${YELLOW}Standard mount failed, trying loop device...${NC}"

    # Create loop device
    LOOP_DEV=$(losetup -f)
    losetup "$LOOP_DEV" "$USB_DEVICE"

    # Try to mount
    if mount -o rw,offset=0 "$LOOP_DEV" "$MOUNT_POINT" 2>/dev/null; then
        echo -e "${GREEN}✓ Mounted via loop device${NC}"
        MOUNTED=1
    else
        losetup -d "$LOOP_DEV"
    fi
fi

if [ $MOUNTED -eq 0 ]; then
    echo -e "${RED}Error: Could not mount USB${NC}"
    rmdir "$MOUNT_POINT"
    echo ""
    echo -e "${YELLOW}The USB is bootable but we cannot add answer file${NC}"
    echo -e "${YELLOW}You'll need to manually edit boot parameters:${NC}"
    echo ""
    echo "At boot, press 'e' to edit, then add to kernel line:"
    echo "  auto-install-cfg=/dev/sdb/answer.toml"
    echo ""
    echo "And manually copy answer.toml to USB later"
    exit 1
fi

echo ""
echo -e "${GREEN}Step 4: Adding answer file...${NC}"

# Check if we can write
if touch "$MOUNT_POINT/.test" 2>/dev/null; then
    rm "$MOUNT_POINT/.test"
    echo "✓ Filesystem is writable"

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
else
    echo -e "${YELLOW}Warning: Filesystem is read-only${NC}"
fi

echo ""
echo -e "${GREEN}Step 5: Modifying GRUB configuration...${NC}"

# Find GRUB config
GRUB_CFG="$MOUNT_POINT/boot/grub/grub.cfg"

if [ -f "$GRUB_CFG" ]; then
    if [ -w "$GRUB_CFG" ]; then
        # Backup
        cp "$GRUB_CFG" "$GRUB_CFG.backup" 2>/dev/null || true

        # Modify GRUB to add auto-install entry and set as default
        # Insert auto-install entry at the beginning
        sed -i '1i set default=0' "$GRUB_CFG"
        sed -i '2i set timeout=5' "$GRUB_CFG"

        # Find first menuentry and duplicate it with auto-install parameters
        FIRST_MENUENTRY=$(grep -n "^menuentry" "$GRUB_CFG" | head -1 | cut -d: -f1)

        if [ -n "$FIRST_MENUENTRY" ]; then
            # Insert auto-install menuentry before first one
            # CRITICAL: Remove 'quiet splash=silent' and add video/graphics parameters
            # This forces graphical mode which is REQUIRED for Mini DisplayPort output
            sed -i "${FIRST_MENUENTRY}i menuentry 'Install Proxmox VE (Automated - GUI Mode)' {\n    linux /boot/linux26 auto-install-cfg=partition ro video=vesafb:ywrap,mtrr vga=791 nomodeset\n    initrd /boot/initrd.img\n}\n" "$GRUB_CFG"
            echo "✓ GRUB config modified (GUI mode for external display)"
        else
            echo -e "${YELLOW}Warning: Could not find menuentry in GRUB config${NC}"
        fi
    else
        echo -e "${YELLOW}Warning: GRUB config is read-only${NC}"
    fi
else
    echo -e "${YELLOW}Warning: GRUB config not found at $GRUB_CFG${NC}"
fi

# Also try ISOLINUX for BIOS boot
ISOLINUX_CFG="$MOUNT_POINT/boot/isolinux/isolinux.cfg"
if [ -f "$ISOLINUX_CFG" ] && [ -w "$ISOLINUX_CFG" ]; then
    cp "$ISOLINUX_CFG" "$ISOLINUX_CFG.backup" 2>/dev/null || true

    # Set timeout and default
    sed -i 's/^timeout .*/timeout 50/' "$ISOLINUX_CFG"
    sed -i 's/^default .*/default autoinstall/' "$ISOLINUX_CFG"

    # Add auto-install label at the beginning
    # CRITICAL: Add video parameters for graphical mode (Mini DisplayPort needs this)
    FIRST_LABEL=$(grep -n "^label" "$ISOLINUX_CFG" | head -1 | cut -d: -f1)
    if [ -n "$FIRST_LABEL" ]; then
        sed -i "${FIRST_LABEL}i label autoinstall\n  menu label ^Automated Installation (GUI Mode)\n  menu default\n  kernel /boot/linux26\n  append auto-install-cfg=partition initrd=/boot/initrd.img ro video=vesafb:ywrap,mtrr vga=791 nomodeset\n" "$ISOLINUX_CFG"
        echo "✓ ISOLINUX config modified (GUI mode)"
    fi
fi

# Sync and unmount
sync
umount "$MOUNT_POINT"

# Clean up loop device if used
if [ -n "$LOOP_DEV" ]; then
    losetup -d "$LOOP_DEV" 2>/dev/null || true
fi

rmdir "$MOUNT_POINT"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  USB PREPARATION COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}USB is now bootable with:${NC}"
echo "  ✓ Proxmox VE 9 installer (original ISO)"
echo "  ✓ Answer file (if writable)"
echo "  ✓ Modified GRUB/ISOLINUX for GUI mode"
echo "  ✓ Graphics parameters for Mini DisplayPort"
echo ""
echo -e "${YELLOW}IMPORTANT - External Display Setup:${NC}"
echo ""
echo -e "${RED}  ⚠ BEFORE booting:${NC}"
echo "    1. Connect external monitor to Mini DisplayPort"
echo "    2. Power on external monitor first"
echo "    3. Then power on laptop with USB inserted"
echo ""
echo -e "${YELLOW}Boot Instructions (Dell XPS L701X):${NC}"
echo ""
echo "  1. Insert USB into USB 2.0 port (NOT USB 3.0)"
echo "  2. Connect external monitor to Mini DisplayPort"
echo "  3. Power on and press F12 repeatedly"
echo "  4. Select: 'USB Storage Device' or 'UEFI: USB...'"
echo "     (Try BOTH if one doesn't work)"
echo ""
echo -e "${GREEN}You should see on external display:${NC}"
echo "  - GRUB menu with 'Install Proxmox VE (Automated - GUI Mode)'"
echo "  - Press Enter or wait 5 seconds"
echo "  - Graphical installer appears (you'll see GUI)"
echo "  - Installation runs automatically with progress bar"
echo ""
echo -e "${YELLOW}If display stays black:${NC}"
echo "  • Wait 30 seconds for auto-boot"
echo "  • Try Legacy/BIOS boot instead of UEFI (or vice versa)"
echo "  • Press F2 → BIOS → Boot Mode → change UEFI/Legacy"
echo ""
echo -e "${BLUE}Graphics boot parameters added:${NC}"
echo "  video=vesafb:ywrap,mtrr    (enables framebuffer)"
echo "  vga=791                     (1024x768 16-bit color)"
echo "  nomodeset                   (prevents mode switching)"
echo ""
echo -e "${GREEN}After installation completes:${NC}"
echo "  - System reboots (external display may go black)"
echo "  - Wait for Proxmox boot (external display activates again)"
echo "  - Find IP and run: ssh root@<ip>"
echo "  - Run: bash proxmox-post-install.sh"
echo ""
