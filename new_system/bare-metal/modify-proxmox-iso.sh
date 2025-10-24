#!/bin/bash
#
# modify-proxmox-iso.sh - Modify Proxmox ISO to enable auto-installer by default
#
# PROBLEM: GRUB loads /boot/grub/grub.cfg from HFS+ partition which checks
#          for auto-installer-mode.toml file. File is on ISO9660 layer, not HFS+.
#
# SOLUTION: Modify /boot/grub/grub.cfg to ALWAYS enable auto-installer menu
#           without file check, then rebuild ISO.
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_error() { echo -e "${RED}✗ $1${NC}" >&2; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_info() { echo -e "${YELLOW}→ $1${NC}"; }

# Check dependencies
for cmd in xorriso isoinfo; do
    if ! command -v "$cmd" &>/dev/null; then
        print_error "Required command not found: $cmd"
        print_error "Install with: sudo apt install xorriso"
        exit 1
    fi
done

# Usage
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <input-iso> <output-iso>"
    echo ""
    echo "Example:"
    echo "  $0 proxmox-ve_9.0-1.iso proxmox-ve_9.0-1-autoinstall.iso"
    exit 1
fi

INPUT_ISO="$1"
OUTPUT_ISO="$2"

if [[ ! -f "$INPUT_ISO" ]]; then
    print_error "Input ISO not found: $INPUT_ISO"
    exit 1
fi

if [[ -f "$OUTPUT_ISO" ]]; then
    print_error "Output ISO already exists: $OUTPUT_ISO"
    read -p "Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    rm -f "$OUTPUT_ISO"
fi

print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_info "Modifying Proxmox ISO for Auto-Installer"
print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_info ""
print_info "Input:  $INPUT_ISO"
print_info "Output: $OUTPUT_ISO"
print_info ""

# Create temp directory
TEMP_DIR=$(mktemp -d -t proxmox-iso-mod.XXXX)
trap "rm -rf '$TEMP_DIR'" EXIT

print_info "Extracting ISO to temporary directory..."
ISO_EXTRACT="$TEMP_DIR/iso"
mkdir -p "$ISO_EXTRACT"

# Extract ISO
xorriso -osirrox on -indev "$INPUT_ISO" -extract / "$ISO_EXTRACT" 2>&1 | grep -v "^xorriso" || true

print_success "ISO extracted to $ISO_EXTRACT"

# Find and modify grub.cfg
GRUB_CFG="$ISO_EXTRACT/boot/grub/grub.cfg"

if [[ ! -f "$GRUB_CFG" ]]; then
    print_error "GRUB config not found: $GRUB_CFG"
    exit 1
fi

print_info "Original GRUB config:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
head -60 "$GRUB_CFG" | grep -A 15 "if \[ -f auto-installer-mode.toml \]" || echo "(auto-installer section not found)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_info "Modifying GRUB config to enable auto-installer by default..."

# Backup original
cp "$GRUB_CFG" "$GRUB_CFG.original"

# Modify: Remove the 'if [ -f auto-installer-mode.toml ]' check
# Make auto-installer menu ALWAYS available and set as default

cat > "$GRUB_CFG.new" << 'GRUB_NEW_EOF'
insmod gzio
insmod iso9660

if [ x$feature_default_font_path = xy ] ; then
   font=unicode
else
   font=$prefix/unicode.pf2
fi

set gfxmode=1024x768,640x480
# set kernel parameter vga=791
# do not specify color depth here (else efifb can fall back to 800x600)
set gfxpayload=1024x768
#set gfxmode=auto
#set gfxpayload=keep

if loadfont $font; then
    if test "${grub_platform}" = "efi"; then
        insmod efi_gop
        insmod efi_uga
    fi
    insmod video_bochs
    insmod video_cirrus
    insmod all_video
    insmod png
    insmod gfxterm
    set theme=/boot/grub/pvetheme/theme.txt
    export theme
    terminal_input console
    terminal_output gfxterm
fi

# Enable serial console
insmod serial
# FIXME: add below to our fixed-modules for next shim-review
insmod usbserial_common
insmod usbserial_ftdi
insmod usbserial_pl2303
insmod usbserial_usbdebug
if serial --unit=0 --speed=115200; then
    terminal_input --append serial
    terminal_output --append serial
    set show_serial_entry=y
fi

# AUTO-INSTALLER ENABLED BY DEFAULT (modified by modify-proxmox-iso.sh)
# Original check removed: if [ -f auto-installer-mode.toml ]; then
set timeout_style=menu
set timeout=10
set default=0

menuentry 'Install Proxmox VE (Automated)' --class debian --class gnu-linux --class gnu --class os {
    echo        'Loading Proxmox VE Automatic Installer ...'
    linux       /boot/linux26 ro ramdisk_size=16777216 rw quiet splash=silent proxmox-start-auto-installer
    echo        'Loading initial ramdisk ...'
    initrd      /boot/initrd.img
}

menuentry 'Install Proxmox VE (Graphical)' --class debian --class gnu-linux --class gnu --class os {
    echo	'Loading Proxmox VE Installer ...'
    linux	/boot/linux26 ro ramdisk_size=16777216 rw quiet splash=silent
    echo	'Loading initial ramdisk ...'
    initrd	/boot/initrd.img
}

menuentry 'Install Proxmox VE (Terminal UI)' --class debian --class gnu-linux --class gnu --class os {
    set background_color=black
    echo    'Loading Proxmox VE Console Installer ...'
    gfxpayload=800x600x16,800x600
    linux   /boot/linux26 ro ramdisk_size=16777216 rw quiet splash=silent proxtui
    echo    'Loading initial ramdisk ...'
    initrd  /boot/initrd.img
}

if [ x"${show_serial_entry}" == 'xy' ]; then
    menuentry 'Install Proxmox VE (Terminal UI, Serial Console)' --class debian --class gnu-linux --class gnu --class os {
        echo	'Loading Proxmox Console Installer (serial) ...'
        linux	/boot/linux26 ro ramdisk_size=16777216 rw splash=verbose proxtui console=ttyS0,115200
        echo	'Loading initial ramdisk ...'
        initrd	/boot/initrd.img
    }
fi

menuentry 'Install Proxmox VE (Debug Mode)' --class debian --class gnu-linux --class gnu --class os {
    echo	'Loading Proxmox VE Installer (Debug) ...'
    linux	/boot/linux26 ro ramdisk_size=16777216 rw splash=verbose proxdebug
    echo	'Loading initial ramdisk ...'
    initrd	/boot/initrd.img
}
GRUB_NEW_EOF

# Replace grub.cfg
mv "$GRUB_CFG.new" "$GRUB_CFG"
print_success "GRUB config modified"

print_info "Modified GRUB config:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
head -70 "$GRUB_CFG" | grep -A 15 "AUTO-INSTALLER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Rebuild ISO
print_info "Rebuilding ISO with modified GRUB config..."

# Get ISO info from original
ISO_LABEL=$(isoinfo -d -i "$INPUT_ISO" | grep "Volume id:" | cut -d: -f2 | xargs)
print_info "ISO Label: $ISO_LABEL"

# Extract MBR from original ISO for --grub2-mbr
dd if="$INPUT_ISO" bs=1 count=432 of="$TEMP_DIR/isohdpfx.bin" 2>/dev/null

# Rebuild with xorriso (hybrid BIOS/UEFI bootable)
# Parameters copied from original ISO structure
xorriso -as mkisofs \
    -o "$OUTPUT_ISO" \
    -V "$ISO_LABEL" \
    -J -joliet-long -r \
    --grub2-mbr "$TEMP_DIR/isohdpfx.bin" \
    --protective-msdos-label \
    -partition_cyl_align off \
    -partition_offset 0 \
    -partition_hd_cyl 98 \
    -partition_sec_hd 32 \
    -apm-block-size 2048 \
    -hfsplus \
    -efi-boot-part --efi-boot-image \
    -c '/boot/boot.cat' \
    -b '/boot/grub/i386-pc/eltorito.img' \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    --grub2-boot-info \
    -eltorito-alt-boot \
    -e '/efi.img' \
    -no-emul-boot \
    -boot-load-size 16384 \
    "$ISO_EXTRACT" \
    2>&1 | grep -v "^xorriso" || true

if [[ -f "$OUTPUT_ISO" ]]; then
    print_success "ISO rebuilt successfully: $OUTPUT_ISO"

    # Show file sizes
    INPUT_SIZE=$(du -h "$INPUT_ISO" | cut -f1)
    OUTPUT_SIZE=$(du -h "$OUTPUT_ISO" | cut -f1)

    echo ""
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_success "ISO Modification Complete!"
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_info "Original ISO: $INPUT_SIZE"
    print_info "Modified ISO: $OUTPUT_SIZE"
    echo ""
    print_info "Changes:"
    print_success "  • Auto-installer menu enabled by default"
    print_success "  • Removed file check: if [ -f auto-installer-mode.toml ]"
    print_success "  • Auto-installer set as default (option 0, timeout 10 sec)"
    echo ""
    print_info "Next steps:"
    print_info "  1. Prepare answer.toml and run proxmox-auto-install-assistant:"
    print_info "     proxmox-auto-install-assistant prepare-iso $OUTPUT_ISO --fetch-from iso --answer-file answer.toml"
    print_info ""
    print_info "  2. Create USB with modified ISO:"
    print_info "     sudo ./create-uefi-autoinstall-proxmox-usb.sh <prepared-iso> answer.toml /dev/sdX"
else
    print_error "Failed to rebuild ISO"
    exit 1
fi
