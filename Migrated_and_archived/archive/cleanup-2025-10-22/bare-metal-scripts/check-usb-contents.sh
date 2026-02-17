#!/bin/bash
#
# Check USB contents after creation
#

set -e

echo "=========================================="
echo "USB Contents Check"
echo "=========================================="
echo ""

MOUNT_POINT="/mnt/usb-check-$$"
sudo mkdir -p "$MOUNT_POINT"

echo "1. Checking EFI partition (/dev/sdc2)..."
echo ""

sudo mount /dev/sdc2 "$MOUNT_POINT"

echo "EFI/BOOT directory contents:"
ls -lh "$MOUNT_POINT/EFI/BOOT/"
echo ""

echo "Checking GRUB config (first 30 lines):"
echo "---"
head -30 "$MOUNT_POINT/EFI/BOOT/grub.cfg"
echo "---"
echo ""

echo "Searching for UUID wrapper..."
if grep -q "usb_uuid=" "$MOUNT_POINT/EFI/BOOT/grub.cfg" 2>/dev/null; then
    echo "✓ UUID wrapper FOUND in grub.cfg:"
    grep "usb_uuid=" "$MOUNT_POINT/EFI/BOOT/grub.cfg"
else
    echo "✗ UUID wrapper NOT FOUND in grub.cfg"
fi
echo ""

echo "Checking for grub-install.cfg (backup)..."
if [[ -f "$MOUNT_POINT/EFI/BOOT/grub-install.cfg" ]]; then
    echo "✓ grub-install.cfg exists"
else
    echo "✗ grub-install.cfg NOT FOUND"
fi
echo ""

sudo umount "$MOUNT_POINT"

echo "2. Checking HFS+ partition (/dev/sdc3)..."
echo ""

if sudo mount -t hfsplus -o ro /dev/sdc3 "$MOUNT_POINT" 2>/dev/null; then
    echo "HFS+ partition mounted successfully"

    echo "Checking for auto-installer-mode.toml..."
    if [[ -f "$MOUNT_POINT/auto-installer-mode.toml" ]]; then
        echo "✓ auto-installer-mode.toml exists"
        cat "$MOUNT_POINT/auto-installer-mode.toml"
    else
        echo "✗ auto-installer-mode.toml NOT FOUND"
    fi

    sudo umount "$MOUNT_POINT"
else
    echo "⚠ Could not mount HFS+ partition (may be ISO9660)"
fi

sudo rmdir "$MOUNT_POINT"

echo ""
echo "=========================================="
echo "Check completed"
echo "=========================================="
