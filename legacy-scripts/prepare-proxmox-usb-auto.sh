#!/bin/bash
# Proxmox VE 9 Fully Automated USB Preparation
#
# This script creates a bootable USB that auto-starts installation
# with minimal user interaction (just one Enter press)
#
# Method: Extract ISO, modify GRUB config, add answer file, rebuild ISO
#
# Usage: sudo ./prepare-proxmox-usb-auto.sh /dev/sdX path/to/proxmox.iso
#
# WARNING: This will ERASE all data on the target USB drive!

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}"
   echo "Usage: sudo $0 /dev/sdX path/to/proxmox.iso"
   exit 1
fi

# Check arguments
if [ "$#" -ne 2 ]; then
    echo -e "${RED}Error: Invalid number of arguments${NC}"
    echo "Usage: sudo $0 /dev/sdX path/to/proxmox.iso"
    exit 1
fi

USB_DEVICE="$1"
ISO_FILE="$2"

# Validate inputs
if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: $USB_DEVICE is not a valid block device${NC}"
    exit 1
fi

if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: $ISO_FILE not found${NC}"
    exit 1
fi

if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda (system disk)${NC}"
    exit 1
fi

# Check for required tools
for tool in xorriso mkisofs find sed; do
    if ! command -v "$tool" &> /dev/null; then
        echo -e "${YELLOW}Installing required tool: $tool${NC}"
        apt-get update && apt-get install -y xorriso genisoimage isolinux
        break
    fi
done

# Confirm
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

# Create work directory
WORK_DIR="/tmp/proxmox-iso-$$"
mkdir -p "$WORK_DIR"

echo ""
echo -e "${GREEN}Step 1: Extracting ISO contents (this takes 2-3 minutes)...${NC}"

# Extract ISO
xorriso -osirrox on -indev "$ISO_FILE" -extract / "$WORK_DIR" 2>&1 | grep -v "^xorriso" || true

# Make writable
chmod -R u+w "$WORK_DIR"

echo -e "${GREEN}✓ ISO extracted${NC}"

echo ""
echo -e "${GREEN}Step 2: Adding answer file to ISO...${NC}"

# Copy answer file to root of ISO
if [ -f "proxmox-auto-install-answer.toml" ]; then
    cp "proxmox-auto-install-answer.toml" "$WORK_DIR/answer.toml"
    echo "✓ Answer file added: answer.toml"
else
    echo -e "${RED}Error: proxmox-auto-install-answer.toml not found!${NC}"
    rm -rf "$WORK_DIR"
    exit 1
fi

# Copy post-install script
if [ -f "proxmox-post-install.sh" ]; then
    cp "proxmox-post-install.sh" "$WORK_DIR/"
    echo "✓ Post-install script added"
fi

echo ""
echo -e "${GREEN}Step 3: Modifying GRUB configuration for auto-install...${NC}"

# Find GRUB config file
GRUB_CFG="$WORK_DIR/boot/grub/grub.cfg"

if [ ! -f "$GRUB_CFG" ]; then
    echo -e "${RED}Error: GRUB config not found at $GRUB_CFG${NC}"
    rm -rf "$WORK_DIR"
    exit 1
fi

# Backup original GRUB config
cp "$GRUB_CFG" "$GRUB_CFG.original"

# Create new GRUB config with auto-install as default
cat > "$GRUB_CFG" <<'GRUBEOF'
set default=0
set timeout=3

loadfont unicode

set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

menuentry 'Install Proxmox VE (Automated)' {
    linux /boot/linux26 auto-install-cfg=partition ro quiet splash=silent
    initrd /boot/initrd.img
}

menuentry 'Install Proxmox VE (Manual - Debug)' {
    linux /boot/linux26 ro quiet
    initrd /boot/initrd.img
}

menuentry 'Install Proxmox VE (Console Mode)' {
    linux /boot/linux26 ro console=tty0
    initrd /boot/initrd.img
}

menuentry 'Advanced Options' {
    linux /boot/linux26 ro
    initrd /boot/initrd.img
}

menuentry 'Rescue Boot' {
    linux /boot/linux26 ro rescue
    initrd /boot/initrd.img
}
GRUBEOF

echo "✓ GRUB config modified"
echo "  - Default: Auto-install (3 second timeout)"
echo "  - Boot parameter: auto-install-cfg=partition"

echo ""
echo -e "${GREEN}Step 4: Creating modified bootable ISO...${NC}"

# Create new ISO with modifications
MODIFIED_ISO="/tmp/proxmox-auto-$$.iso"

# Find the isolinux and EFI files
ISOLINUX_BIN="$WORK_DIR/boot/isolinux/isolinux.bin"
ISOLINUX_CAT="$WORK_DIR/boot/isolinux/boot.cat"
EFI_IMG="$WORK_DIR/boot/grub/efi.img"

# Check if files exist
if [ ! -f "$ISOLINUX_BIN" ]; then
    echo -e "${YELLOW}Warning: isolinux.bin not found, trying alternative path...${NC}"
    ISOLINUX_BIN=$(find "$WORK_DIR" -name "isolinux.bin" | head -1)
fi

if [ ! -f "$EFI_IMG" ]; then
    echo -e "${YELLOW}Warning: efi.img not found, trying alternative path...${NC}"
    EFI_IMG=$(find "$WORK_DIR" -name "efi.img" | head -1)
fi

echo "Creating ISO (this takes 1-2 minutes)..."

# Create ISO with hybrid boot support
xorriso -as mkisofs \
    -o "$MODIFIED_ISO" \
    -V "PROXMOX_AUTO" \
    -r -J \
    -b boot/isolinux/isolinux.bin \
    -c boot/isolinux/boot.cat \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    -eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin \
    "$WORK_DIR" 2>&1 | grep -E "(Writing|xorriso.*done)" || true

if [ ! -f "$MODIFIED_ISO" ]; then
    echo -e "${RED}Error: Failed to create modified ISO${NC}"
    rm -rf "$WORK_DIR"
    exit 1
fi

echo -e "${GREEN}✓ Modified ISO created: $MODIFIED_ISO${NC}"

ISO_SIZE=$(du -h "$MODIFIED_ISO" | cut -f1)
echo "  Size: $ISO_SIZE"

echo ""
echo -e "${GREEN}Step 5: Writing modified ISO to USB...${NC}"

# Write to USB
dd if="$MODIFIED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=sync conv=fsync

sync
sleep 2

echo -e "${GREEN}✓ USB written${NC}"

echo ""
echo -e "${GREEN}Step 6: Making ISO hybrid bootable...${NC}"

# Make hybrid (if isohybrid is available)
if command -v isohybrid &> /dev/null; then
    isohybrid "$USB_DEVICE" 2>/dev/null || echo "  (isohybrid already applied)"
fi

sync

echo ""
echo -e "${GREEN}Step 7: Cleanup...${NC}"

# Cleanup
rm -rf "$WORK_DIR"
rm -f "$MODIFIED_ISO"

echo -e "${GREEN}✓ Cleanup complete${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  AUTOMATED USB READY!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}What happens on boot:${NC}"
echo "  1. Boot screen appears (3 second timeout)"
echo "  2. Auto-selects: 'Install Proxmox VE (Automated)'"
echo "  3. Reads answer.toml from USB"
echo "  4. Installs completely automatically:"
echo "     - Partitions SSD (/dev/sda)"
echo "     - Installs Proxmox VE"
echo "     - Configures network (DHCP)"
echo "     - Sets root password (from answer file)"
echo "     - Reboots automatically"
echo "  5. Total time: ~10-15 minutes"
echo ""
echo -e "${YELLOW}Dell XPS L701X Boot Instructions:${NC}"
echo "  1. Insert USB into laptop"
echo "  2. Press F12 during boot"
echo "  3. Select USB drive"
echo "  4. Press Enter when you see 'Install Proxmox VE (Automated)'"
echo "  5. Walk away - it will complete automatically!"
echo ""
echo -e "${BLUE}After installation:${NC}"
echo "  1. System reboots automatically"
echo "  2. SSH to Proxmox: ssh root@<ip>"
echo "  3. Find IP with: ip addr show"
echo "  4. Run: bash /root/proxmox-post-install.sh"
echo "     (or copy from USB ANSWERFILE partition)"
echo ""
echo -e "${GREEN}Configuration in answer file:${NC}"
grep -E "^(country|timezone|root_password)" proxmox-auto-install-answer.toml 2>/dev/null || echo "  Check proxmox-auto-install-answer.toml"
echo ""
