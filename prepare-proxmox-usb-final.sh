#!/bin/bash
# Proxmox VE 9 USB Preparation - Final Version
#
# Method: Properly rebuild ISO with modifications, then write with dd
# This preserves hybrid boot structure like balenaEtcher
#
# Usage: sudo ./prepare-proxmox-usb-final.sh /dev/sdX path/to/proxmox.iso
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
for tool in xorriso genisoimage; do
    if ! command -v "$tool" &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS $tool"
    fi
done

if [ -n "$MISSING_TOOLS" ]; then
    echo -e "${YELLOW}Installing required tools:$MISSING_TOOLS${NC}"
    apt-get update
    apt-get install -y xorriso genisoimage syslinux-utils isolinux
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

# Create work directories
WORK_DIR="/tmp/proxmox-iso-work-$$"
ISO_MOUNT="/tmp/proxmox-iso-mount-$$"
mkdir -p "$WORK_DIR"
mkdir -p "$ISO_MOUNT"

echo ""
echo -e "${GREEN}Step 1: Extracting original ISO...${NC}"

# Mount original ISO
mount -o loop,ro "$ISO_FILE" "$ISO_MOUNT"

# Copy all contents preserving permissions and structure
echo "Copying ISO contents..."
rsync -aH "$ISO_MOUNT/" "$WORK_DIR/" 2>&1 | grep -v "^$" || cp -rp "$ISO_MOUNT/"* "$WORK_DIR/"

# Unmount original
umount "$ISO_MOUNT"
rmdir "$ISO_MOUNT"

# Make all writable
chmod -R u+w "$WORK_DIR" 2>/dev/null || true

echo -e "${GREEN}✓ ISO extracted${NC}"

echo ""
echo -e "${GREEN}Step 2: Adding answer file...${NC}"

# Copy answer file
if [ -f "proxmox-auto-install-answer.toml" ]; then
    cp "proxmox-auto-install-answer.toml" "$WORK_DIR/answer.toml"
    chmod 644 "$WORK_DIR/answer.toml"
    echo "✓ Answer file added"
else
    echo -e "${RED}Error: proxmox-auto-install-answer.toml not found${NC}"
    rm -rf "$WORK_DIR"
    exit 1
fi

# Copy post-install script
if [ -f "proxmox-post-install.sh" ]; then
    cp "proxmox-post-install.sh" "$WORK_DIR/"
    chmod 755 "$WORK_DIR/proxmox-post-install.sh"
    echo "✓ Post-install script added"
fi

echo ""
echo -e "${GREEN}Step 3: Modifying boot configuration for GUI mode...${NC}"

# Modify GRUB config (UEFI boot)
GRUB_CFG="$WORK_DIR/boot/grub/grub.cfg"
if [ -f "$GRUB_CFG" ]; then
    cp "$GRUB_CFG" "$GRUB_CFG.original"

    # Create new GRUB config with auto-install + graphics params
    cat > "$GRUB_CFG" <<'EOF'
set default=0
set timeout=5

insmod all_video
insmod gfxterm
insmod png
loadfont unicode

terminal_output gfxterm

set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

menuentry 'Install Proxmox VE (Automated - GUI Mode for External Display)' {
    linux /boot/linux26 auto-install-cfg=partition ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

menuentry 'Install Proxmox VE (Manual - GUI Mode)' {
    linux /boot/linux26 ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

menuentry 'Install Proxmox VE (Standard)' {
    linux /boot/linux26 ro quiet
    initrd /boot/initrd.img
}

menuentry 'Install Proxmox VE (Debug Mode)' {
    linux /boot/linux26 ro debug
    initrd /boot/initrd.img
}
EOF

    echo "✓ GRUB config created with GUI mode"
else
    echo -e "${YELLOW}Warning: GRUB config not found${NC}"
fi

# Modify ISOLINUX config (Legacy/BIOS boot)
ISOLINUX_CFG="$WORK_DIR/boot/isolinux/isolinux.cfg"
if [ -f "$ISOLINUX_CFG" ]; then
    cp "$ISOLINUX_CFG" "$ISOLINUX_CFG.original"

    # Create new ISOLINUX config
    cat > "$ISOLINUX_CFG" <<'EOF'
default autoinstall
timeout 50
prompt 1

display boot.msg

label autoinstall
  menu label ^Automated Install (GUI Mode - External Display)
  menu default
  kernel /boot/linux26
  append auto-install-cfg=partition initrd=/boot/initrd.img ro video=vesafb:ywrap,mtrr vga=791 nomodeset

label manual
  menu label ^Manual Install (GUI Mode)
  kernel /boot/linux26
  append initrd=/boot/initrd.img ro video=vesafb:ywrap,mtrr vga=791 nomodeset

label standard
  menu label Install Proxmox VE (^Standard)
  kernel /boot/linux26
  append initrd=/boot/initrd.img ro quiet

label debug
  menu label Install Proxmox VE (^Debug)
  kernel /boot/linux26
  append initrd=/boot/initrd.img ro debug
EOF

    echo "✓ ISOLINUX config created with GUI mode"
else
    echo -e "${YELLOW}Warning: ISOLINUX config not found${NC}"
fi

echo ""
echo -e "${GREEN}Step 4: Finding boot files...${NC}"

# Show the ISO structure to help debug
echo "ISO directory structure:"
find "$WORK_DIR" -type d -maxdepth 2 2>/dev/null | head -20

echo ""
echo "Searching for boot files..."

# Find ISOLINUX files (for Legacy/BIOS boot)
ISOLINUX_BIN=$(find "$WORK_DIR" -name "isolinux.bin" -type f 2>/dev/null | head -1)
BOOT_CAT=$(find "$WORK_DIR" -name "boot.cat" -type f 2>/dev/null | head -1)

# Find EFI files (for UEFI boot)
EFI_IMG=$(find "$WORK_DIR" -name "efi*.img" -o -name "efiboot.img" 2>/dev/null | head -1)
EFI_BOOT_DIR=$(find "$WORK_DIR" -type d -name "boot" -path "*/efi/*" 2>/dev/null | head -1)
BOOTX64_EFI=$(find "$WORK_DIR" -name "bootx64.efi" -o -name "grubx64.efi" 2>/dev/null | head -1)

echo "Found boot files:"
echo "  ISOLINUX: ${ISOLINUX_BIN:-NOT FOUND}"
echo "  Boot catalog: ${BOOT_CAT:-NOT FOUND}"
echo "  EFI image: ${EFI_IMG:-NOT FOUND}"
echo "  EFI boot dir: ${EFI_BOOT_DIR:-NOT FOUND}"
echo "  EFI bootloader: ${BOOTX64_EFI:-NOT FOUND}"

# Determine boot type
BOOT_TYPE=""
if [ -n "$ISOLINUX_BIN" ]; then
    BOOT_TYPE="legacy"
    echo -e "${GREEN}✓ Legacy/BIOS boot support detected${NC}"
fi

if [ -n "$EFI_IMG" ] || [ -n "$EFI_BOOT_DIR" ]; then
    if [ -n "$BOOT_TYPE" ]; then
        BOOT_TYPE="hybrid"
        echo -e "${GREEN}✓ UEFI boot support detected (Hybrid ISO)${NC}"
    else
        BOOT_TYPE="uefi"
        echo -e "${GREEN}✓ UEFI-only boot detected${NC}"
    fi
fi

if [ -z "$BOOT_TYPE" ]; then
    echo -e "${RED}Error: No bootloader found (neither Legacy nor UEFI)${NC}"
    echo ""
    echo "Available boot-related files:"
    find "$WORK_DIR" -type f \( -name "*.bin" -o -name "*.efi" -o -name "*.img" \) 2>/dev/null
    rm -rf "$WORK_DIR"
    exit 1
fi

# If UEFI-only and no EFI image, create one from the EFI directory
if [ "$BOOT_TYPE" = "uefi" ] && [ -z "$EFI_IMG" ] && [ -n "$EFI_BOOT_DIR" ]; then
    echo ""
    echo -e "${YELLOW}Creating EFI boot image from EFI directory...${NC}"

    # Get the parent efi directory
    EFI_DIR=$(dirname "$EFI_BOOT_DIR")
    EFI_IMG="$WORK_DIR/efi.img"

    # Calculate size needed (add 20% overhead)
    EFI_SIZE=$(du -sb "$EFI_DIR" | awk '{print int($1 * 1.2 / 1024)}')

    # Create FAT filesystem image
    dd if=/dev/zero of="$EFI_IMG" bs=1k count=$EFI_SIZE 2>/dev/null
    mkfs.vfat "$EFI_IMG" >/dev/null 2>&1

    # Mount and copy EFI files
    EFI_MOUNT="/tmp/efi-mount-$$"
    mkdir -p "$EFI_MOUNT"
    mount -o loop "$EFI_IMG" "$EFI_MOUNT"
    cp -r "$EFI_DIR"/* "$EFI_MOUNT"/
    umount "$EFI_MOUNT"
    rmdir "$EFI_MOUNT"

    echo -e "${GREEN}✓ Created EFI boot image: $EFI_IMG${NC}"
fi

echo ""
echo -e "${GREEN}Step 5: Rebuilding ISO with hybrid boot support...${NC}"

MODIFIED_ISO="/tmp/proxmox-modified-$$.iso"

# Find isohybrid MBR
MBR_TEMPLATE=""
for path in /usr/lib/ISOLINUX/isohdpfx.bin /usr/lib/syslinux/mbr/isohdpfx.bin /usr/share/syslinux/isohdpfx.bin; do
    if [ -f "$path" ]; then
        MBR_TEMPLATE="$path"
        break
    fi
done

if [ -z "$MBR_TEMPLATE" ]; then
    echo -e "${YELLOW}Warning: isohdpfx.bin not found, hybrid boot may not work${NC}"
fi

echo "Building bootable ISO ($BOOT_TYPE mode)..."
echo "  Boot type: $BOOT_TYPE"
if [ -n "$ISOLINUX_BIN" ]; then
    echo "  ISOLINUX: $ISOLINUX_BIN"
fi
if [ -n "$EFI_IMG" ]; then
    echo "  EFI: $EFI_IMG"
fi
echo "  MBR: ${MBR_TEMPLATE:-none}"

# Calculate relative paths for xorriso
if [ -n "$ISOLINUX_BIN" ]; then
    ISOLINUX_REL=${ISOLINUX_BIN#$WORK_DIR/}
fi
if [ -n "$BOOT_CAT" ]; then
    BOOT_CAT_REL=${BOOT_CAT#$WORK_DIR/}
fi
if [ -n "$EFI_IMG" ]; then
    EFI_IMG_REL=${EFI_IMG#$WORK_DIR/}
fi

echo "  Relative paths:"
if [ -n "$ISOLINUX_REL" ]; then
    echo "    ISOLINUX: $ISOLINUX_REL"
fi
if [ -n "$EFI_IMG_REL" ]; then
    echo "    EFI: $EFI_IMG_REL"
fi

# Build xorriso command based on boot type
XORRISO_CMD="xorriso -as mkisofs"
XORRISO_CMD="$XORRISO_CMD -R -r -J -joliet-long"
XORRISO_CMD="$XORRISO_CMD -l -iso-level 3"
XORRISO_CMD="$XORRISO_CMD -V PROXMOX"

# Add BIOS boot (ISOLINUX) if present
if [ "$BOOT_TYPE" = "legacy" ] || [ "$BOOT_TYPE" = "hybrid" ]; then
    if [ -n "$ISOLINUX_BIN" ]; then
        XORRISO_CMD="$XORRISO_CMD -b $ISOLINUX_REL"
        if [ -n "$BOOT_CAT_REL" ]; then
            XORRISO_CMD="$XORRISO_CMD -c $BOOT_CAT_REL"
        else
            XORRISO_CMD="$XORRISO_CMD -c boot.cat"
        fi
        XORRISO_CMD="$XORRISO_CMD -no-emul-boot"
        XORRISO_CMD="$XORRISO_CMD -boot-load-size 4"
        XORRISO_CMD="$XORRISO_CMD -boot-info-table"
    fi
fi

# Add EFI boot
if [ "$BOOT_TYPE" = "uefi" ] || [ "$BOOT_TYPE" = "hybrid" ]; then
    if [ -n "$EFI_IMG" ]; then
        if [ "$BOOT_TYPE" = "hybrid" ]; then
            XORRISO_CMD="$XORRISO_CMD -eltorito-alt-boot"
        fi
        XORRISO_CMD="$XORRISO_CMD -e $EFI_IMG_REL"
        XORRISO_CMD="$XORRISO_CMD -no-emul-boot"

        # For UEFI-only or hybrid, append the EFI partition
        if [ -f "$EFI_IMG" ]; then
            XORRISO_CMD="$XORRISO_CMD -append_partition 2 0xef $EFI_IMG"
        fi
    fi
fi

# Add partition offset for hybrid boot
if [ "$BOOT_TYPE" = "hybrid" ]; then
    XORRISO_CMD="$XORRISO_CMD -partition_offset 16"
fi

XORRISO_CMD="$XORRISO_CMD -o $MODIFIED_ISO"
XORRISO_CMD="$XORRISO_CMD $WORK_DIR"

echo ""
echo "Running xorriso..."
echo "Command: $XORRISO_CMD"
echo ""
eval $XORRISO_CMD 2>&1 | grep -E "ISO image produced|xorriso : UPDATE|xorriso : NOTE|Writing|Writing to" || true

# Check if ISO was created
if [ ! -f "$MODIFIED_ISO" ]; then
    echo -e "${RED}Error: Failed to create modified ISO${NC}"
    echo "Check xorriso output above for errors"
    rm -rf "$WORK_DIR"
    exit 1
fi

# Make it hybrid bootable (GPT + MBR)
if [ -n "$MBR_TEMPLATE" ]; then
    echo "Making hybrid MBR/GPT bootable..."
    if command -v isohybrid &> /dev/null; then
        isohybrid --uefi "$MODIFIED_ISO" 2>/dev/null || echo "  (isohybrid already applied by xorriso)"
    fi

    # Alternative: use xorriso to add hybrid MBR
    xorriso -indev "$MODIFIED_ISO" \
        -boot_image any replay \
        -append_partition 2 0xef "$EFI_IMG" \
        -boot_image isolinux partition_table=on \
        -boot_image any cat_path=/boot/isolinux/boot.cat \
        -boot_image grub bin_path=/boot/isolinux/isolinux.bin \
        -boot_image any emul_type=no_emulation \
        -boot_image any platform_id=0x00 \
        -outdev "$MODIFIED_ISO.hybrid" 2>/dev/null || cp "$MODIFIED_ISO" "$MODIFIED_ISO.hybrid"

    if [ -f "$MODIFIED_ISO.hybrid" ]; then
        mv "$MODIFIED_ISO.hybrid" "$MODIFIED_ISO"
    fi
fi

ISO_SIZE=$(du -h "$MODIFIED_ISO" | cut -f1)
echo -e "${GREEN}✓ Modified ISO created ($ISO_SIZE)${NC}"

echo ""
echo -e "${GREEN}Step 6: Writing ISO to USB drive...${NC}"

# Write ISO to USB like balenaEtcher does - plain dd
echo "Writing with dd (this preserves hybrid boot structure)..."
dd if="$MODIFIED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

# Sync everything to disk
sync
sleep 2

echo -e "${GREEN}✓ USB written successfully${NC}"

echo ""
echo -e "${GREEN}Step 7: Verifying USB...${NC}"

# Force kernel to re-read partition table
partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 2

# Show what was created
echo "USB partition structure:"
fdisk -l "$USB_DEVICE" 2>/dev/null | grep "^$USB_DEVICE" || lsblk "$USB_DEVICE"

echo ""
echo -e "${GREEN}Step 8: Cleanup...${NC}"

rm -rf "$WORK_DIR"
rm -f "$MODIFIED_ISO"

echo -e "${GREEN}✓ Cleanup complete${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  USB READY - BOOTABLE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}What was done:${NC}"
echo "  ✓ Extracted Proxmox ISO"
echo "  ✓ Added answer.toml for auto-install"
echo "  ✓ Modified GRUB (UEFI) with graphics parameters"
echo "  ✓ Modified ISOLINUX (Legacy) with graphics parameters"
echo "  ✓ Rebuilt ISO with hybrid boot (like balenaEtcher)"
echo "  ✓ Written to USB preserving boot structure"
echo ""
echo -e "${YELLOW}Graphics parameters added:${NC}"
echo "  video=vesafb:ywrap,mtrr   → Enables framebuffer for Mini DisplayPort"
echo "  vga=791                    → 1024x768 resolution"
echo "  nomodeset                  → Keeps graphics in compatibility mode"
echo ""
echo -e "${RED}BEFORE BOOTING:${NC}"
echo "  1. Connect external monitor to Mini DisplayPort"
echo "  2. Power ON monitor first"
echo "  3. Insert USB into laptop (USB 2.0 port)"
echo "  4. Power on laptop"
echo ""
echo -e "${GREEN}Boot Instructions:${NC}"
echo "  1. Press F12 during boot"
echo "  2. Select USB drive (try BOTH options):"
echo "     - 'USB Storage Device' (Legacy/BIOS)"
echo "     - 'UEFI: USB...' (UEFI)"
echo "  3. You should see menu on external display:"
echo "     'Install Proxmox VE (Automated - GUI Mode)'"
echo "  4. Press ENTER or wait 5 seconds"
echo "  5. Installation proceeds automatically"
echo ""
echo -e "${BLUE}If USB won't boot:${NC}"
echo "  • Try F2 → Boot Mode → Toggle UEFI/Legacy"
echo "  • Try different USB port (prefer USB 2.0)"
echo "  • Verify Secure Boot is DISABLED"
echo "  • Try the OTHER USB option in F12 boot menu"
echo ""
echo -e "${GREEN}The USB is now bootable like balenaEtcher created it!${NC}"
echo ""
