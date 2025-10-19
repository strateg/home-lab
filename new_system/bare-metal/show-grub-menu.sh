#!/bin/bash
# Quick check of GRUB menu on USB

MOUNT="/mnt/usb-grub-$$"
sudo mkdir -p "$MOUNT"
sudo mount /dev/sdc2 "$MOUNT"

echo "=========================================="
echo "GRUB MENU ON USB (/dev/sdc2)"
echo "=========================================="
echo ""
cat "$MOUNT/EFI/BOOT/grub.cfg"
echo ""
echo "=========================================="

sudo umount "$MOUNT"
sudo rmdir "$MOUNT"
