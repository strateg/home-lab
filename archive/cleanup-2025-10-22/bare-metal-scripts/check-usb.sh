#!/bin/bash
# Проверить USB флэшку на готовность к UEFI-загрузке

USB_DEVICE="${1:-/dev/sdc}"

echo "Checking USB device: $USB_DEVICE"
echo ""

# 1. Partition table
echo "=== Partition Table ==="
sudo fdisk -l "$USB_DEVICE" | grep -E "Disk $USB_DEVICE|^$USB_DEVICE"
echo ""

# 2. EFI partition
echo "=== EFI Partition Check ==="
MOUNT_POINT=$(mktemp -d)
sudo mount "${USB_DEVICE}2" "$MOUNT_POINT" 2>/dev/null || sudo mount "${USB_DEVICE}p2" "$MOUNT_POINT" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✓ EFI partition mounted"

    if [ -f "$MOUNT_POINT/EFI/BOOT/grubx64.efi" ]; then
        echo "✓ UEFI bootloader found: EFI/BOOT/grubx64.efi"
    else
        echo "✗ MISSING: EFI/BOOT/grubx64.efi"
    fi

    if [ -f "$MOUNT_POINT/EFI/BOOT/grub.cfg" ]; then
        echo "✓ GRUB config found: EFI/BOOT/grub.cfg"
        echo ""
        echo "=== grub.cfg content (first 30 lines) ==="
        head -30 "$MOUNT_POINT/EFI/BOOT/grub.cfg"
    else
        echo "✗ MISSING: EFI/BOOT/grub.cfg"
    fi

    sudo umount "$MOUNT_POINT"
else
    echo "✗ Cannot mount EFI partition"
fi

rmdir "$MOUNT_POINT" 2>/dev/null
echo ""
echo "=== Recommendation ==="
echo "Boot with F12 and select: UEFI: USB... (NOT 'USB Storage Device')"
