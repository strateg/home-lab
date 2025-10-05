#!/bin/bash
# Compare USB structure to understand what balenaEtcher creates
#
# Usage: sudo ./compare-usb-structure.sh /dev/sdX

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

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  USB Structure Analysis${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Device: $USB_DEVICE"
echo ""

echo -e "${YELLOW}[1] Partition table type:${NC}"
fdisk -l "$USB_DEVICE" 2>/dev/null | grep "Disklabel type"

echo ""
echo -e "${YELLOW}[2] Partitions:${NC}"
fdisk -l "$USB_DEVICE" 2>/dev/null | grep "^$USB_DEVICE"

echo ""
echo -e "${YELLOW}[3] Partition details (lsblk):${NC}"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL,PARTLABEL,PARTUUID

echo ""
echo -e "${YELLOW}[4] Filesystem details (blkid):${NC}"
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ -b "$part" ]; then
        echo "$part:"
        blkid "$part" | sed 's/^/  /'
    fi
done

echo ""
echo -e "${YELLOW}[5] MBR boot signature:${NC}"
MBR_SIG=$(dd if="$USB_DEVICE" bs=1 skip=510 count=2 2>/dev/null | xxd -p)
echo "  Signature at 0x1FE: 0x$MBR_SIG"
if [ "$MBR_SIG" = "55aa" ]; then
    echo -e "${GREEN}  ✓ Valid boot signature${NC}"
else
    echo -e "${RED}  ✗ Invalid boot signature${NC}"
fi

echo ""
echo -e "${YELLOW}[6] GPT table:${NC}"
sgdisk -p "$USB_DEVICE" 2>/dev/null || echo "  (No GPT table or not accessible)"

echo ""
echo -e "${YELLOW}[7] ISO9660 signature:${NC}"
ISO_SIG=$(dd if="$USB_DEVICE" bs=1 skip=32769 count=5 2>/dev/null)
if [ "$ISO_SIG" = "CD001" ]; then
    echo -e "${GREEN}  ✓ ISO9660 filesystem present (hybrid ISO)${NC}"
else
    echo "  (No ISO9660 signature)"
fi

echo ""
echo -e "${YELLOW}[8] EFI partition check:${NC}"
MOUNT_POINT="/tmp/usb-check-$$"
mkdir -p "$MOUNT_POINT"

for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ -b "$part" ]; then
        FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")
        if [ "$FSTYPE" = "vfat" ] || [ "$FSTYPE" = "iso9660" ]; then
            echo "  Checking $part ($FSTYPE)..."
            if mount -o ro "$part" "$MOUNT_POINT" 2>/dev/null; then
                if [ -d "$MOUNT_POINT/efi" ] || [ -d "$MOUNT_POINT/EFI" ]; then
                    echo -e "${GREEN}    ✓ EFI directory found${NC}"
                    find "$MOUNT_POINT" -type f -name "*.efi" 2>/dev/null | head -5 | sed 's/^/      /'
                fi
                if [ -d "$MOUNT_POINT/boot/grub" ]; then
                    echo -e "${GREEN}    ✓ GRUB directory found${NC}"
                    if [ -f "$MOUNT_POINT/boot/grub/grub.cfg" ]; then
                        echo "      grub.cfg present"
                    fi
                fi
                umount "$MOUNT_POINT"
            fi
        fi
    fi
done

rmdir "$MOUNT_POINT"

echo ""
echo -e "${YELLOW}[9] Hex dump of first 512 bytes (MBR):${NC}"
xxd -l 512 "$USB_DEVICE" | head -20

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Analysis Complete${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
