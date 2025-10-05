#!/bin/bash
# Proxmox VE 9 USB Creator - SIMPLE APPROACH
#
# Strategy: Keep it simple
# 1. Write ISO with dd (guaranteed bootable)
# 2. PREPEND to GRUB (don't replace - keep original)
# 3. Add answer file
# That's it!
#
# Usage: sudo ./create-proxmox-usb-simple.sh /dev/sdX path/to/proxmox.iso

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: Run as root${NC}"
   exit 1
fi

if [ "$#" -ne 2 ]; then
    echo "Usage: sudo $0 /dev/sdX path/to/proxmox.iso"
    exit 1
fi

USB_DEVICE="$1"
ISO_FILE="$2"

if [ ! -b "$USB_DEVICE" ] || [ ! -f "$ISO_FILE" ] || [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Invalid device or ISO${NC}"
    exit 1
fi

if [ ! -f "proxmox-auto-install-answer.toml" ]; then
    echo -e "${RED}Error: proxmox-auto-install-answer.toml not found${NC}"
    exit 1
fi

echo -e "${YELLOW}WARNING: This will ERASE $USB_DEVICE${NC}"
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes': " confirm
[ "$confirm" != "yes" ] && exit 0

umount "${USB_DEVICE}"* 2>/dev/null || true

echo ""
echo -e "${GREEN}[1/3] Writing ISO with dd...${NC}"

dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync
sync
sleep 3

echo -e "${GREEN}✓ Bootable USB created${NC}"

echo ""
echo -e "${GREEN}[2/3] Modifying GRUB...${NC}"

partprobe "$USB_DEVICE" 2>/dev/null || true
sleep 3

MOUNT_POINT="/tmp/usb-$$"
mkdir -p "$MOUNT_POINT"
MODIFIED=0

for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue
    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ] && mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
        GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

        if [ -n "$GRUB_CFG" ]; then
            echo "Found GRUB: ${GRUB_CFG#$MOUNT_POINT/}"

            # Save original
            cp "$GRUB_CFG" "$GRUB_CFG.original"

            # Read original content
            ORIGINAL=$(cat "$GRUB_CFG")

            # Extract UUID for root search
            UUID=$(echo "$ORIGINAL" | grep "search --fs-uuid" | grep -o '[0-9-]\{10,\}' | head -1)
            [ -z "$UUID" ] && UUID="2025-08-05-10-48-40-00"

            # Create new GRUB: our menuentry FIRST, then original content
            cat > "$GRUB_CFG" <<GRUBEOF
# Auto-install entry (added by script)
set default=0
set timeout=3

search --fs-uuid --set=root $UUID

menuentry 'Proxmox - Auto Install (External Display)' {
    linux /boot/linux26 auto-install-cfg=partition ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

# Original GRUB configuration below:
$ORIGINAL
GRUBEOF

            echo -e "${GREEN}✓ GRUB modified (prepended auto-install entry)${NC}"

            # Add answer file
            cp "proxmox-auto-install-answer.toml" "$MOUNT_POINT/answer.toml"
            echo -e "${GREEN}✓ Answer file added${NC}"

            [ -f "proxmox-post-install.sh" ] && cp "proxmox-post-install.sh" "$MOUNT_POINT/"

            sync
            MODIFIED=1
        fi

        umount "$MOUNT_POINT"
        [ $MODIFIED -eq 1 ] && break
    fi
done

rmdir "$MOUNT_POINT"

echo ""
echo -e "${GREEN}[3/3] Verification...${NC}"

if [ $MODIFIED -eq 1 ]; then
    echo -e "${GREEN}✓ USB ready for auto-install${NC}"
    echo ""
    echo "Boot steps:"
    echo "  1. Connect external monitor to Mini DisplayPort"
    echo "  2. Boot from USB (F12 → UEFI: USB...)"
    echo "  3. Wait 3 sec or press Enter"
    echo "  4. Auto-install starts!"
else
    echo -e "${RED}✗ Could not modify GRUB${NC}"
    echo "USB is bootable but not configured for auto-install"
fi

echo ""
