#!/bin/bash
# Proxmox VE 9 Fully Automated USB Preparation - V2
#
# Improved version with better ISO handling
#
# Usage: sudo ./prepare-proxmox-usb-auto-v2.sh /dev/sdX path/to/proxmox.iso
#

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
echo "Checking required tools..."
MISSING_TOOLS=""
for tool in xorriso; do
    if ! command -v "$tool" &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS $tool"
    fi
done

if [ -n "$MISSING_TOOLS" ]; then
    echo -e "${YELLOW}Installing required tools:$MISSING_TOOLS${NC}"
    apt-get update
    apt-get install -y xorriso syslinux-utils isolinux
fi

# Confirm
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

# Create work directory
WORK_DIR="/tmp/proxmox-iso-$$"
ISO_MOUNT="/tmp/proxmox-mount-$$"
mkdir -p "$WORK_DIR"
mkdir -p "$ISO_MOUNT"

echo ""
echo -e "${GREEN}Step 1: Mounting original ISO...${NC}"

# Mount original ISO
mount -o loop "$ISO_FILE" "$ISO_MOUNT"

echo -e "${GREEN}✓ ISO mounted${NC}"

echo ""
echo -e "${GREEN}Step 2: Copying ISO contents...${NC}"

# Copy all files
rsync -a "$ISO_MOUNT/" "$WORK_DIR/" 2>&1 | grep -v "^sending" || cp -a "$ISO_MOUNT/"* "$WORK_DIR/"

# Unmount original
umount "$ISO_MOUNT"
rmdir "$ISO_MOUNT"

# Make writable
chmod -R u+w "$WORK_DIR" 2>/dev/null || true

echo -e "${GREEN}✓ ISO contents copied${NC}"

echo ""
echo -e "${GREEN}Step 3: Adding answer file...${NC}"

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
echo -e "${GREEN}Step 4: Modifying GRUB configuration...${NC}"

# Find and modify GRUB config
GRUB_CFG="$WORK_DIR/boot/grub/grub.cfg"

if [ -f "$GRUB_CFG" ]; then
    cp "$GRUB_CFG" "$GRUB_CFG.backup"

    # Create modified GRUB config
    cat > "$GRUB_CFG" <<'GRUBEOF'
set default=0
set timeout=3

insmod all_video
insmod gfxterm
loadfont unicode

terminal_output gfxterm

set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

menuentry 'Install Proxmox VE (Automated - Press Enter)' {
    linux /boot/linux26 auto-install-cfg=partition ro quiet splash=silent
    initrd /boot/initrd.img
}

menuentry 'Install Proxmox VE (Manual)' {
    linux /boot/linux26 ro quiet
    initrd /boot/initrd.img
}

menuentry 'Install Proxmox VE (Debug Mode)' {
    linux /boot/linux26 ro debug
    initrd /boot/initrd.img
}

menuentry 'Advanced Options' {
    linux /boot/linux26 ro
    initrd /boot/initrd.img
}
GRUBEOF

    echo "✓ GRUB config modified (3s timeout, auto-install default)"
else
    echo -e "${YELLOW}Warning: GRUB config not found, trying alternative...${NC}"
fi

# Also modify ISOLINUX for BIOS boot
ISOLINUX_CFG="$WORK_DIR/boot/isolinux/isolinux.cfg"
if [ -f "$ISOLINUX_CFG" ]; then
    cp "$ISOLINUX_CFG" "$ISOLINUX_CFG.backup"

    sed -i 's/^timeout .*/timeout 30/' "$ISOLINUX_CFG"
    sed -i 's/^default .*/default auto/' "$ISOLINUX_CFG"

    # Add auto-install entry at the beginning
    sed -i '/^label /i label auto\n  menu label ^Automated Install (Press Enter)\n  kernel /boot/linux26\n  append auto-install-cfg=partition initrd=/boot/initrd.img ro quiet splash=silent\n' "$ISOLINUX_CFG"

    echo "✓ ISOLINUX config modified"
fi

echo ""
echo -e "${GREEN}Step 5: Creating bootable ISO...${NC}"

MODIFIED_ISO="/tmp/proxmox-auto-$$.iso"

# Get actual paths
ISOLINUX_BIN=$(find "$WORK_DIR" -name "isolinux.bin" 2>/dev/null | head -1)
EFI_IMG=$(find "$WORK_DIR" -name "efi.img" -o -name "efiboot.img" 2>/dev/null | head -1)

echo "  ISOLINUX: $ISOLINUX_BIN"
echo "  EFI IMG: $EFI_IMG"

# Determine if we have MBR file
MBR_FILE="/usr/lib/ISOLINUX/isohdpfx.bin"
if [ ! -f "$MBR_FILE" ]; then
    MBR_FILE="/usr/lib/syslinux/mbr/isohdpfx.bin"
fi
if [ ! -f "$MBR_FILE" ]; then
    MBR_FILE=$(find /usr -name "isohdpfx.bin" 2>/dev/null | head -1)
fi

echo "  MBR: $MBR_FILE"

# Build xorriso command
XORRISO_CMD="xorriso -as mkisofs -o $MODIFIED_ISO"
XORRISO_CMD="$XORRISO_CMD -V PROXMOX_AUTO"
XORRISO_CMD="$XORRISO_CMD -r -J"

# Add BIOS boot if isolinux exists
if [ -n "$ISOLINUX_BIN" ]; then
    ISOLINUX_DIR=$(dirname "$ISOLINUX_BIN")
    BOOT_CAT_REL="${ISOLINUX_DIR#$WORK_DIR/}/boot.cat"
    ISOLINUX_REL="${ISOLINUX_BIN#$WORK_DIR/}"

    XORRISO_CMD="$XORRISO_CMD -b $ISOLINUX_REL"
    XORRISO_CMD="$XORRISO_CMD -c $BOOT_CAT_REL"
    XORRISO_CMD="$XORRISO_CMD -no-emul-boot"
    XORRISO_CMD="$XORRISO_CMD -boot-load-size 4"
    XORRISO_CMD="$XORRISO_CMD -boot-info-table"
fi

# Add EFI boot
if [ -n "$EFI_IMG" ]; then
    EFI_REL="${EFI_IMG#$WORK_DIR/}"
    XORRISO_CMD="$XORRISO_CMD -eltorito-alt-boot"
    XORRISO_CMD="$XORRISO_CMD -e $EFI_REL"
    XORRISO_CMD="$XORRISO_CMD -no-emul-boot"
fi

# Add hybrid MBR if available
if [ -n "$MBR_FILE" ] && [ -f "$MBR_FILE" ]; then
    XORRISO_CMD="$XORRISO_CMD -isohybrid-mbr $MBR_FILE"
    XORRISO_CMD="$XORRISO_CMD -isohybrid-gpt-basdat"
fi

# Add source directory
XORRISO_CMD="$XORRISO_CMD $WORK_DIR"

echo "Creating ISO..."
echo "Command: $XORRISO_CMD"
echo ""

# Execute
eval $XORRISO_CMD 2>&1 | tee /tmp/xorriso-output.log | grep -E "(Writing|% done|xorriso : UPDATE|xorriso : NOTE)" || true

# Check if ISO was created
if [ ! -f "$MODIFIED_ISO" ]; then
    echo -e "${RED}Error: ISO creation failed${NC}"
    echo "Last 20 lines of xorriso output:"
    tail -20 /tmp/xorriso-output.log
    rm -rf "$WORK_DIR"
    exit 1
fi

ISO_SIZE=$(du -h "$MODIFIED_ISO" | cut -f1)
echo -e "${GREEN}✓ ISO created successfully ($ISO_SIZE)${NC}"

echo ""
echo -e "${GREEN}Step 6: Writing to USB drive...${NC}"

# Write to USB
dd if="$MODIFIED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
echo -e "${GREEN}✓ USB written${NC}"

echo ""
echo -e "${GREEN}Step 7: Cleanup...${NC}"

rm -rf "$WORK_DIR"
rm -f "$MODIFIED_ISO"
rm -f /tmp/xorriso-output.log

echo -e "${GREEN}✓ Done${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  AUTOMATED USB READY!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Boot Instructions (Dell XPS L701X):${NC}"
echo ""
echo "  1. Insert USB drive"
echo "  2. Press F12 during boot"
echo "  3. Select your USB drive"
echo "  4. Wait 3 seconds OR press Enter on:"
echo "     'Install Proxmox VE (Automated - Press Enter)'"
echo "  5. Installation runs automatically (~10-15 min)"
echo "  6. System reboots when complete"
echo ""
echo -e "${YELLOW}After installation:${NC}"
echo "  - Find IP: check your router or connect monitor"
echo "  - SSH: ssh root@<ip> (password from answer file)"
echo "  - Run: bash proxmox-post-install.sh"
echo ""
