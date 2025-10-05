#!/bin/bash
# Proxmox VE 9 USB Preparation - Simple DD Method
#
# This mimics balenaEtcher: write ISO as-is, then modify configs in-place
#
# Usage: sudo ./prepare-proxmox-usb-simple-dd.sh /dev/sdX path/to/proxmox.iso
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}"
   exit 1
fi

if [ "$#" -ne 2 ]; then
    echo "Usage: sudo $0 /dev/sdX path/to/proxmox.iso"
    exit 1
fi

USB_DEVICE="$1"
ISO_FILE="$2"

if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: $USB_DEVICE is not a valid block device${NC}"
    exit 1
fi

if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: $ISO_FILE not found${NC}"
    exit 1
fi

if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda${NC}"
    exit 1
fi

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

# Unmount
umount "${USB_DEVICE}"* 2>/dev/null || true

echo ""
echo -e "${GREEN}Step 1: Writing ISO to USB (exactly like balenaEtcher)...${NC}"

# Write ISO exactly as-is (this is what balenaEtcher does)
dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo -e "${GREEN}✓ ISO written (bootable like balenaEtcher)${NC}"

echo ""
echo -e "${GREEN}Step 2: Detecting partitions...${NC}"

# Force kernel to re-read
partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

echo "Partitions created:"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL

echo ""
echo -e "${GREEN}Step 3: Attempting to add answer file and modify boot configs...${NC}"

# Try to mount each partition and modify if writable
MOUNT_POINT="/tmp/usb-mount-$$"
mkdir -p "$MOUNT_POINT"

MODIFIED=0

for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ ! -b "$part" ]; then
        continue
    fi

    echo ""
    echo "Trying partition: $part"
    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")
    echo "  Filesystem: $FSTYPE"

    # Try to mount read-write
    if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
        echo -e "${GREEN}  ✓ Mounted read-write${NC}"

        # Check if writable
        if touch "$MOUNT_POINT/.test" 2>/dev/null; then
            rm "$MOUNT_POINT/.test"
            echo "  ✓ Filesystem is writable"

            # Look for GRUB config
            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)
            if [ -n "$GRUB_CFG" ]; then
                echo "  ✓ Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}"

                # Backup
                cp "$GRUB_CFG" "$GRUB_CFG.backup"

                # Modify: add graphics params and auto-install to first menuentry
                sed -i '/^menuentry/,/^}/s|linux .*|& video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition|' "$GRUB_CFG"

                # Set shorter timeout
                if grep -q "^set timeout=" "$GRUB_CFG"; then
                    sed -i 's/^set timeout=.*/set timeout=5/' "$GRUB_CFG"
                else
                    sed -i '1i set timeout=5' "$GRUB_CFG"
                fi

                echo "  ✓ Modified GRUB config (added graphics params + auto-install)"
                MODIFIED=1
            fi

            # Copy answer file
            if [ -f "proxmox-auto-install-answer.toml" ]; then
                cp "proxmox-auto-install-answer.toml" "$MOUNT_POINT/answer.toml"
                echo "  ✓ Copied answer.toml"
                MODIFIED=1
            fi

            # Copy post-install script
            if [ -f "proxmox-post-install.sh" ]; then
                cp "proxmox-post-install.sh" "$MOUNT_POINT/"
                echo "  ✓ Copied post-install script"
            fi

        else
            echo -e "${YELLOW}  ⚠ Read-only filesystem${NC}"
        fi

        sync
        umount "$MOUNT_POINT"
    else
        echo "  ⚠ Could not mount"
    fi
done

rmdir "$MOUNT_POINT"

if [ $MODIFIED -eq 0 ]; then
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  USB is bootable but NOT modified${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo -e "${YELLOW}The USB filesystem is read-only (ISO9660).${NC}"
    echo "This is normal for Proxmox ISOs."
    echo ""
    echo "The USB will boot, but you need to:"
    echo ""
    echo -e "${GREEN}Option 1: Manual boot parameter (recommended)${NC}"
    echo "  1. Boot from USB"
    echo "  2. At GRUB menu, press 'e' to edit"
    echo "  3. Find the line starting with 'linux' or 'linuxefi'"
    echo "  4. Add to the END of that line:"
    echo -e "${BLUE}     video=vesafb:ywrap,mtrr vga=791 nomodeset${NC}"
    echo "  5. Press Ctrl+X or F10 to boot"
    echo ""
    echo -e "${GREEN}Option 2: Install normally, use external display${NC}"
    echo "  - Just the graphics params will enable your Mini DisplayPort"
    echo "  - Install manually (no auto-install)"
    echo ""
else
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  SUCCESS! USB is bootable and modified${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
fi

echo -e "${BLUE}Important: Dell XPS L701X with external display${NC}"
echo ""
echo "BEFORE booting:"
echo "  1. Connect external monitor to Mini DisplayPort"
echo "  2. Power ON monitor"
echo "  3. Insert USB into laptop"
echo ""
echo "BIOS settings (F2):"
echo "  - Boot Mode: UEFI"
echo "  - Secure Boot: DISABLED"
echo "  - Boot Order: USB first"
echo ""
echo "Boot (F12):"
echo "  - Select: 'UEFI: USB...' option"
echo "  - NOT 'USB Storage Device'"
echo ""
echo -e "${GREEN}The USB has the exact same boot structure as balenaEtcher!${NC}"
echo ""
