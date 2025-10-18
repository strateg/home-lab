#!/bin/bash
# Диагностика почему grub.cfg не был модифицирован

USB_DEVICE="${1:-/dev/sdc}"

echo "=== File System Types ==="
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ -b "$part" ]; then
        fstype=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "unknown")
        echo "$part: $fstype"
    fi
done

echo ""
echo "=== Mounting EFI Partition ==="
MOUNT_POINT=$(mktemp -d)

# Try sdc2
if sudo mount -o rw "${USB_DEVICE}2" "$MOUNT_POINT" 2>/dev/null; then
    echo "✓ Mounted ${USB_DEVICE}2"

    echo ""
    echo "=== EFI/BOOT/ contents ==="
    ls -lah "$MOUNT_POINT/EFI/BOOT/"

    echo ""
    echo "=== Checking for grub-install.cfg ==="
    if [ -f "$MOUNT_POINT/EFI/BOOT/grub-install.cfg" ]; then
        echo "✓ grub-install.cfg EXISTS (backup created by script)"
        echo ""
        echo "=== grub-install.cfg content (first 20 lines) ==="
        head -20 "$MOUNT_POINT/EFI/BOOT/grub-install.cfg"
    else
        echo "✗ grub-install.cfg NOT FOUND"
        echo "   This means embed_uuid_wrapper() did NOT run or failed"
    fi

    sudo umount "$MOUNT_POINT"
elif sudo mount -o rw "${USB_DEVICE}p2" "$MOUNT_POINT" 2>/dev/null; then
    echo "✓ Mounted ${USB_DEVICE}p2"
    ls -lah "$MOUNT_POINT/EFI/BOOT/"
    sudo umount "$MOUNT_POINT"
else
    echo "✗ Cannot mount EFI partition"
fi

rmdir "$MOUNT_POINT" 2>/dev/null
