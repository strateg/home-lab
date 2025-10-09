#!/bin/bash
# Proxmox VE Auto-Install USB Creator
# Creates bootable USB with auto-install configuration

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC} $1"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ============================================================
# Check Requirements
# ============================================================

check_requirements() {
    print_section "Checking Requirements"

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        print_error "Please run as root (sudo)"
        exit 1
    fi

    # Check for required tools
    local required_tools=("dd" "lsblk" "sync" "mkpasswd")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            print_warning "$tool not found, installing..."
            apt-get update -qq
            apt-get install -y -qq whois coreutils util-linux
        fi
    done

    print_success "All requirements satisfied"
}

# ============================================================
# Display Usage
# ============================================================

usage() {
    cat <<EOF
Usage: $0 <USB_DEVICE> <ISO_FILE>

Create Proxmox VE auto-install USB drive

Arguments:
  USB_DEVICE    Target USB device (e.g., /dev/sdb)
  ISO_FILE      Proxmox VE ISO file path

Examples:
  $0 /dev/sdb proxmox-ve_9.0-1.iso
  $0 /dev/sdc ~/Downloads/proxmox-ve_9.0-1.iso

Options:
  -h, --help    Show this help message

Notes:
  - USB device will be COMPLETELY ERASED
  - Minimum 2 GB USB drive required
  - ISO file will be downloaded if not found

EOF
}

# ============================================================
# Parse Arguments
# ============================================================

if [ "$#" -lt 2 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    usage
    exit 0
fi

USB_DEVICE="$1"
ISO_FILE="$2"

# ============================================================
# Validate USB Device
# ============================================================

validate_usb_device() {
    print_section "Validating USB Device: $USB_DEVICE"

    if [ ! -b "$USB_DEVICE" ]; then
        print_error "Device $USB_DEVICE does not exist or is not a block device"
        echo ""
        echo "Available devices:"
        lsblk -o NAME,SIZE,TYPE,MOUNTPOINT
        exit 1
    fi

    # Check if device is mounted
    if mount | grep -q "$USB_DEVICE"; then
        print_warning "Device $USB_DEVICE is mounted, unmounting..."
        umount "${USB_DEVICE}"* 2>/dev/null || true
    fi

    # Get device size
    local size=$(lsblk -b -d -n -o SIZE "$USB_DEVICE")
    local size_gb=$((size / 1024 / 1024 / 1024))

    print_info "Device: $USB_DEVICE"
    print_info "Size: ${size_gb} GB"

    if [ "$size_gb" -lt 2 ]; then
        print_error "USB drive too small (minimum 2 GB required)"
        exit 1
    fi

    print_success "USB device validated"
}

# ============================================================
# Validate ISO File
# ============================================================

validate_iso_file() {
    print_section "Validating ISO File"

    if [ ! -f "$ISO_FILE" ]; then
        print_error "ISO file not found: $ISO_FILE"
        echo ""
        print_info "Download Proxmox VE ISO from:"
        echo "  https://www.proxmox.com/en/downloads/proxmox-virtual-environment/iso"
        echo ""
        print_info "Or auto-download latest version? (y/n)"
        read -r response
        if [ "$response" == "y" ]; then
            download_iso
        else
            exit 1
        fi
    fi

    local iso_size=$(stat -c%s "$ISO_FILE")
    local iso_size_mb=$((iso_size / 1024 / 1024))

    print_info "ISO file: $ISO_FILE"
    print_info "Size: ${iso_size_mb} MB"

    # Basic validation - check if it's a valid ISO
    if ! file "$ISO_FILE" | grep -q "ISO 9660"; then
        print_error "File does not appear to be a valid ISO image"
        exit 1
    fi

    print_success "ISO file validated"
}

# ============================================================
# Download ISO (optional)
# ============================================================

download_iso() {
    print_section "Downloading Proxmox VE ISO"

    # Latest Proxmox VE 9 ISO URL (update as needed)
    local ISO_URL="https://enterprise.proxmox.com/iso/proxmox-ve_9.0-1.iso"
    local ISO_DIR="./iso"

    mkdir -p "$ISO_DIR"
    ISO_FILE="$ISO_DIR/proxmox-ve_9.0-1.iso"

    print_info "Downloading from: $ISO_URL"
    print_info "Destination: $ISO_FILE"

    wget -c -O "$ISO_FILE" "$ISO_URL"

    print_success "ISO downloaded"
}

# ============================================================
# Prepare answer.toml
# ============================================================

prepare_answer_file() {
    print_section "Preparing Auto-Install Configuration"

    local ANSWER_FILE="./answer.toml"

    if [ ! -f "$ANSWER_FILE" ]; then
        print_error "answer.toml not found in current directory"
        exit 1
    fi

    # Check if password is still default
    if grep -q "YourSaltHere" "$ANSWER_FILE"; then
        print_warning "Default password detected in answer.toml"
        echo ""
        print_info "Enter root password for Proxmox:"
        read -s -r password
        echo ""
        print_info "Confirm password:"
        read -s -r password_confirm
        echo ""

        if [ "$password" != "$password_confirm" ]; then
            print_error "Passwords do not match"
            exit 1
        fi

        # Generate password hash
        local password_hash=$(mkpasswd -m sha-512 "$password")

        # Update answer.toml (create backup first)
        cp "$ANSWER_FILE" "${ANSWER_FILE}.bak"
        sed -i "s|root_password = \".*\"|root_password = \"$password_hash\"|" "$ANSWER_FILE"

        print_success "Password updated in answer.toml"
    fi

    print_success "Auto-install configuration ready"
}

# ============================================================
# Create Bootable USB
# ============================================================

create_bootable_usb() {
    print_section "Creating Bootable USB"

    print_warning "This will ERASE all data on $USB_DEVICE"
    print_info "Continue? (yes/no)"
    read -r response

    if [ "$response" != "yes" ]; then
        print_info "Aborted by user"
        exit 0
    fi

    # Write ISO to USB
    print_info "Writing ISO to USB (this may take 5-10 minutes)..."
    dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=sync

    # Sync to ensure all data is written
    print_info "Syncing data to USB..."
    sync

    print_success "ISO written to USB"
}

# ============================================================
# Add Auto-Install Configuration
# ============================================================

add_autoinstall_config() {
    print_section "Adding Auto-Install Configuration"

    # Mount USB partition
    print_info "Mounting USB partition..."
    local MOUNT_POINT="/mnt/proxmox-usb"
    mkdir -p "$MOUNT_POINT"

    # Find ISO partition (usually partition 2)
    local USB_PARTITION="${USB_DEVICE}2"
    if [ ! -b "$USB_PARTITION" ]; then
        USB_PARTITION="${USB_DEVICE}p2"
    fi

    mount "$USB_PARTITION" "$MOUNT_POINT" 2>/dev/null || {
        print_warning "Could not mount partition, trying partition 1..."
        USB_PARTITION="${USB_DEVICE}1"
        mount "$USB_PARTITION" "$MOUNT_POINT"
    }

    # Copy answer.toml to USB
    print_info "Copying answer.toml to USB..."
    cp ./answer.toml "$MOUNT_POINT/answer.toml"

    # Copy post-install scripts to USB (optional)
    if [ -d "./post-install" ]; then
        print_info "Copying post-install scripts to USB..."
        mkdir -p "$MOUNT_POINT/post-install"
        cp -r ./post-install/* "$MOUNT_POINT/post-install/"
    fi

    # Unmount
    print_info "Unmounting USB..."
    umount "$MOUNT_POINT"
    rmdir "$MOUNT_POINT"

    print_success "Auto-install configuration added"
}

# ============================================================
# Verify USB
# ============================================================

verify_usb() {
    print_section "Verifying USB Drive"

    # Check if USB is bootable
    print_info "USB device: $USB_DEVICE"
    print_info "USB is ready for installation"

    # Display partition table
    echo ""
    print_info "Partition table:"
    fdisk -l "$USB_DEVICE"

    print_success "USB verification complete"
}

# ============================================================
# Display Instructions
# ============================================================

display_instructions() {
    print_section "Installation Instructions"

    cat <<EOF
${GREEN}✅ Bootable USB created successfully!${NC}

${BLUE}Next steps:${NC}

1. ${YELLOW}Boot from USB on Dell XPS L701X${NC}
   - Insert USB drive
   - Power on laptop
   - Press F12 for boot menu
   - Select USB drive (UEFI mode)

2. ${YELLOW}Proxmox Installation${NC}
   - Installation will start automatically
   - No user input required (unattended)
   - Takes ~10-15 minutes

3. ${YELLOW}After Installation${NC}
   - Remove USB drive
   - Reboot system
   - SSH to Proxmox: ssh root@<ip-address>
   - Password: (the one you set in answer.toml)

4. ${YELLOW}Post-Installation${NC}
   - Copy post-install scripts: scp -r post-install/ root@<ip>:/root/
   - SSH to Proxmox
   - Run: cd /root/post-install && ./01-install-terraform.sh

5. ${YELLOW}Access Web UI${NC}
   - URL: https://<ip-address>:8006
   - User: root
   - Password: (the one you set)

${BLUE}Configuration Details:${NC}
- Filesystem: ext4
- Root partition: 50 GB
- Swap: 2 GB
- LVM thin pool: ~128 GB (for VMs/LXC)
- Network: DHCP (will be reconfigured by Ansible)
- Hostname: pve.home.local

${GREEN}USB device is ready: $USB_DEVICE${NC}

EOF
}

# ============================================================
# Main Execution
# ============================================================

main() {
    print_section "Proxmox VE Auto-Install USB Creator"

    check_requirements
    validate_usb_device
    validate_iso_file
    prepare_answer_file
    create_bootable_usb
    add_autoinstall_config
    verify_usb
    display_instructions

    print_success "Process completed successfully!"
}

# Run main function
main
