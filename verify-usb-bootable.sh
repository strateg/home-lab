#!/bin/bash
# Verify USB Bootability
#
# This script checks if a USB drive has proper boot sectors
# and partition structure for booting
#
# Usage: sudo ./verify-usb-bootable.sh /dev/sdX

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}"
   exit 1
fi

if [ "$#" -ne 1 ]; then
    echo "Usage: sudo $0 /dev/sdX"
    exit 1
fi

USB_DEVICE="$1"

if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: $USB_DEVICE is not a valid block device${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  USB Bootability Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Device: $USB_DEVICE"
echo ""

# Check 1: MBR boot signature
echo -e "${YELLOW}[1] Checking MBR boot signature...${NC}"
MBR_SIG=$(dd if="$USB_DEVICE" bs=1 skip=510 count=2 2>/dev/null | xxd -p)
if [ "$MBR_SIG" = "55aa" ]; then
    echo -e "${GREEN}✓ MBR boot signature present (0x55AA)${NC}"
else
    echo -e "${RED}✗ MBR boot signature missing or invalid ($MBR_SIG)${NC}"
fi

# Check 2: Partition table
echo ""
echo -e "${YELLOW}[2] Checking partition table...${NC}"
fdisk -l "$USB_DEVICE" 2>/dev/null | grep "^$USB_DEVICE"
PART_COUNT=$(fdisk -l "$USB_DEVICE" 2>/dev/null | grep "^$USB_DEVICE" | wc -l)
if [ "$PART_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $PART_COUNT partition(s)${NC}"
else
    echo -e "${RED}✗ No partitions found${NC}"
fi

# Check 3: Boot flag
echo ""
echo -e "${YELLOW}[3] Checking boot flag...${NC}"
BOOT_FLAG=$(fdisk -l "$USB_DEVICE" 2>/dev/null | grep "^\*" | wc -l)
if [ "$BOOT_FLAG" -gt 0 ]; then
    echo -e "${GREEN}✓ Boot flag is set${NC}"
else
    echo -e "${YELLOW}⚠ No boot flag set (may be OK for UEFI)${NC}"
fi

# Check 4: Filesystem types
echo ""
echo -e "${YELLOW}[4] Checking filesystems...${NC}"
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ -b "$part" ]; then
        FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "unknown")
        LABEL=$(blkid -s LABEL -o value "$part" 2>/dev/null || echo "")
        echo "  $part: $FSTYPE ${LABEL:+[$LABEL]}"
    fi
done

# Check 5: ISO9660 signature (if present)
echo ""
echo -e "${YELLOW}[5] Checking for ISO9660 filesystem...${NC}"
ISO_SIG=$(dd if="$USB_DEVICE" bs=1 skip=32769 count=5 2>/dev/null)
if [ "$ISO_SIG" = "CD001" ]; then
    echo -e "${GREEN}✓ ISO9660 signature found (hybrid ISO)${NC}"
else
    echo -e "${YELLOW}⚠ No ISO9660 signature (may be normal)${NC}"
fi

# Check 6: EFI boot files
echo ""
echo -e "${YELLOW}[6] Checking for EFI boot capability...${NC}"

# Try to mount and check for EFI files
MOUNT_POINT="/mnt/usb-verify-$$"
mkdir -p "$MOUNT_POINT"

EFI_FOUND=0
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ -b "$part" ]; then
        if mount -o ro "$part" "$MOUNT_POINT" 2>/dev/null; then
            if [ -d "$MOUNT_POINT/EFI" ] || [ -d "$MOUNT_POINT/boot/grub" ]; then
                echo -e "${GREEN}✓ EFI boot files found on $part${NC}"
                EFI_FOUND=1
            fi
            umount "$MOUNT_POINT"
        fi
    fi
done

if [ $EFI_FOUND -eq 0 ]; then
    echo -e "${YELLOW}⚠ No EFI boot directory found${NC}"
fi

rmdir "$MOUNT_POINT"

# Check 7: ISOLINUX/SYSLINUX
echo ""
echo -e "${YELLOW}[7] Checking for ISOLINUX/SYSLINUX...${NC}"

ISOLINUX_FOUND=0
MOUNT_POINT="/mnt/usb-verify-$$"
mkdir -p "$MOUNT_POINT"

for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ -b "$part" ]; then
        if mount -o ro "$part" "$MOUNT_POINT" 2>/dev/null; then
            if [ -f "$MOUNT_POINT/boot/isolinux/isolinux.bin" ] || [ -f "$MOUNT_POINT/isolinux/isolinux.bin" ]; then
                echo -e "${GREEN}✓ ISOLINUX found on $part${NC}"
                ISOLINUX_FOUND=1
            fi
            umount "$MOUNT_POINT"
        fi
    fi
done

if [ $ISOLINUX_FOUND -eq 0 ]; then
    echo -e "${YELLOW}⚠ No ISOLINUX found${NC}"
fi

rmdir "$MOUNT_POINT"

# Check 8: GPT
echo ""
echo -e "${YELLOW}[8] Checking partition table type...${NC}"
PART_TYPE=$(fdisk -l "$USB_DEVICE" 2>/dev/null | grep "Disklabel type" | awk '{print $3}')
if [ -n "$PART_TYPE" ]; then
    echo "  Partition table: $PART_TYPE"
    if [ "$PART_TYPE" = "gpt" ]; then
        echo -e "${GREEN}✓ GPT partition table (good for UEFI)${NC}"
    elif [ "$PART_TYPE" = "dos" ]; then
        echo -e "${GREEN}✓ MBR/DOS partition table (good for Legacy)${NC}"
    fi
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  SUMMARY${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

BOOTABLE=1

if [ "$MBR_SIG" != "55aa" ]; then
    echo -e "${RED}✗ Missing MBR boot signature${NC}"
    BOOTABLE=0
fi

if [ "$PART_COUNT" -eq 0 ]; then
    echo -e "${RED}✗ No partitions found${NC}"
    BOOTABLE=0
fi

if [ $EFI_FOUND -eq 0 ] && [ $ISOLINUX_FOUND -eq 0 ]; then
    echo -e "${RED}✗ No boot loader found (neither EFI nor ISOLINUX)${NC}"
    BOOTABLE=0
fi

if [ $BOOTABLE -eq 1 ]; then
    echo -e "${GREEN}✓✓✓ USB appears to be BOOTABLE ✓✓✓${NC}"
    echo ""
    echo "Boot modes supported:"
    if [ $EFI_FOUND -eq 1 ]; then
        echo "  ✓ UEFI boot"
    fi
    if [ $ISOLINUX_FOUND -eq 1 ]; then
        echo "  ✓ Legacy/BIOS boot"
    fi
    echo ""
    echo -e "${GREEN}This USB should boot on Dell XPS L701X${NC}"
else
    echo -e "${RED}✗✗✗ USB may NOT be bootable ✗✗✗${NC}"
    echo ""
    echo "Issues found:"
    echo "  - Check the output above for details"
    echo "  - Try recreating the USB"
fi

echo ""
