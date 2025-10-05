#!/bin/bash
# Fix USB GRUB - Replace Loader with Complete Config
#
# Instead of sourcing the read-only grub.cfg, we replace
# the loader with a complete GRUB configuration
#
# Usage: sudo ./fix-usb-grub-complete.sh /dev/sdX

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

echo -e "${GREEN}Replacing GRUB loader with complete config...${NC}"
echo ""

MOUNT_POINT="/tmp/usb-fix-$$"
mkdir -p "$MOUNT_POINT"

FIXED=0

# Find the FAT32 EFI partition
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ]; then
        echo "Mounting $part (writable)..."

        if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -path "*/efi/boot/*" -type f 2>/dev/null | head -1)

            if [ -n "$GRUB_CFG" ]; then
                echo -e "${GREEN}Found GRUB loader: ${GRUB_CFG#$MOUNT_POINT/}${NC}"
                echo ""

                # Backup original
                cp "$GRUB_CFG" "$GRUB_CFG.backup-$(date +%s)"

                # Get the root partition UUID
                ROOT_UUID=$(grep "search --fs-uuid" "$GRUB_CFG" | grep -o '[0-9-]\{20,\}' || echo "")

                if [ -z "$ROOT_UUID" ]; then
                    ROOT_UUID="2025-08-05-10-48-40-00"
                fi

                echo "Root partition UUID: $ROOT_UUID"

                # Create COMPLETE GRUB config (don't source, define everything here)
                cat > "$GRUB_CFG" <<GRUBEOF
set default=0
set timeout=3

# Load modules
insmod all_video
insmod gfxterm
insmod png
loadfont unicode

# Graphics setup
terminal_output gfxterm
set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

# Find root partition
search --fs-uuid --set=root $ROOT_UUID

menuentry 'Proxmox VE - Auto Install (External Display)' {
    linux /boot/linux26 auto-install-cfg=partition ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Manual Install (External Display)' {
    linux /boot/linux26 ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Standard Install' {
    linux /boot/linux26 ro quiet
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Debug Mode' {
    linux /boot/linux26 ro debug
    initrd /boot/initrd.img
}
GRUBEOF

                echo ""
                echo "New GRUB config:"
                cat "$GRUB_CFG"
                echo ""

                # Verify answer file
                if [ ! -f "$MOUNT_POINT/answer.toml" ] && [ -f "proxmox-auto-install-answer.toml" ]; then
                    cp "proxmox-auto-install-answer.toml" "$MOUNT_POINT/answer.toml"
                    echo -e "${GREEN}✓ answer.toml added${NC}"
                fi

                sync
                FIXED=1

                echo -e "${GREEN}✓ Complete GRUB config created${NC}"

                umount "$MOUNT_POINT"
                break
            fi

            umount "$MOUNT_POINT"
        fi
    fi
done

rmdir "$MOUNT_POINT"

if [ $FIXED -eq 1 ]; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  GRUB FIXED - READY FOR AUTO-INSTALL  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "Changes made:"
    echo "  ✓ Replaced loader with complete GRUB config"
    echo "  ✓ Auto-install parameter added"
    echo "  ✓ Graphics parameters added"
    echo "  ✓ Timeout: 3 seconds"
    echo "  ✓ Default: Auto-install entry"
    echo ""
    echo "Boot the USB now:"
    echo "  1. Connect external monitor"
    echo "  2. Boot from USB (F12 → UEFI: USB...)"
    echo "  3. Wait 3 seconds or press Enter"
    echo "  4. Auto-install should start!"
    echo ""
else
    echo -e "${RED}Could not fix GRUB${NC}"
fi
