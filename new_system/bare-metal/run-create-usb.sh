#!/bin/bash
#
# Wrapper script for create-uefi-autoinstall-proxmox-usb.sh
# Run this script manually in terminal with: sudo ./run-create-usb.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Proxmox Auto-Install USB Creator"
echo "=========================================="
echo ""
echo "This script will create bootable USB with:"
echo "  - Proxmox VE 9 ISO"
echo "  - Auto-install configuration (answer.toml)"
echo "  - UUID-based reinstall prevention"
echo ""
echo "Configuration:"
echo "  ISO: /home/strateg/Загрузки/proxmox-ve_9.0-1.iso"
echo "  Config: answer.toml"
echo "  Target: /dev/sdc (SanDisk 3.2Gen1 114.6G)"
echo ""
echo "⚠️  WARNING: ALL DATA ON /dev/sdc WILL BE ERASED!"
echo ""
read -p "Continue? (type YES): " confirm

if [[ "$confirm" != "YES" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Starting USB creation..."
echo ""

# Run the main script with AUTO_CONFIRM and absolute ISO path
AUTO_CONFIRM=1 ./create-uefi-autoinstall-proxmox-usb.sh /home/strateg/Загрузки/proxmox-ve_9.0-1.iso answer.toml /dev/sdc

echo ""
echo "=========================================="
echo "USB creation completed!"
echo "=========================================="
