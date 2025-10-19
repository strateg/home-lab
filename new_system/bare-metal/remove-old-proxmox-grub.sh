#!/bin/bash
#
# Remove old Proxmox GRUB from Dell XPS L701X
# Run this ON Dell XPS via SSH before using auto-install USB
#

set -e

echo "=========================================="
echo "Removing Old Proxmox GRUB"
echo "=========================================="
echo ""
echo "This will remove Proxmox EFI bootloader from disk"
echo "System will NOT boot from disk after this!"
echo "You MUST boot from USB to reinstall Proxmox"
echo ""
read -p "Continue? (type YES): " confirm

if [[ "$confirm" != "YES" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Searching for EFI partition..."

# Find EFI mount point
EFI_MOUNT=""
if mountpoint -q /efi 2>/dev/null; then
    EFI_MOUNT="/efi"
    echo "✓ Found EFI at /efi"
elif mountpoint -q /boot/efi 2>/dev/null; then
    EFI_MOUNT="/boot/efi"
    echo "✓ Found EFI at /boot/efi"
else
    echo "✗ EFI partition not mounted!"
    echo "Trying to mount..."

    # Try to find and mount EFI partition
    EFI_PART=$(blkid | grep -i 'TYPE="vfat"' | grep -E 'sda[0-9]' | head -1 | cut -d: -f1)
    if [[ -n "$EFI_PART" ]]; then
        echo "Found EFI partition: $EFI_PART"
        mkdir -p /efi
        mount "$EFI_PART" /efi
        EFI_MOUNT="/efi"
        echo "✓ Mounted $EFI_PART to /efi"
    else
        echo "✗ Could not find EFI partition!"
        exit 1
    fi
fi

echo ""
echo "EFI mount point: $EFI_MOUNT"
echo "Listing contents:"
ls -la "$EFI_MOUNT/EFI/" || ls -la "$EFI_MOUNT/"

echo ""
echo "Removing Proxmox bootloader..."

# Remove Proxmox EFI directory
if [[ -d "$EFI_MOUNT/EFI/proxmox" ]]; then
    rm -rf "$EFI_MOUNT/EFI/proxmox"
    echo "✓ Removed $EFI_MOUNT/EFI/proxmox"
else
    echo "⚠ $EFI_MOUNT/EFI/proxmox not found (maybe already removed?)"
fi

# Remove installation markers
echo ""
echo "Removing installation markers..."
rm -f /etc/proxmox-install-id
rm -f "$EFI_MOUNT/proxmox-installed"
echo "✓ Markers removed"

sync

echo ""
echo "=========================================="
echo "✓ Old Proxmox GRUB removed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Reboot system: shutdown -r now"
echo "2. System will fail to boot from disk (expected)"
echo "3. It will fallback to USB boot"
echo "4. You will see our GRUB wrapper with auto-install"
echo ""
echo "Ready to reboot? (shutdown -r now)"
