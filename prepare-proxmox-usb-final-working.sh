#!/bin/bash
# Proxmox VE 9 USB - Final Working Version
#
# Strategy: Rebuild ISO properly (like original) with modifications embedded
# Then write with dd to preserve boot structure
#
# Usage: sudo ./prepare-proxmox-usb-final-working.sh /dev/sdX path/to/proxmox.iso

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

# Check tools
for tool in xorriso mkisofs; do
    if ! command -v "$tool" &> /dev/null; then
        echo "Installing $tool..."
        apt-get update && apt-get install -y xorriso genisoimage
        break
    fi
done

echo ""
echo -e "${YELLOW}WARNING: This will ERASE $USB_DEVICE${NC}"
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes': " confirm
[ "$confirm" != "yes" ] && exit 0

umount "${USB_DEVICE}"* 2>/dev/null || true

WORK_DIR="/tmp/pve-iso-$$"
ISO_MOUNT="/tmp/pve-mount-$$"
mkdir -p "$WORK_DIR" "$ISO_MOUNT"

echo ""
echo -e "${GREEN}[1/6] Extracting ISO...${NC}"

mount -o loop,ro "$ISO_FILE" "$ISO_MOUNT"
rsync -aH "$ISO_MOUNT/" "$WORK_DIR/" 2>&1 | grep -v "^$" || cp -a "$ISO_MOUNT/"* "$WORK_DIR/"
umount "$ISO_MOUNT"
rmdir "$ISO_MOUNT"
chmod -R u+w "$WORK_DIR" 2>/dev/null || true

echo -e "${GREEN}✓ Extracted${NC}"

echo ""
echo -e "${GREEN}[2/6] Adding answer file...${NC}"

if [ ! -f "proxmox-auto-install-answer.toml" ]; then
    echo -e "${RED}Error: proxmox-auto-install-answer.toml not found${NC}"
    rm -rf "$WORK_DIR"
    exit 1
fi

cp "proxmox-auto-install-answer.toml" "$WORK_DIR/answer.toml"
[ -f "proxmox-post-install.sh" ] && cp "proxmox-post-install.sh" "$WORK_DIR/"

echo -e "${GREEN}✓ Files added${NC}"

echo ""
echo -e "${GREEN}[3/6] Modifying GRUB for auto-install + graphics...${NC}"

# Find GRUB config
GRUB_CFG=$(find "$WORK_DIR" -name "grub.cfg" -type f 2>/dev/null | head -1)

if [ -z "$GRUB_CFG" ]; then
    echo -e "${RED}Error: grub.cfg not found${NC}"
    rm -rf "$WORK_DIR"
    exit 1
fi

echo "Found: ${GRUB_CFG#$WORK_DIR/}"

# Backup
cp "$GRUB_CFG" "$GRUB_CFG.original"

# Create new GRUB config with auto-install as default
cat > "$GRUB_CFG" <<'GRUBEOF'
set default=0
set timeout=3

insmod all_video
insmod gfxterm
insmod png
loadfont unicode

terminal_output gfxterm

set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

menuentry 'Proxmox VE - Automated Install (GUI Mode)' {
    linux /boot/linux26 auto-install-cfg=partition ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Install (GUI Mode)' {
    linux /boot/linux26 ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Install (Standard)' {
    linux /boot/linux26 ro quiet
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Advanced Options' {
    linux /boot/linux26 ro
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Rescue Boot' {
    linux /boot/linux26 ro rescue
    initrd /boot/initrd.img
}
GRUBEOF

echo -e "${GREEN}✓ GRUB modified (auto-install + GUI graphics)${NC}"

echo ""
echo -e "${GREEN}[4/6] Finding boot files...${NC}"

# Find EFI boot image
EFI_IMG=$(find "$WORK_DIR" -name "efi*.img" -o -name "efiboot.img" 2>/dev/null | head -1)
EFI_BOOT_DIR=$(find "$WORK_DIR" -type d -path "*/efi/boot" 2>/dev/null | head -1)

if [ -z "$EFI_IMG" ] && [ -n "$EFI_BOOT_DIR" ]; then
    echo "Creating EFI boot image..."
    EFI_DIR=$(dirname "$EFI_BOOT_DIR")
    EFI_IMG="$WORK_DIR/efiboot.img"
    EFI_SIZE=$(du -sb "$EFI_DIR" | awk '{print int($1 * 1.3 / 1024)}')

    dd if=/dev/zero of="$EFI_IMG" bs=1k count=$EFI_SIZE 2>/dev/null
    mkfs.vfat "$EFI_IMG" >/dev/null 2>&1

    EFI_MOUNT="/tmp/efi-$$"
    mkdir -p "$EFI_MOUNT"
    mount -o loop "$EFI_IMG" "$EFI_MOUNT"
    cp -r "$EFI_DIR"/* "$EFI_MOUNT"/
    umount "$EFI_MOUNT"
    rmdir "$EFI_MOUNT"

    echo -e "${GREEN}✓ EFI image created${NC}"
fi

if [ -z "$EFI_IMG" ]; then
    echo -e "${RED}Error: No EFI boot method found${NC}"
    rm -rf "$WORK_DIR"
    exit 1
fi

echo "EFI image: ${EFI_IMG#$WORK_DIR/}"

echo ""
echo -e "${GREEN}[5/6] Rebuilding ISO...${NC}"

MODIFIED_ISO="/tmp/proxmox-auto-$$.iso"
EFI_IMG_REL="${EFI_IMG#$WORK_DIR/}"

# Build ISO with UEFI boot support
xorriso -as mkisofs \
    -R -r -J -joliet-long \
    -l -iso-level 3 \
    -V "PROXMOX" \
    -e "$EFI_IMG_REL" \
    -no-emul-boot \
    -append_partition 2 0xef "$EFI_IMG" \
    -partition_cyl_align all \
    -o "$MODIFIED_ISO" \
    "$WORK_DIR" 2>&1 | grep -E "xorriso.*done|ISO image produced" || true

if [ ! -f "$MODIFIED_ISO" ]; then
    echo -e "${RED}Error: ISO creation failed${NC}"
    rm -rf "$WORK_DIR"
    exit 1
fi

# Make it hybrid bootable (MBR + GPT)
if command -v isohybrid &> /dev/null; then
    isohybrid --uefi "$MODIFIED_ISO" 2>/dev/null || true
fi

ISO_SIZE=$(du -h "$MODIFIED_ISO" | cut -f1)
echo -e "${GREEN}✓ ISO created ($ISO_SIZE)${NC}"

echo ""
echo -e "${GREEN}[6/6] Writing to USB...${NC}"

# Write exactly like balenaEtcher
dd if="$MODIFIED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 2

echo -e "${GREEN}✓ USB written${NC}"

# Cleanup
rm -rf "$WORK_DIR"
rm -f "$MODIFIED_ISO"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  SUCCESS! USB READY${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}What was configured:${NC}"
echo "  ✓ Auto-install enabled (3 second timeout)"
echo "  ✓ Graphics parameters for external display"
echo "  ✓ Answer file embedded in ISO"
echo "  ✓ Bootable like balenaEtcher"
echo ""
echo -e "${YELLOW}Boot Instructions:${NC}"
echo ""
echo "  1. Connect external monitor to Mini DisplayPort"
echo "  2. Power ON monitor"
echo "  3. Insert USB, power on laptop"
echo "  4. Press F12 → Select 'UEFI: USB...'"
echo "  5. Wait 3 seconds OR press Enter"
echo "  6. Auto-install starts automatically!"
echo ""
echo -e "${GREEN}Installation will:${NC}"
echo "  - Show GUI on external display"
echo "  - Install to SSD (/dev/sda)"
echo "  - Configure network via DHCP"
echo "  - Set password from answer file"
echo "  - Reboot when done (~10-15 min)"
echo ""
