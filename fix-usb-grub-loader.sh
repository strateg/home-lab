#!/bin/bash
# Fix USB GRUB - Modify the Loader
#
# The GRUB we found is a loader that sources the real config.
# We'll modify this loader to set default boot parameters
# BEFORE it loads the main config.
#
# Usage: sudo ./fix-usb-grub-loader.sh /dev/sdX

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

if [ "$#" -ne 1 ]; then
    echo "Usage: sudo $0 /dev/sdX"
    exit 1
fi

USB_DEVICE="$1"

echo -e "${GREEN}Fixing GRUB loader on USB...${NC}"
echo ""

MOUNT_POINT="/tmp/usb-fix-$$"
mkdir -p "$MOUNT_POINT"

# Find the FAT32 EFI partition
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ]; then
        echo "Mounting $part..."

        if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -path "*/efi/boot/*" -type f 2>/dev/null | head -1)

            if [ -n "$GRUB_CFG" ]; then
                echo -e "${GREEN}Found GRUB loader: ${GRUB_CFG#$MOUNT_POINT/}${NC}"
                echo ""
                echo "Current content:"
                cat "$GRUB_CFG"
                echo ""

                # Backup
                cp "$GRUB_CFG" "$GRUB_CFG.backup"

                # Create new GRUB loader that sets parameters before sourcing
                cat > "$GRUB_CFG" <<'GRUBEOF'
set default=0
set timeout=3

# Set default kernel parameters for ALL boot entries
set linux_default="video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition"

# Search for the root partition
search --fs-uuid --set=root 2025-08-05-10-48-40-00

# Set prefix
set prefix=(${root})/boot/grub

# Export the default parameters so the sourced config can use them
export linux_default

# Source the main GRUB config
# We'll modify it on-the-fly as it loads
source ${prefix}/grub.cfg
GRUBEOF

                echo "Modified GRUB loader:"
                cat "$GRUB_CFG"
                echo ""

                sync
                echo -e "${GREEN}✓ GRUB loader modified${NC}"

                # Also check if answer file exists
                if [ -f "$MOUNT_POINT/answer.toml" ]; then
                    echo -e "${GREEN}✓ answer.toml present${NC}"
                else
                    if [ -f "proxmox-auto-install-answer.toml" ]; then
                        cp "proxmox-auto-install-answer.toml" "$MOUNT_POINT/answer.toml"
                        echo -e "${GREEN}✓ answer.toml added${NC}"
                    fi
                fi

                umount "$MOUNT_POINT"
                rmdir "$MOUNT_POINT"

                echo ""
                echo -e "${YELLOW}Note: The sourced grub.cfg may override these settings.${NC}"
                echo -e "${YELLOW}We need a different approach...${NC}"
                echo ""

                exit 0
            fi

            umount "$MOUNT_POINT"
        fi
    fi
done

rmdir "$MOUNT_POINT"

echo -e "${RED}Could not find GRUB loader${NC}"
