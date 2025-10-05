#!/bin/bash
# Proxmox VE 9 USB - Direct On-Disk Patching
#
# Strategy:
# 1. Write ISO with dd (creates bootable USB - guaranteed to work)
# 2. Find GRUB config file location on the USB
# 3. Patch it directly on the block device (no rebuilding!)
#
# Usage: sudo ./prepare-proxmox-usb-direct-patch.sh /dev/sdX path/to/proxmox.iso

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

if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: Invalid device${NC}"
    exit 1
fi

if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: ISO not found${NC}"
    exit 1
fi

if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}WARNING: This will ERASE $USB_DEVICE${NC}"
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes': " confirm
[ "$confirm" != "yes" ] && exit 0

umount "${USB_DEVICE}"* 2>/dev/null || true

echo ""
echo -e "${GREEN}[1/4] Writing ISO to USB with dd...${NC}"
echo "This creates bootable USB (like balenaEtcher - guaranteed to work)"
echo ""

dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo ""
echo -e "${GREEN}✓ Bootable USB created${NC}"

echo ""
echo -e "${GREEN}[2/4] Mounting USB to find GRUB config...${NC}"

partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL

MOUNT_POINT="/tmp/usb-$$"
mkdir -p "$MOUNT_POINT"

GRUB_FOUND=""
GRUB_PATH=""

# Try to mount the ISO9660 partition read-only to find GRUB location
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "iso9660" ] || [ "$FSTYPE" = "vfat" ]; then
        echo "Checking $part ($FSTYPE)..."

        if mount -o ro "$part" "$MOUNT_POINT" 2>/dev/null; then
            # Find GRUB config
            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

            if [ -n "$GRUB_CFG" ]; then
                GRUB_FOUND="$GRUB_CFG"
                GRUB_PATH="${GRUB_CFG#$MOUNT_POINT/}"
                echo -e "${GREEN}✓ Found GRUB at: $GRUB_PATH${NC}"

                # Read current GRUB content
                cat "$GRUB_CFG" > /tmp/grub-original.cfg

                umount "$MOUNT_POINT"
                break
            fi

            umount "$MOUNT_POINT"
        fi
    fi
done

if [ -z "$GRUB_FOUND" ]; then
    echo -e "${RED}Error: Could not find GRUB config on USB${NC}"
    rmdir "$MOUNT_POINT"
    exit 1
fi

echo ""
echo -e "${GREEN}[3/4] Creating modified GRUB config...${NC}"

# Create new GRUB with our modifications
GRUB_NEW="/tmp/grub-new.cfg"

cat > "$GRUB_NEW" <<'GRUBEOF'
set default=0
set timeout=3
insmod all_video
insmod gfxterm
loadfont unicode
terminal_output gfxterm
set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

menuentry 'Proxmox - Auto Install + External Display' {
    linux /boot/linux26 auto-install-cfg=partition ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

menuentry 'Proxmox - Manual Install + External Display' {
    linux /boot/linux26 ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

menuentry 'Proxmox - Standard Install' {
    linux /boot/linux26 ro quiet
    initrd /boot/initrd.img
}
GRUBEOF

# Get original and new file sizes
ORIGINAL_SIZE=$(stat -c%s /tmp/grub-original.cfg)
NEW_SIZE=$(stat -c%s "$GRUB_NEW")

echo "Original GRUB size: $ORIGINAL_SIZE bytes"
echo "New GRUB size: $NEW_SIZE bytes"

# Pad new file to match original size if needed (ISO9660 has fixed sizes)
if [ $NEW_SIZE -lt $ORIGINAL_SIZE ]; then
    # Pad with spaces/newlines
    while [ $(stat -c%s "$GRUB_NEW") -lt $ORIGINAL_SIZE ]; do
        echo "" >> "$GRUB_NEW"
    done

    # Trim to exact size
    truncate -s $ORIGINAL_SIZE "$GRUB_NEW"
    echo "✓ Padded to original size"
elif [ $NEW_SIZE -gt $ORIGINAL_SIZE ]; then
    echo -e "${YELLOW}Warning: New GRUB config is larger than original${NC}"
    echo "Truncating to fit..."
    truncate -s $ORIGINAL_SIZE "$GRUB_NEW"
fi

echo ""
echo -e "${GREEN}[4/4] Patching GRUB directly on USB...${NC}"

# Now we need to find the exact byte offset of grub.cfg on the USB device
# and overwrite it directly

# Method: Use isoinfo to find the file's location
if command -v isoinfo &> /dev/null; then
    echo "Using isoinfo to find file offset..."

    # Get file info
    FILE_INFO=$(isoinfo -i "$USB_DEVICE" -l -find -name grub.cfg 2>/dev/null | grep "grub.cfg" | head -1)

    if [ -n "$FILE_INFO" ]; then
        # Extract block number and size
        # isoinfo output format varies, so we'll use a different approach
        echo "File found in ISO structure"
    fi
fi

# Alternative method: Mount and use debugfs or direct block finding
# For ISO9660, we can search for the file content and replace it

echo "Searching for GRUB config pattern on disk..."

# Create a unique pattern from original GRUB to find its location
SEARCH_PATTERN=$(head -c 50 /tmp/grub-original.cfg | tr -d '\n' | head -c 40)

# Search for this pattern on the USB device
OFFSET=$(grep -obUaP "$SEARCH_PATTERN" "$USB_DEVICE" | head -1 | cut -d: -f1)

if [ -n "$OFFSET" ]; then
    echo -e "${GREEN}✓ Found GRUB at byte offset: $OFFSET${NC}"

    echo "Writing new GRUB config to USB..."
    dd if="$GRUB_NEW" of="$USB_DEVICE" bs=1 seek=$OFFSET conv=notrunc 2>/dev/null

    sync

    echo -e "${GREEN}✓ GRUB config patched on USB!${NC}"
    PATCHED=1
else
    echo -e "${YELLOW}Warning: Could not find exact GRUB location for direct patching${NC}"
    echo ""
    echo "Alternative: Remount and try filesystem-level modification..."

    # Try to remount with write permissions using special options
    for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
        [ ! -b "$part" ] && continue

        FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

        if [ "$FSTYPE" = "iso9660" ]; then
            # Try mount with write option (usually fails for iso9660)
            if mount -o rw,unhide "$part" "$MOUNT_POINT" 2>/dev/null; then
                echo "Mounted with write access!"

                GRUB_ON_MOUNT=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

                if [ -n "$GRUB_ON_MOUNT" ]; then
                    if cp "$GRUB_NEW" "$GRUB_ON_MOUNT" 2>/dev/null; then
                        echo -e "${GREEN}✓ GRUB replaced via mount${NC}"
                        PATCHED=1
                        sync
                    fi
                fi

                umount "$MOUNT_POINT"

                [ "$PATCHED" = "1" ] && break
            fi
        fi
    done
fi

rmdir "$MOUNT_POINT"
rm -f /tmp/grub-original.cfg "$GRUB_NEW"

echo ""

if [ "$PATCHED" = "1" ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  SUCCESS - GRUB PATCHED ON USB!      ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    echo ""
    echo "✓ USB is bootable (dd method - works)"
    echo "✓ GRUB modified directly on USB"
    echo "✓ Graphics parameters added for external display"
    echo "✓ Auto-install parameter added"
    echo ""
    echo "Boot and test:"
    echo "  1. Connect external monitor"
    echo "  2. Boot from USB"
    echo "  3. Should see menu on external display"
    echo "  4. Auto-install should start"
else
    echo -e "${YELLOW}╔═══════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  USB BOOTABLE - GRUB NOT PATCHED      ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════╝${NC}"
    echo ""
    echo "ISO9660 is read-only and couldn't be patched."
    echo ""
    echo "USB will boot, but you'll need to provide"
    echo "boot parameters another way."
fi

echo ""
