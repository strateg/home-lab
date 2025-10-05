#!/bin/bash
# Proxmox VE 9 - CORRECT Automated Installation USB Creator
#
# This script implements the OFFICIAL Proxmox automated installation method:
# 1. Install proxmox-auto-install-assistant
# 2. Prepare ISO with embedded answer.toml
# 3. Write prepared ISO to USB
# 4. Add graphics parameters for external display
#
# The prepared ISO automatically boots "Automated Installation" after 10 seconds
#
# Usage: sudo ./create-proxmox-usb.sh /dev/sdX path/to/proxmox.iso

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

if [ ! -f "answer.toml" ]; then
    echo -e "${RED}Error: answer.toml not found in current directory${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Proxmox VE 9 - Automated Installation      ║${NC}"
echo -e "${GREEN}║  Official Method (prepare-iso)              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================
# STEP 1: Check for proxmox-auto-install-assistant
# ============================================================
echo -e "${GREEN}[1/5] Checking for proxmox-auto-install-assistant...${NC}"

if ! command -v proxmox-auto-install-assistant &> /dev/null; then
    echo -e "${RED}Error: proxmox-auto-install-assistant not found${NC}"
    echo ""
    echo "Install it with these commands:"
    echo ""
    echo -e "${YELLOW}# Add Proxmox repository:${NC}"
    echo "wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg"
    echo 'echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" > /etc/apt/sources.list.d/pve-install-repo.list'
    echo ""
    echo -e "${YELLOW}# Update and install:${NC}"
    echo "apt update"
    echo "apt install proxmox-auto-install-assistant"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "  ✓ proxmox-auto-install-assistant found"

# ============================================================
# STEP 2: Validate answer.toml
# ============================================================
echo ""
echo -e "${GREEN}[2/5] Validating answer.toml...${NC}"

if proxmox-auto-install-assistant validate-answer answer.toml; then
    echo "  ✓ answer.toml is valid"
else
    echo -e "${RED}Error: answer.toml validation failed${NC}"
    exit 1
fi

# ============================================================
# STEP 3: Prepare ISO with embedded answer.toml
# ============================================================
echo ""
echo -e "${GREEN}[3/5] Preparing ISO with embedded answer.toml...${NC}"

PREPARED_ISO="${ISO_FILE%.iso}-automated.iso"

# Remove old prepared ISO if exists
rm -f "$PREPARED_ISO"

echo "Running: proxmox-auto-install-assistant prepare-iso ..."
proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
    --fetch-from iso \
    --answer-file answer.toml \
    --target "$PREPARED_ISO"

if [ ! -f "$PREPARED_ISO" ]; then
    echo -e "${RED}Error: Failed to create prepared ISO${NC}"
    exit 1
fi

echo "  ✓ Prepared ISO created: $PREPARED_ISO"
echo "  ✓ This ISO includes 'Automated Installation' boot entry"
echo "  ✓ Auto-selects after 10 seconds (official behavior)"

# ============================================================
# STEP 4: Write prepared ISO to USB
# ============================================================
echo ""
echo -e "${GREEN}[4/5] Writing prepared ISO to USB...${NC}"
echo ""
echo -e "${YELLOW}WARNING: This will ERASE all data on $USB_DEVICE${NC}"
echo ""
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    # Clean up prepared ISO
    rm -f "$PREPARED_ISO"
    exit 0
fi

# Unmount any mounted partitions
umount "${USB_DEVICE}"* 2>/dev/null || true

echo ""
echo "Writing prepared ISO to USB with dd..."
dd if="$PREPARED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo ""
echo "  ✓ Prepared ISO written to USB"

# ============================================================
# STEP 5: Add graphics parameters for external display
# ============================================================
echo ""
echo -e "${GREEN}[5/5] Adding graphics parameters for external display...${NC}"

partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

MOUNT_POINT="/tmp/usb-$$"
mkdir -p "$MOUNT_POINT"
GRUB_MODIFIED=0

# Find and mount the FAT32 EFI partition
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ]; then
        if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

            if [ -n "$GRUB_CFG" ]; then
                echo "Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}"

                # Backup original
                cp "$GRUB_CFG" "$GRUB_CFG.backup-$(date +%s)"

                # Check if graphics parameters already present
                if grep -q "video=vesafb" "$GRUB_CFG"; then
                    echo "  ✓ Graphics parameters already present"
                else
                    echo "  Adding graphics parameters to all boot entries..."

                    # Add graphics parameters to all linux boot lines
                    sed -i '/linux.*\/boot\/linux26/ s|$| video=vesafb:ywrap,mtrr vga=791 nomodeset|' "$GRUB_CFG"

                    echo "  ✓ Graphics parameters added"
                fi

                sync
                GRUB_MODIFIED=1
            fi

            umount "$MOUNT_POINT"
            break
        fi
    fi
done

rmdir "$MOUNT_POINT"

# ============================================================
# FINAL STATUS
# ============================================================
echo ""
sync
sleep 2

if [ $GRUB_MODIFIED -eq 1 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║  USB READY FOR AUTOMATED INSTALLATION!         ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}What was done:${NC}"
    echo "  ✓ Validated answer.toml"
    echo "  ✓ Prepared ISO with embedded answer file (official method)"
    echo "  ✓ Written prepared ISO to USB"
    echo "  ✓ Added graphics parameters for external display"
    echo ""
    echo -e "${YELLOW}BOOT INSTRUCTIONS:${NC}"
    echo ""
    echo "  1. Connect external monitor to Mini DisplayPort"
    echo "  2. Power ON the external monitor"
    echo "  3. Insert USB into Dell XPS L701X"
    echo "  4. Power on laptop"
    echo "  5. Press F12 for boot menu"
    echo "  6. Select: 'UEFI: USB...' (NOT 'USB Storage Device')"
    echo ""
    echo -e "${GREEN}AUTOMATIC BEHAVIOR:${NC}"
    echo ""
    echo "  • GRUB menu appears on external display"
    echo "  • First option: 'Automated Installation' (added by prepare-iso)"
    echo "  • Countdown: 10 seconds (OFFICIAL timeout)"
    echo "  • Installation starts AUTOMATICALLY!"
    echo "  • Reads embedded answer.toml from ISO"
    echo "  • Progress shown on external display"
    echo "  • System reboots when complete (~10-15 min)"
    echo ""
    echo -e "${BLUE}AFTER INSTALLATION:${NC}"
    echo ""
    echo "  1. Find IP address (check router DHCP leases)"
    echo "  2. SSH: ssh root@<ip-address>"
    echo "  3. Password: Homelab2025! (from answer.toml)"
    echo "  4. Web UI: https://<ip-address>:8006"
    echo ""
    echo -e "${GREEN}Installation is FULLY AUTOMATIC using official Proxmox method!${NC}"
    echo ""
else
    echo -e "${YELLOW}Warning: Could not modify GRUB for graphics${NC}"
    echo "USB created but external display may not work"
    echo ""
fi

# Clean up prepared ISO
echo "Cleaning up..."
rm -f "$PREPARED_ISO"
echo "  ✓ Temporary prepared ISO removed"
echo ""
