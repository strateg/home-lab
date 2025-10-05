#!/bin/bash
# Proxmox VE 9 USB - Smart Modification Approach
#
# Strategy:
# 1. Write ISO with dd (bootable - guaranteed to work)
# 2. Look for writable EFI partition and modify GRUB there
# 3. If no writable partition, provide clear manual instructions
#
# Usage: sudo ./prepare-proxmox-usb-smart.sh /dev/sdX path/to/proxmox.iso

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
echo -e "${GREEN}[1/3] Writing ISO with dd...${NC}"

dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo -e "${GREEN}✓ Bootable USB created (like balenaEtcher)${NC}"

echo ""
echo -e "${GREEN}[2/3] Scanning for modifiable partitions...${NC}"

partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL

MOUNT_POINT="/tmp/usb-$$"
mkdir -p "$MOUNT_POINT"
MODIFIED=0

# Look for VFAT (EFI) partition - these are often writable
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ]; then
        echo ""
        echo "Found VFAT partition: $part (potentially writable)"

        if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            if touch "$MOUNT_POINT/.test" 2>/dev/null; then
                rm "$MOUNT_POINT/.test"
                echo -e "${GREEN}✓ Partition is writable!${NC}"

                # Look for GRUB config
                GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

                if [ -n "$GRUB_CFG" ]; then
                    echo "✓ Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}"

                    # Back up
                    cp "$GRUB_CFG" "$GRUB_CFG.backup"

                    # Modify all linux boot lines
                    sed -i '/^\s*linux/ s|$| video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition|' "$GRUB_CFG"

                    # Set timeout and default
                    sed -i '1i set timeout=3\nset default=0' "$GRUB_CFG"

                    echo -e "${GREEN}✓ GRUB modified (graphics + auto-install)${NC}"
                    MODIFIED=1
                fi

                # Copy answer file
                if [ -f "proxmox-auto-install-answer.toml" ]; then
                    cp "proxmox-auto-install-answer.toml" "$MOUNT_POINT/answer.toml"
                    echo -e "${GREEN}✓ Answer file copied${NC}"
                fi

                # Copy post-install
                [ -f "proxmox-post-install.sh" ] && cp "proxmox-post-install.sh" "$MOUNT_POINT/"

                sync
            fi

            umount "$MOUNT_POINT"

            [ $MODIFIED -eq 1 ] && break
        fi
    fi
done

rmdir "$MOUNT_POINT"

echo ""
echo -e "${GREEN}[3/3] Creating boot helper script...${NC}"

# Create a script on the USB root that user can reference
HELPER="/tmp/add-boot-params.txt"

cat > "$HELPER" <<'HELPEREOF'
═══════════════════════════════════════════════════════════
  PROXMOX AUTO-INSTALL - BOOT PARAMETERS
═══════════════════════════════════════════════════════════

Dell XPS L701X requires these parameters for external display:

AT GRUB MENU (if needed):
  Press 'e' to edit
  Find line starting with: linux /boot/
  Add to END of line:

  video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition

  Press Ctrl+X to boot

═══════════════════════════════════════════════════════════
HELPEREOF

cat "$HELPER"
rm "$HELPER"

echo ""

if [ $MODIFIED -eq 1 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   SUCCESS - USB READY FOR AUTO-INSTALL ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "✓ Bootable USB (dd method - works like balenaEtcher)"
    echo "✓ GRUB modified with auto-install + graphics params"
    echo "✓ Answer file on USB"
    echo ""
    echo "Boot steps:"
    echo "  1. Connect external monitor → Mini DisplayPort"
    echo "  2. F12 → Select 'UEFI: USB...'"
    echo "  3. Press Enter or wait 3 seconds"
    echo "  4. Auto-install starts!"
else
    echo -e "${YELLOW}╔════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║   USB BOOTABLE - NEEDS MANUAL GRUB EDIT ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "USB is bootable, but ISO filesystem is read-only."
    echo ""
    echo -e "${RED}PROBLEM: You can't manually edit GRUB (broken display)${NC}"
    echo ""
    echo -e "${BLUE}Solution: Connect USB keyboard + external monitor FIRST${NC}"
    echo "Then you CAN edit GRUB before boot."
    echo ""
    echo "Or: Run this script on a system with display to verify the answer file is accessible"
fi

echo ""
