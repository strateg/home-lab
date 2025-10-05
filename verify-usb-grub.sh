#!/bin/bash
# Verify USB GRUB Configuration
#
# This checks what's actually on the USB after modification
#
# Usage: sudo ./verify-usb-grub.sh /dev/sdX

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: Run as root${NC}"
   exit 1
fi

if [ "$#" -ne 1 ]; then
    echo "Usage: sudo $0 /dev/sdX"
    exit 1
fi

USB_DEVICE="$1"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  USB GRUB Configuration Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

MOUNT_POINT="/tmp/usb-check-$$"
mkdir -p "$MOUNT_POINT"

echo "Scanning partitions..."
echo ""

for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    echo "Partition: $part ($FSTYPE)"

    if [ "$FSTYPE" = "vfat" ] || [ "$FSTYPE" = "iso9660" ]; then
        if mount -o ro "$part" "$MOUNT_POINT" 2>/dev/null; then
            # Look for GRUB
            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

            if [ -n "$GRUB_CFG" ]; then
                echo -e "${GREEN}  ✓ Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}${NC}"
                echo ""
                echo "  --- GRUB Configuration ---"
                cat "$GRUB_CFG"
                echo "  --- End of GRUB ---"
                echo ""

                # Check for our modifications
                if grep -q "auto-install-cfg=partition" "$GRUB_CFG"; then
                    echo -e "${GREEN}  ✓ Auto-install parameter found${NC}"
                else
                    echo -e "${RED}  ✗ Auto-install parameter NOT found${NC}"
                fi

                if grep -q "video=vesafb" "$GRUB_CFG"; then
                    echo -e "${GREEN}  ✓ Graphics parameters found${NC}"
                else
                    echo -e "${RED}  ✗ Graphics parameters NOT found${NC}"
                fi

                if grep -q "set timeout=3" "$GRUB_CFG"; then
                    echo -e "${GREEN}  ✓ Timeout set to 3${NC}"
                else
                    echo -e "${YELLOW}  ! Timeout not set to 3${NC}"
                fi
            fi

            # Check for answer file
            if [ -f "$MOUNT_POINT/answer.toml" ]; then
                echo -e "${GREEN}  ✓ answer.toml found on partition${NC}"
                echo "    Location: /answer.toml"
            else
                echo -e "${RED}  ✗ answer.toml NOT found${NC}"
            fi

            umount "$MOUNT_POINT"
            echo ""
        fi
    fi
done

rmdir "$MOUNT_POINT"

echo -e "${BLUE}========================================${NC}"
echo ""
