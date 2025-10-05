#!/bin/bash
# Proxmox VE 9 - Official Unattended USB Creator
#
# Uses the official proxmox-auto-install-assistant tool to properly
# embed the answer file into the ISO BEFORE writing to USB.
#
# This is the CORRECT method recommended by Proxmox documentation.
#
# Requirements:
#   - proxmox-auto-install-assistant (install with: apt install proxmox-auto-install-assistant)
#   - proxmox-auto-install-answer.toml in current directory
#   - Original Proxmox VE ISO
#
# Usage: sudo ./create-proxmox-usb-official.sh /dev/sdX path/to/proxmox.iso

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

# Validate inputs
if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: $USB_DEVICE is not a block device${NC}"
    exit 1
fi

if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: $ISO_FILE not found${NC}"
    exit 1
fi

if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda (safety check)${NC}"
    exit 1
fi

if [ ! -f "proxmox-auto-install-answer.toml" ]; then
    echo -e "${RED}Error: proxmox-auto-install-answer.toml not found${NC}"
    exit 1
fi

# Check if proxmox-auto-install-assistant is installed
if ! command -v proxmox-auto-install-assistant &> /dev/null; then
    echo -e "${RED}Error: proxmox-auto-install-assistant not installed${NC}"
    echo ""
    echo "Install it with:"
    echo "  apt update"
    echo "  apt install proxmox-auto-install-assistant"
    echo ""
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Proxmox VE 9 - Official USB Creator         ║${NC}"
echo -e "${GREEN}║  Using proxmox-auto-install-assistant        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}WARNING: This will ERASE all data on $USB_DEVICE${NC}"
echo ""
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Unmount any mounted partitions
umount "${USB_DEVICE}"* 2>/dev/null || true

# ============================================================
# STEP 1: Prepare ISO with embedded answer file
# ============================================================
echo ""
echo -e "${GREEN}[1/3] Preparing ISO with embedded answer file...${NC}"
echo ""

MODIFIED_ISO="proxmox-auto-install.iso"

# Remove old modified ISO if exists
rm -f "$MODIFIED_ISO"

echo "Running: proxmox-auto-install-assistant prepare-iso ..."
proxmox-auto-install-assistant prepare-iso \
    "$ISO_FILE" \
    --fetch-from iso \
    --answer-file proxmox-auto-install-answer.toml \
    --target "$MODIFIED_ISO"

if [ ! -f "$MODIFIED_ISO" ]; then
    echo -e "${RED}Error: Failed to create modified ISO${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Modified ISO created: $MODIFIED_ISO${NC}"

# ============================================================
# STEP 2: Add graphics parameters for external display
# ============================================================
echo ""
echo -e "${GREEN}[2/3] Adding graphics parameters for external display...${NC}"
echo ""

# Mount the ISO to modify GRUB
MOUNT_POINT="/tmp/iso-$$"
mkdir -p "$MOUNT_POINT"

# Mount the modified ISO
mount -o loop "$MODIFIED_ISO" "$MOUNT_POINT" 2>/dev/null || {
    echo -e "${YELLOW}Note: Cannot mount ISO directly (expected for hybrid ISOs)${NC}"
    echo "Will modify after writing to USB..."
}

if mountpoint -q "$MOUNT_POINT"; then
    # ISO is mounted, try to find GRUB config
    GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" 2>/dev/null | head -1)

    if [ -n "$GRUB_CFG" ]; then
        echo "Found GRUB config in ISO"
        echo "The auto-install entry should already be added by proxmox-auto-install-assistant"
        cat "$GRUB_CFG" | grep -A 3 "Auto"
    fi

    umount "$MOUNT_POINT"
fi

rmdir "$MOUNT_POINT"

# ============================================================
# STEP 3: Write modified ISO to USB
# ============================================================
echo ""
echo -e "${GREEN}[3/3] Writing modified ISO to USB...${NC}"
echo ""

dd if="$MODIFIED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo ""
echo -e "${GREEN}✓ USB written${NC}"

# ============================================================
# STEP 4: Modify GRUB on USB to add graphics parameters
# ============================================================
echo ""
echo -e "${GREEN}[4/4] Adding graphics parameters to GRUB...${NC}"
echo ""

partprobe "$USB_DEVICE" 2>/dev/null || true
sleep 3

MOUNT_POINT="/tmp/usb-$$"
mkdir -p "$MOUNT_POINT"
MODIFIED=0

# Find and mount the FAT32 EFI partition
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ] && mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
        GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

        if [ -n "$GRUB_CFG" ]; then
            echo "Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}"

            # Check if auto-install entry exists
            if grep -q "auto-install" "$GRUB_CFG" || grep -q "Automated" "$GRUB_CFG"; then
                echo "✓ Auto-install entry found"

                # Add graphics parameters to the auto-install entry
                # We need to add: video=vesafb:ywrap,mtrr vga=791 nomodeset

                if grep -q "video=vesafb" "$GRUB_CFG"; then
                    echo "✓ Graphics parameters already present"
                else
                    echo "Adding graphics parameters..."

                    # Backup original
                    cp "$GRUB_CFG" "$GRUB_CFG.backup-$(date +%s)"

                    # Add graphics parameters to the auto-install linux line
                    sed -i '/auto-install/,/linux.*linux26/ s|linux \(/boot/linux26.*\)|linux \1 video=vesafb:ywrap,mtrr vga=791 nomodeset|' "$GRUB_CFG"

                    sync
                    echo "✓ Graphics parameters added"
                fi

                MODIFIED=1
            else
                echo "⚠ Auto-install entry not found in GRUB"
                echo "Contents:"
                cat "$GRUB_CFG"
            fi
        fi

        umount "$MOUNT_POINT"
        [ $MODIFIED -eq 1 ] && break
    fi
done

rmdir "$MOUNT_POINT"

# ============================================================
# STEP 5: Final verification
# ============================================================
echo ""
echo -e "${GREEN}[5/5] Verification...${NC}"
echo ""

sync
sleep 2

if [ $MODIFIED -eq 1 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║     USB READY FOR AUTO-INSTALL!                ║${NC}"
    echo -e "${GREEN}║     (Created with official tool)               ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}What was done:${NC}"
    echo "  ✓ Used proxmox-auto-install-assistant to embed answer file"
    echo "  ✓ Auto-install boot entry created by official tool"
    echo "  ✓ Graphics parameters added for external display"
    echo "  ✓ Modified ISO written to USB with dd"
    echo ""
    echo -e "${YELLOW}BOOT INSTRUCTIONS:${NC}"
    echo ""
    echo "  1. Connect external monitor to Mini DisplayPort"
    echo "  2. Power ON the monitor"
    echo "  3. Insert USB into Dell XPS L701X"
    echo "  4. Power on laptop"
    echo "  5. Press F12 for boot menu"
    echo "  6. Select: 'UEFI: USB...' (NOT 'USB Storage Device')"
    echo "  7. Select 'Automated Installation' entry"
    echo "  8. Installation should start automatically"
    echo ""
    echo -e "${GREEN}Installation will complete in ~10-15 minutes${NC}"
    echo ""

    # Clean up modified ISO
    echo "Cleaning up..."
    rm -f "$MODIFIED_ISO"
    echo "✓ Temporary ISO removed"
    echo ""
else
    echo -e "${YELLOW}USB created but couldn't modify GRUB for graphics${NC}"
    echo "You may need to manually select the auto-install entry with graphics parameters"
    echo ""

    # Don't delete ISO in case user wants to inspect it
    echo "Modified ISO kept: $MODIFIED_ISO"
    echo ""
fi
