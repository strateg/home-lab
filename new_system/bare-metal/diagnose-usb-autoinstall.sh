#!/usr/bin/env bash
#
# diagnose-usb-autoinstall.sh
# Comprehensive USB auto-installer diagnostics for Legacy BIOS
#
# Usage:
#   sudo ./diagnose-usb-autoinstall.sh /dev/sdc
#

set -euo pipefail

SCRIPT_NAME=$(basename "$0")
USB_DEVICE="${1:-}"
MOUNT_POINT=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

cleanup() {
    if [[ -n "${MOUNT_POINT:-}" && -d "$MOUNT_POINT" ]]; then
        if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
            umount "$MOUNT_POINT" 2>/dev/null || true
        fi
        rmdir "$MOUNT_POINT" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() { echo -e "  ${GREEN}✓${NC} $*"; }
print_error() { echo -e "  ${RED}✗${NC} $*"; }
print_warning() { echo -e "  ${YELLOW}⚠${NC} $*"; }
print_info() { echo "  $*"; }

check_root() {
    if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
        echo -e "${RED}ERROR: This script must be run as root (use sudo)${NC}"
        exit 1
    fi
}

usage() {
    echo "Usage: sudo $SCRIPT_NAME <usb-device>"
    echo "Example: sudo $SCRIPT_NAME /dev/sdc"
    exit 1
}

# Main diagnostics
main() {
    check_root

    if [[ -z "$USB_DEVICE" ]]; then
        usage
    fi

    if [[ ! -b "$USB_DEVICE" ]]; then
        echo -e "${RED}ERROR: $USB_DEVICE is not a block device${NC}"
        exit 1
    fi

    print_header "USB Auto-Installer Diagnostics"
    echo "Target device: $USB_DEVICE"
    echo "Date: $(date)"

    # ============================================================
    # Check 1: Device Information
    # ============================================================
    print_header "1. Device Information"

    echo "Basic info:"
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT "$USB_DEVICE" 2>/dev/null || print_error "Failed to read device info"

    echo ""
    echo "Partition table:"
    parted -s "$USB_DEVICE" print 2>/dev/null || print_error "Failed to read partition table"

    # ============================================================
    # Check 2: Bootloader Check
    # ============================================================
    print_header "2. Bootloader Check (MBR)"

    echo "Reading MBR boot signature..."
    local boot_sig=$(dd if="$USB_DEVICE" bs=1 skip=510 count=2 2>/dev/null | xxd -p)
    if [[ "$boot_sig" == "55aa" ]]; then
        print_success "MBR boot signature valid (0x55AA)"
    else
        print_error "MBR boot signature invalid or missing (found: 0x${boot_sig:-none})"
    fi

    echo ""
    echo "Checking for bootloader in MBR..."
    local mbr_code=$(dd if="$USB_DEVICE" bs=1 skip=0 count=446 2>/dev/null | xxd -l 64)
    if [[ -n "$mbr_code" ]]; then
        print_info "MBR code present (first 64 bytes):"
        echo "$mbr_code" | sed 's/^/    /'
    else
        print_error "No MBR code found"
    fi

    # ============================================================
    # Check 3: Filesystem Mount and Structure
    # ============================================================
    print_header "3. Filesystem Check"

    MOUNT_POINT=$(mktemp -d /tmp/usb-diag.XXXX)
    local mounted=0
    local mount_target=""

    # Try to mount first partition or whole device
    for target in "${USB_DEVICE}1" "${USB_DEVICE}"; do
        if [[ -b "$target" ]]; then
            if mount -o ro "$target" "$MOUNT_POINT" 2>/dev/null; then
                print_success "Mounted: $target → $MOUNT_POINT"
                mounted=1
                mount_target="$target"
                break
            fi
        fi
    done

    if [[ $mounted -eq 0 ]]; then
        print_error "Failed to mount USB filesystem"
        print_warning "Cannot continue with filesystem checks"
        return 1
    fi

    echo ""
    echo "Filesystem type:"
    df -T "$MOUNT_POINT" | tail -1

    echo ""
    echo "Root directory structure:"
    tree -L 2 "$MOUNT_POINT" 2>/dev/null || find "$MOUNT_POINT" -maxdepth 2 -type d | sed 's/^/  /'

    # ============================================================
    # Check 4: Auto-Installer Files
    # ============================================================
    print_header "4. Auto-Installer Configuration"

    echo "Searching for auto-installer files..."

    # Check for answer.toml
    local answer_files=$(find "$MOUNT_POINT" -name "answer.toml" 2>/dev/null)
    if [[ -n "$answer_files" ]]; then
        print_success "Found answer.toml:"
        echo "$answer_files" | sed 's/^/    /'
        echo ""
        echo "Content (first 20 lines):"
        head -20 $(echo "$answer_files" | head -1) | sed 's/^/    /'
    else
        print_error "answer.toml NOT FOUND (auto-install will fail!)"
    fi

    echo ""
    # Check for auto-installer-mode.toml
    local mode_files=$(find "$MOUNT_POINT" -name "auto-installer-mode.toml" 2>/dev/null)
    if [[ -n "$mode_files" ]]; then
        print_success "Found auto-installer-mode.toml:"
        echo "$mode_files" | sed 's/^/    /'
    else
        print_warning "auto-installer-mode.toml NOT FOUND (may not be required for all versions)"
    fi

    echo ""
    # Check for first-boot script
    local firstboot_files=$(find "$MOUNT_POINT" -name "*first-boot*.sh" 2>/dev/null)
    if [[ -n "$firstboot_files" ]]; then
        print_success "Found first-boot script:"
        echo "$firstboot_files" | sed 's/^/    /'
    else
        print_warning "First-boot script not found (reinstall protection may not work)"
    fi

    # ============================================================
    # Check 5: Bootloader Configuration (Legacy BIOS)
    # ============================================================
    print_header "5. Bootloader Configuration"

    echo "Checking for bootloader configs..."
    echo ""
    print_info "NOTE: Proxmox uses GRUB (not ISOLINUX/SYSLINUX) for Legacy BIOS boot"
    echo ""

    # Check GRUB (Primary bootloader for Proxmox hybrid ISO)
    local grub_found=0
    if [[ -f "$MOUNT_POINT/boot/grub/grub.cfg" ]]; then
        print_success "Found GRUB config: boot/grub/grub.cfg"
        grub_found=1
        echo ""
        echo "GRUB configuration (first 40 lines):"
        head -40 "$MOUNT_POINT/boot/grub/grub.cfg" | sed 's/^/    /'
        echo ""
        echo "Checking for auto-installer kernel parameter..."
        if grep -q "proxmox-start-auto-installer" "$MOUNT_POINT/boot/grub/grub.cfg"; then
            print_success "Found 'proxmox-start-auto-installer' flag in GRUB config"
        else
            print_error "'proxmox-start-auto-installer' NOT FOUND in GRUB config!"
            print_error "Auto-install will NOT activate automatically!"
        fi
    else
        print_error "boot/grub/grub.cfg NOT FOUND!"
        print_error "This is critical - USB won't boot without GRUB config"
    fi

    echo ""
    # Check for GRUB core files
    echo "Checking for GRUB core files..."
    local grub_core_found=0
    for grub_file in "$MOUNT_POINT/boot/grub/i386-pc/core.img" "$MOUNT_POINT/boot/grub/i386-pc/boot.img"; do
        if [[ -f "$grub_file" ]]; then
            print_success "Found: $(basename $(dirname $grub_file))/$(basename $grub_file)"
            grub_core_found=1
        fi
    done

    if [[ $grub_core_found -eq 0 ]]; then
        print_warning "GRUB i386-pc core files not found (may use embedded GRUB)"
    fi

    echo ""
    # Check ISOLINUX (Legacy - Proxmox doesn't use this anymore)
    if [[ -f "$MOUNT_POINT/isolinux/isolinux.cfg" ]]; then
        print_info "Found ISOLINUX config (legacy, not used by Proxmox)"
    else
        print_info "ISOLINUX not found (expected - Proxmox uses GRUB)"
    fi

    echo ""
    # Check SYSLINUX (Legacy - Proxmox doesn't use this)
    if [[ -f "$MOUNT_POINT/syslinux/syslinux.cfg" ]]; then
        print_info "Found SYSLINUX config (legacy, not used by Proxmox)"
    else
        print_info "SYSLINUX not found (expected - Proxmox uses GRUB)"
    fi

    # ============================================================
    # Check 6: Kernel and Initrd
    # ============================================================
    print_header "6. Kernel and Initrd"

    echo "Searching for kernel files..."
    local kernel_files=$(find "$MOUNT_POINT" -type f \( -name "linux26" -o -name "vmlinuz*" \) 2>/dev/null | head -5)
    if [[ -n "$kernel_files" ]]; then
        print_success "Found kernel files:"
        echo "$kernel_files" | sed 's/^/    /'
    else
        print_error "Kernel files NOT FOUND"
    fi

    echo ""
    echo "Searching for initrd files..."
    local initrd_files=$(find "$MOUNT_POINT" -type f \( -name "initrd*" -o -name "initramfs*" \) 2>/dev/null | head -5)
    if [[ -n "$initrd_files" ]]; then
        print_success "Found initrd files:"
        echo "$initrd_files" | sed 's/^/    /'
    else
        print_error "Initrd files NOT FOUND"
    fi

    # ============================================================
    # Check 7: Boot Priority Issue Detection
    # ============================================================
    print_header "7. Common Issues Detection"

    # Check if it's a proper ISO9660 filesystem
    local fstype=$(blkid -o value -s TYPE "$mount_target" 2>/dev/null || echo "unknown")
    if [[ "$fstype" == "iso9660" ]]; then
        print_warning "Filesystem is ISO9660 (read-only, standard for hybrid ISO)"
        print_info "This is expected for Proxmox ISO written with dd"
    fi

    # Check free space
    local free_space=$(df -h "$MOUNT_POINT" | awk 'NR==2 {print $4}')
    print_info "Free space: $free_space"

    # ============================================================
    # Summary and Recommendations
    # ============================================================
    print_header "8. Summary and Recommendations"

    echo "Diagnosis complete. Key findings:"
    echo ""

    # Check if answer.toml exists
    if [[ -n "$(find "$MOUNT_POINT" -name "answer.toml" 2>/dev/null)" ]]; then
        print_success "answer.toml present (auto-install configuration found)"
    else
        print_error "answer.toml MISSING - USB will not auto-install!"
        echo ""
        print_info "To fix: Recreate USB with create-legacy-autoinstall-proxmox-usb.sh"
    fi

    echo ""
    # Check if proxmox-start-auto-installer flag exists
    if grep -qr "proxmox-start-auto-installer" "$MOUNT_POINT" 2>/dev/null; then
        print_success "Auto-installer kernel flag found (should activate automatically)"
    else
        print_error "Auto-installer kernel flag MISSING - USB will show interactive menu!"
        echo ""
        print_info "Issue: proxmox-auto-install-assistant may not have modified bootloader"
        print_info "To fix: Check if proxmox-auto-install-assistant is installed and working"
        print_info "        Or manually add 'proxmox-start-auto-installer' to kernel cmdline"
    fi

    echo ""
    # Boot method check (GRUB-based)
    if [[ -f "$MOUNT_POINT/boot/grub/grub.cfg" ]]; then
        print_success "Legacy BIOS boot method: GRUB (correct for Proxmox hybrid ISO)"

        # Check if GRUB MBR is installed
        echo ""
        echo "Checking MBR boot sector..."
        local mbr_sig=$(dd if="$USB_DEVICE" bs=1 skip=510 count=2 2>/dev/null | xxd -p)
        if [[ "$mbr_sig" == "55aa" ]]; then
            print_success "MBR boot signature valid (0x55AA)"
        else
            print_error "MBR boot signature invalid! USB may not boot in Legacy BIOS"
        fi
    else
        print_error "GRUB config not found - USB will NOT boot in Legacy BIOS mode!"
        echo ""
        print_info "To fix: Recreate USB with corrected create-legacy-autoinstall-proxmox-usb.sh"
    fi

    echo ""
    print_info "Troubleshooting if Dell boots to old Proxmox GRUB instead of USB:"
    print_info "1. Verify USB is first in BIOS boot order (USB HDD must be #1)"
    print_info "2. Try different USB port (USB 2.0 ports work better with Legacy BIOS)"
    print_info "3. Press F12 at boot and manually select 'Removable Devices' or 'USB HDD'"
    print_info "4. Disable 'Fast Boot' in BIOS if present"
    print_info "5. Check if MBR is correctly installed (run this diagnostic again)"
    echo ""
    print_info "If USB still doesn't boot:"
    print_info "- Recreate USB ensuring grub-install runs successfully"
    print_info "- Check USB integrity: sudo fdisk -l $USB_DEVICE"
    print_info "- Verify GRUB files exist: ls -la /mnt/usb/boot/grub/"

    echo ""
}

main "$@"
