#!/bin/bash
# Отключить UUID-защиту на существующем Proxmox USB
# Позволяет принудительную переустановку без проверки UUID
#
# Usage: sudo ./disable-uuid-protection.sh /dev/sdX

set -euo pipefail

USB_DEVICE="${1:-}"

if [ -z "$USB_DEVICE" ]; then
    echo "Usage: sudo $0 /dev/sdX"
    echo "Example: sudo $0 /dev/sdb"
    exit 1
fi

if [ $EUID -ne 0 ]; then
    echo "ERROR: This script must be run as root"
    exit 1
fi

if [ ! -b "$USB_DEVICE" ]; then
    echo "ERROR: $USB_DEVICE is not a block device"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Disable UUID Protection on Proxmox USB                ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "USB Device: $USB_DEVICE"
echo ""
echo "WARNING: This will modify GRUB configuration on USB"
echo "         to FORCE reinstallation (no UUID check)"
echo ""
read -p "Continue? (yes/no): " response

if [ "$response" != "yes" ]; then
    echo "Aborted"
    exit 0
fi

# Unmount any mounted partitions
umount "${USB_DEVICE}"* 2>/dev/null || true
sync
sleep 2

# Find and mount EFI partition
MOUNT_POINT="/tmp/usb-disable-uuid-$$"
mkdir -p "$MOUNT_POINT"
MOUNTED=0

for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ]; then
        if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            GRUB_CFG="$MOUNT_POINT/EFI/BOOT/grub.cfg"

            if [ -f "$GRUB_CFG" ]; then
                echo "✓ Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}"

                # Check if this is UUID wrapper
                if grep -q "usb_uuid=" "$GRUB_CFG" 2>/dev/null; then
                    echo "✓ Found UUID protection wrapper"

                    # Check if original installer menu exists
                    GRUB_INSTALL="$MOUNT_POINT/EFI/BOOT/grub-install.cfg"
                    if [ -f "$GRUB_INSTALL" ]; then
                        echo "✓ Found original installer menu"

                        # Backup current grub.cfg
                        cp "$GRUB_CFG" "$GRUB_CFG.uuid-backup"
                        echo "✓ Backed up: grub.cfg.uuid-backup"

                        # Replace grub.cfg with installer menu (bypass UUID check)
                        cp "$GRUB_INSTALL" "$GRUB_CFG"
                        echo "✓ Restored original installer menu (no UUID check)"

                        # Optionally: modify timeout for immediate auto-install
                        sed -i 's/set timeout=.*/set timeout=5/' "$GRUB_CFG" 2>/dev/null || true

                        sync
                        MOUNTED=1

                        echo ""
                        echo "╔══════════════════════════════════════════════════════════╗"
                        echo "║   SUCCESS: UUID Protection Disabled                     ║"
                        echo "╚══════════════════════════════════════════════════════════╝"
                        echo ""
                        echo "Changes:"
                        echo "  • grub.cfg replaced with installer menu"
                        echo "  • UUID check completely bypassed"
                        echo "  • Auto-install will run on EVERY boot"
                        echo ""
                        echo "⚠️  WARNING: Remove USB after installation!"
                        echo "    This USB will now reinstall Proxmox every time"
                        echo ""
                        echo "To restore UUID protection:"
                        echo "  cp $MOUNT_POINT/EFI/BOOT/grub.cfg.uuid-backup \\"
                        echo "     $MOUNT_POINT/EFI/BOOT/grub.cfg"
                        echo ""

                        umount "$MOUNT_POINT"
                        rmdir "$MOUNT_POINT"
                        exit 0
                    else
                        echo "ERROR: Original installer menu not found (grub-install.cfg)"
                        echo "       This USB may not have UUID protection"
                        umount "$MOUNT_POINT"
                    fi
                else
                    echo "INFO: No UUID protection detected on this USB"
                    echo "      (grub.cfg does not contain usb_uuid)"
                    umount "$MOUNT_POINT"
                fi
            else
                umount "$MOUNT_POINT"
            fi
        fi
    fi
done

rmdir "$MOUNT_POINT" 2>/dev/null || true

if [ $MOUNTED -eq 0 ]; then
    echo ""
    echo "ERROR: Could not disable UUID protection"
    echo "Possible reasons:"
    echo "  • EFI partition not found on USB"
    echo "  • grub.cfg not found"
    echo "  • USB does not have UUID protection"
    echo "  • grub-install.cfg backup missing"
    exit 1
fi
