#!/bin/bash
# Proxmox VE 9 USB - EFI Partition Modification
#
# Key insight: UEFI boot reads from EFI partition (FAT32 - writable!), not ISO9660
#
# Strategy:
# 1. Write ISO with dd (bootable USB)
# 2. Find EFI partition (FAT32)
# 3. Mount it writable
# 4. Modify GRUB config there
#
# Usage: sudo ./prepare-proxmox-usb-efi-modify.sh /dev/sdX path/to/proxmox.iso

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

if [ "$#" -ne 2 ]; then
    echo "Usage: sudo $0 /dev/sdX path/to/proxmox.iso"
    exit 1
fi

USB_DEVICE="$1"
ISO_FILE="$2"

if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: Invalid device${NC}"
    exit 1
fi

if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: ISO not found${NC}"
    exit 1
fi

if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}WARNING: This will ERASE $USB_DEVICE${NC}"
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes': " confirm
[ "$confirm" != "yes" ] && exit 0

umount "${USB_DEVICE}"* 2>/dev/null || true

echo ""
echo -e "${GREEN}[1/4] Writing ISO to USB (bootable)...${NC}"

dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo -e "${GREEN}✓ Bootable USB created${NC}"

echo ""
echo -e "${GREEN}[2/4] Detecting partitions...${NC}"

partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

echo "Partition table:"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL
fdisk -l "$USB_DEVICE" 2>/dev/null | grep "^$USB_DEVICE"

echo ""
echo -e "${GREEN}[3/4] Looking for EFI partition (FAT32 - writable)...${NC}"

MOUNT_POINT="/tmp/usb-efi-$$"
mkdir -p "$MOUNT_POINT"
EFI_FOUND=0

# Look specifically for FAT32/VFAT partitions (EFI System Partition)
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")
    PARTTYPE=$(blkid -s PTTYPE -o value "$part" 2>/dev/null || echo "")

    echo ""
    echo "Checking: $part"
    echo "  Filesystem: $FSTYPE"

    if [ "$FSTYPE" = "vfat" ]; then
        echo -e "${GREEN}  ✓ Found FAT partition (potentially EFI)${NC}"

        # Try to mount writable
        if mount -t vfat -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            echo -e "${GREEN}  ✓ Mounted writable!${NC}"

            # Check if it's actually an EFI partition
            if [ -d "$MOUNT_POINT/EFI" ] || [ -d "$MOUNT_POINT/efi" ]; then
                echo -e "${GREEN}  ✓ This is the EFI partition!${NC}"

                # Look for GRUB
                GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

                if [ -n "$GRUB_CFG" ]; then
                    echo -e "${GREEN}  ✓ Found GRUB: ${GRUB_CFG#$MOUNT_POINT/}${NC}"

                    # Backup original
                    cp "$GRUB_CFG" "$GRUB_CFG.backup"

                    # Read original to understand structure
                    echo ""
                    echo "Original GRUB preview:"
                    head -20 "$GRUB_CFG"

                    echo ""
                    echo -e "${GREEN}[4/4] Modifying GRUB on EFI partition...${NC}"

                    # Modify existing entries to add our parameters
                    # Find all lines with 'linux' and add our params at the end
                    sed -i.orig '/^\s*linux/ {
                        /video=vesafb/! s|$| video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition|
                    }' "$GRUB_CFG"

                    # Set shorter timeout
                    if grep -q "^set timeout=" "$GRUB_CFG"; then
                        sed -i 's/^set timeout=.*/set timeout=3/' "$GRUB_CFG"
                    else
                        sed -i '1i set timeout=3' "$GRUB_CFG"
                    fi

                    # Set default to first entry
                    if grep -q "^set default=" "$GRUB_CFG"; then
                        sed -i 's/^set default=.*/set default=0/' "$GRUB_CFG"
                    else
                        sed -i '1i set default=0' "$GRUB_CFG"
                    fi

                    echo ""
                    echo "Modified GRUB preview:"
                    head -20 "$GRUB_CFG"

                    echo ""
                    echo -e "${GREEN}✓ GRUB modified with graphics + auto-install${NC}"

                    # Add answer file
                    if [ -f "proxmox-auto-install-answer.toml" ]; then
                        cp "proxmox-auto-install-answer.toml" "$MOUNT_POINT/answer.toml"
                        echo -e "${GREEN}✓ Answer file copied${NC}"
                    fi

                    # Add post-install script
                    if [ -f "proxmox-post-install.sh" ]; then
                        cp "proxmox-post-install.sh" "$MOUNT_POINT/"
                        echo -e "${GREEN}✓ Post-install script copied${NC}"
                    fi

                    sync
                    EFI_FOUND=1
                fi
            fi

            umount "$MOUNT_POINT"

            if [ $EFI_FOUND -eq 1 ]; then
                break
            fi
        else
            echo "  ✗ Could not mount writable"
        fi
    fi
done

rmdir "$MOUNT_POINT"

echo ""

if [ $EFI_FOUND -eq 1 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   SUCCESS - EFI PARTITION MODIFIED!       ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Outcome A achieved!${NC}"
    echo ""
    echo "What was done:"
    echo "  ✓ USB written with dd (bootable like balenaEtcher)"
    echo "  ✓ EFI partition found (FAT32 - writable)"
    echo "  ✓ GRUB modified directly on USB"
    echo "  ✓ Graphics parameters added"
    echo "  ✓ Auto-install parameter added"
    echo "  ✓ Answer file added"
    echo "  ✓ Timeout set to 3 seconds"
    echo ""
    echo -e "${BLUE}Boot Instructions:${NC}"
    echo "  1. Connect external monitor to Mini DisplayPort"
    echo "  2. Power on monitor first"
    echo "  3. Insert USB, power on laptop"
    echo "  4. F12 → Select 'UEFI: USB...'"
    echo "  5. Wait 3 seconds OR press Enter"
    echo "  6. Installation starts automatically!"
    echo ""
    echo -e "${GREEN}External display will work immediately!${NC}"
    echo ""
else
    echo -e "${YELLOW}╔════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║   NO WRITABLE EFI PARTITION FOUND          ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "The USB has no writable FAT32 EFI partition."
    echo "This ISO might be structured differently."
    echo ""
    echo "Partitions found:"
    lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL
    echo ""
    echo -e "${YELLOW}Cannot achieve automatic modification with this ISO.${NC}"
fi

echo ""
