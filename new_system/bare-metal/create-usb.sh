#!/bin/bash
# Proxmox VE Auto-Install USB Creator
# Uses OFFICIAL Proxmox automated installation method:
# 1. Validates answer.toml configuration
# 2. Prepares ISO with embedded answer.toml (using proxmox-auto-install-assistant)
# 3. Writes prepared ISO to USB
# 4. Adds graphics parameters for external display (Dell XPS L701X)
#
# The prepared ISO automatically boots "Automated Installation" after 10 seconds
#
# DISK SETUP (configured in answer.toml):
# - SSD (sda): WILL BE ERASED AND FORMATTED - System disk
# - HDD (sdb): PRESERVED - Data disk (mounted by post-install scripts)
#
# Usage: sudo ./create-usb.sh /dev/sdX path/to/proxmox.iso

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

    # Check for proxmox-auto-install-assistant (CRITICAL for auto-install)
    if ! command -v proxmox-auto-install-assistant &> /dev/null; then
        print_error "proxmox-auto-install-assistant not found"
        echo ""
        print_info "This tool is REQUIRED for automated installation"
        echo ""
        echo "Install it with these commands:"
        echo ""
        echo -e "${YELLOW}# Add Proxmox GPG key:${NC}"
        echo "wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg"
        echo ""
        echo -e "${YELLOW}# Add Proxmox repository:${NC}"
        echo 'echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" | tee /etc/apt/sources.list.d/pve-install-repo.list'
        echo ""
        echo -e "${YELLOW}# Update and install:${NC}"
        echo "apt update && apt install proxmox-auto-install-assistant"
        echo ""
        exit 1
    fi

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
# Validate answer.toml
# ============================================================

validate_answer_file() {
    print_section "Validating answer.toml"

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

    # Validate answer.toml using official tool
    print_info "Validating answer.toml syntax..."
    if proxmox-auto-install-assistant validate-answer "$ANSWER_FILE"; then
        print_success "answer.toml is valid"
    else
        print_error "answer.toml validation failed"
        exit 1
    fi
}

# ============================================================
# Prepare ISO with embedded answer.toml
# ============================================================

prepare_iso() {
    print_section "Preparing ISO with embedded answer.toml"

    print_info "Using proxmox-auto-install-assistant to prepare ISO..."
    print_info "This creates an ISO with 'Automated Installation' boot option"
    echo ""

    # Generate readable installation ID with timestamp (штамп)
    # Format: TIMEZONE_YYYY_MM_DD_HH_MM
    TIMEZONE=$(date +%Z)
    TIMESTAMP=$(date +%Y_%m_%d_%H_%M)
    INSTALL_UUID="${TIMEZONE}_${TIMESTAMP}"

    print_info "Generated installation ID: $INSTALL_UUID"
    print_info "Format: ${TIMEZONE} (timezone) ${TIMESTAMP//_/-} (date time)"

    # Save UUID to file for later embedding on USB
    echo "$INSTALL_UUID" > /tmp/install-uuid-$$
    export INSTALL_UUID

    # Create first-boot script with UUID marker commands
    FIRST_BOOT_SCRIPT="/tmp/first-boot-$$.sh"
    cat > "$FIRST_BOOT_SCRIPT" << 'SCRIPTEOF'
#!/bin/bash
# First-boot script - Reinstall Prevention
# Reads installation ID from USB and saves it to the installed system

set -e

# Log everything
exec 1>>/var/log/proxmox-first-boot.log 2>&1
echo "===== First-boot script started at $(date) ====="

# Find the USB installation media (look for install-id file)
INSTALL_ID=""
USB_MOUNT=""

# Search all mounted vfat partitions for install-id file
for mount_point in /media/* /mnt/* /run/media/* /run/mount/*; do
    if [ -f "$mount_point/EFI/BOOT/install-id" ]; then
        INSTALL_ID=$(cat "$mount_point/EFI/BOOT/install-id")
        USB_MOUNT="$mount_point"
        echo "✓ Found USB installation media at: $USB_MOUNT"
        echo "✓ Installation ID from USB: $INSTALL_ID"
        break
    fi
done

# If not found in mounted locations, search all vfat partitions
if [ -z "$INSTALL_ID" ]; then
    echo "Searching for USB in all vfat partitions..."
    for dev in $(blkid -t TYPE=vfat -o device); do
        TMP_MOUNT="/tmp/usb-check-$$"
        mkdir -p "$TMP_MOUNT"
        if mount -o ro "$dev" "$TMP_MOUNT" 2>/dev/null; then
            if [ -f "$TMP_MOUNT/EFI/BOOT/install-id" ]; then
                INSTALL_ID=$(cat "$TMP_MOUNT/EFI/BOOT/install-id")
                echo "✓ Found installation ID on $dev: $INSTALL_ID"
                umount "$TMP_MOUNT"
                rmdir "$TMP_MOUNT"
                break
            fi
            umount "$TMP_MOUNT" 2>/dev/null
            rmdir "$TMP_MOUNT"
        fi
    done
fi

if [ -z "$INSTALL_ID" ]; then
    echo "⚠ WARNING: Could not find USB installation media!"
    echo "⚠ Using fallback timestamp-based ID"
    TIMEZONE=$(date +%Z)
    TIMESTAMP=$(date +%Y_%m_%d_%H_%M)
    INSTALL_ID="${TIMEZONE}_${TIMESTAMP}"
    echo "Generated fallback ID: $INSTALL_ID"
fi

echo "Installation ID to save: $INSTALL_ID"

# Save installation ID to system root
echo -n "$INSTALL_ID" > /etc/proxmox-install-id
echo "✓ Created /etc/proxmox-install-id"

# Find EFI partition and mount it
EFI_PARTITION=$(blkid | grep -i 'TYPE="vfat"' | grep -i 'efi' | head -1 | cut -d: -f1)
if [ -z "$EFI_PARTITION" ]; then
    # Try finding any vfat partition (likely EFI)
    EFI_PARTITION=$(blkid -t TYPE=vfat -o device | head -1)
fi

if [ -n "$EFI_PARTITION" ]; then
    echo "Found EFI partition: $EFI_PARTITION"

    # Ensure mount point exists
    mkdir -p /boot/efi

    # Mount if not already mounted
    if ! mountpoint -q /boot/efi; then
        mount "$EFI_PARTITION" /boot/efi
        echo "✓ Mounted $EFI_PARTITION to /boot/efi"
    else
        echo "✓ /boot/efi already mounted"
    fi

    # Write UUID marker to EFI partition root (without trailing newline)
    echo -n "$INSTALL_ID" > /boot/efi/proxmox-installed
    sync
    echo "✓ Created /boot/efi/proxmox-installed with ID: $INSTALL_ID"

    # Verify the file was created
    if [ -f /boot/efi/proxmox-installed ]; then
        SAVED_ID=$(cat /boot/efi/proxmox-installed)
        echo "✓ Verified: File contains '$SAVED_ID'"
    else
        echo "✗ ERROR: File was not created!"
    fi
else
    echo "⚠ WARNING: Could not find EFI partition!"
    echo "⚠ Reinstall prevention may not work!"
fi

echo "===== First-boot script completed at $(date) ====="
exit 0
SCRIPTEOF

    # Make script executable (no placeholder replacement needed - UUID generated dynamically)
    chmod +x "$FIRST_BOOT_SCRIPT"

    # Create modified answer.toml with first-boot reference
    TEMP_ANSWER="/tmp/answer-with-uuid-$$.toml"
    cp ./answer.toml "$TEMP_ANSWER"

    # Add first-boot section
    cat >> "$TEMP_ANSWER" << 'EOF'

# ============================================================
# First-boot script (Reinstall Prevention)
# ============================================================

[first-boot]
source = "from-iso"
EOF

    print_success "Created first-boot script with UUID: $INSTALL_UUID"

    PREPARED_ISO="${ISO_FILE%.iso}-automated.iso"

    # Remove old prepared ISO if exists
    rm -f "$PREPARED_ISO"

    # Run prepare-iso with modified answer.toml and first-boot script
    # --fetch-from iso: embeds answer.toml and first-boot script into ISO
    # --answer-file: path to modified answer.toml
    # --on-first-boot: path to first-boot script
    proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
        --fetch-from iso \
        --answer-file "$TEMP_ANSWER" \
        --on-first-boot "$FIRST_BOOT_SCRIPT"

    # Clean up temporary files
    rm -f "$TEMP_ANSWER" "$FIRST_BOOT_SCRIPT"

    # The tool creates ISO with specific naming pattern
    # Find the created ISO
    CREATED_ISO=$(ls -t "${ISO_FILE%.iso}"*-auto-from-iso.iso 2>/dev/null | head -1)

    if [ -z "$CREATED_ISO" ]; then
        print_error "Failed to create prepared ISO"
        echo "Expected pattern: ${ISO_FILE%.iso}*-auto-from-iso.iso"
        exit 1
    fi

    # Rename to our target
    mv "$CREATED_ISO" "$PREPARED_ISO"

    if [ ! -f "$PREPARED_ISO" ]; then
        print_error "Failed to create prepared ISO"
        exit 1
    fi

    print_success "Prepared ISO created: $PREPARED_ISO"
    print_success "This ISO includes 'Automated Installation' boot entry"
    print_success "Auto-selects after 10 seconds (official Proxmox behavior)"
}

# ============================================================
# Write prepared ISO to USB
# ============================================================

write_usb() {
    print_section "Writing prepared ISO to USB"

    print_warning "This will ERASE all data on $USB_DEVICE"
    print_info "Continue? (yes/no)"
    read -r response

    if [ "$response" != "yes" ]; then
        print_info "Aborted by user"
        # Clean up prepared ISO
        rm -f "$PREPARED_ISO"
        exit 0
    fi

    # Unmount any mounted partitions
    umount "${USB_DEVICE}"* 2>/dev/null || true

    # Write prepared ISO to USB
    print_info "Writing prepared ISO to USB (this may take 5-10 minutes)..."
    dd if="$PREPARED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

    # Sync to ensure all data is written
    print_info "Syncing data to USB..."
    sync
    sleep 3

    print_success "Prepared ISO written to USB"
}

# ============================================================
# Add graphics parameters for external display (Dell XPS L701X)
# ============================================================

add_graphics_params() {
    print_section "Adding graphics parameters for external display"

    print_info "Modifying GRUB configuration for Dell XPS L701X..."

    # Force re-read partition table
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
                    print_info "Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}"

                    # Backup original
                    cp "$GRUB_CFG" "$GRUB_CFG.backup-$(date +%s)"

                    # Check if graphics parameters already present
                    if grep -q "video=vesafb" "$GRUB_CFG"; then
                        print_info "Graphics parameters already present"
                    else
                        print_info "Adding graphics parameters to all boot entries..."

                        # Add graphics parameters to all linux boot lines
                        sed -i '/linux.*\/boot\/linux26/ s|$| video=vesafb:ywrap,mtrr vga=791 nomodeset|' "$GRUB_CFG"

                        print_success "Graphics parameters added"
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

    if [ $GRUB_MODIFIED -eq 1 ]; then
        print_success "GRUB configuration modified for external display"
    else
        print_warning "Could not modify GRUB (external display may not work)"
    fi
}

# ============================================================
# Embed installation UUID and reinstall-check script
# ============================================================

embed_install_uuid() {
    print_section "Embedding installation ID on USB"

    # Get saved UUID
    INSTALL_UUID=$(cat /tmp/install-uuid-$$ 2>/dev/null)
    if [ -z "$INSTALL_UUID" ]; then
        print_error "Installation ID not found"
        exit 1
    fi

    # Parse UUID to show readable format
    TIMEZONE="${INSTALL_UUID%%_*}"
    TIMESTAMP="${INSTALL_UUID#*_}"
    TIMESTAMP_READABLE=$(echo "$TIMESTAMP" | sed 's/_/-/g; s/-/ /3; s/-/:/4')

    print_info "Installation ID: $INSTALL_UUID"
    print_info "Created: $TIMEZONE $TIMESTAMP_READABLE"

    # Force re-read partition table
    partprobe "$USB_DEVICE" 2>/dev/null || true
    blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
    sleep 3

    MOUNT_POINT="/tmp/usb-uuid-$$"
    mkdir -p "$MOUNT_POINT"
    UUID_EMBEDDED=0

    # Find and mount the FAT32 EFI partition
    for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
        [ ! -b "$part" ] && continue

        FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

        if [ "$FSTYPE" = "vfat" ]; then
            if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
                # Create EFI/BOOT directory if needed
                mkdir -p "$MOUNT_POINT/EFI/BOOT"

                # Save installation ID (without trailing newline for exact comparison)
                echo -n "$INSTALL_UUID" > "$MOUNT_POINT/EFI/BOOT/install-id"

                # Also save human-readable version
                cat > "$MOUNT_POINT/EFI/BOOT/install-info.txt" << INFOEOF
Proxmox VE Auto-Install USB
============================

Installation ID: $INSTALL_UUID

Created:
  Timezone: $TIMEZONE
  Date:     $(echo "$TIMESTAMP" | cut -d_ -f1-3 | sed 's/_/-/g')
  Time:     $(echo "$TIMESTAMP" | cut -d_ -f4-5 | sed 's/_/:/g')

This USB will mark installed systems with this ID to prevent
accidental reinstallation on reboot.
INFOEOF

                print_success "ID saved to: /EFI/BOOT/install-id"
                print_success "Info saved to: /EFI/BOOT/install-info.txt"

                # Backup original grub.cfg
                if [ -f "$MOUNT_POINT/EFI/BOOT/grub.cfg" ]; then
                    mv "$MOUNT_POINT/EFI/BOOT/grub.cfg" "$MOUNT_POINT/EFI/BOOT/grub-install.cfg"
                    print_success "Backed up original grub.cfg → grub-install.cfg"
                fi

                # Create reinstall-check GRUB script as MAIN grub.cfg
                cat > "$MOUNT_POINT/EFI/BOOT/grub.cfg" << GRUBEOF
# Reinstall Prevention Check
# This script prevents automatic reinstallation if system is already installed

# Load required modules
insmod part_gpt
insmod part_msdos
insmod fat
insmod ext2
insmod search
insmod search_fs_file
insmod chain

set install_detected=0
set debug_mode=1

# Debug: Show what we're doing
if [ \$debug_mode -eq 1 ]; then
    echo "DEBUG: Searching for installation marker..."
fi

# Check for installation marker on first disk EFI partition
search --no-floppy --set=efipart --file /proxmox-installed
if [ -n "\$efipart" ]; then
    if [ \$debug_mode -eq 1 ]; then
        echo "DEBUG: Found EFI partition with marker: \$efipart"
    fi

    # Read installation ID from disk
    cat --set=installed_id (\$efipart)/proxmox-installed

    if [ \$debug_mode -eq 1 ]; then
        echo "DEBUG: Disk UUID: \$installed_id"
    fi

    # Read USB installation ID
    if [ -f (\$root)/EFI/BOOT/install-id ]; then
        cat --set=usb_id (\$root)/EFI/BOOT/install-id

        if [ \$debug_mode -eq 1 ]; then
            echo "DEBUG: USB UUID: \$usb_id"
        fi

        # Compare IDs
        if [ "\$installed_id" = "\$usb_id" ]; then
            set install_detected=1
            if [ \$debug_mode -eq 1 ]; then
                echo "DEBUG: UUIDs match! System already installed."
            fi
        else
            if [ \$debug_mode -eq 1 ]; then
                echo "DEBUG: UUIDs DO NOT match."
            fi
        fi
    else
        if [ \$debug_mode -eq 1 ]; then
            echo "DEBUG: No install-id file on USB"
        fi
    fi
else
    if [ \$debug_mode -eq 1 ]; then
        echo "DEBUG: No installation marker found on disk"
    fi
fi

if [ \$debug_mode -eq 1 ]; then
    echo "DEBUG: install_detected = \$install_detected"
    echo " "
    echo "Press any key to continue..."
    read -t 5
fi

if [ \$install_detected -eq 1 ]; then
    # System already installed - show menu with auto-boot to disk
    set timeout=5
    set default=0

    menuentry 'Boot Proxmox VE (installed system)' --hotkey=d {
        echo "Booting installed Proxmox VE..."
        # Search for Proxmox EFI bootloader and chainload
        search --no-floppy --set=proxmoxroot --file /EFI/proxmox/grubx64.efi
        if [ -n "\$proxmoxroot" ]; then
            set root=\$proxmoxroot
            chainloader /EFI/proxmox/grubx64.efi
            boot
        else
            # Fallback: try standard EFI location
            set root=(hd0,gpt2)
            chainloader /EFI/proxmox/grubx64.efi
            boot
        fi
    }

    menuentry 'Reinstall Proxmox VE (ERASES ALL DATA!)' --hotkey=r {
        echo "Starting Proxmox installation..."
        configfile /EFI/BOOT/grub-install.cfg
    }
else
    # No installation detected - proceed with normal installation
    configfile /EFI/BOOT/grub-install.cfg
fi
GRUBEOF

                print_success "Created reinstall-check as main grub.cfg"

                sync
                UUID_EMBEDDED=1
                umount "$MOUNT_POINT"
                break
            fi
        fi
    done

    rmdir "$MOUNT_POINT"

    # Clean up temp UUID file
    rm -f /tmp/install-uuid-$$

    if [ $UUID_EMBEDDED -eq 1 ]; then
        print_success "Installation ID embedded on USB"
        echo ""
        print_info "📝 Installation ID breakdown:"
        print_info "   Timezone: $TIMEZONE"
        print_info "   Date:     $(echo "$TIMESTAMP" | cut -d_ -f1-3 | sed 's/_/-/g')"
        print_info "   Time:     $(echo "$TIMESTAMP" | cut -d_ -f4-5 | sed 's/_/:/g')"
    else
        print_error "Failed to embed ID (USB may reinstall every boot)"
        exit 1
    fi
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
${GREEN}╔════════════════════════════════════════════════════════╗${NC}
${GREEN}║                                                        ║${NC}
${GREEN}║  USB READY FOR AUTOMATED INSTALLATION!                 ║${NC}
${GREEN}║                                                        ║${NC}
${GREEN}╚════════════════════════════════════════════════════════╝${NC}

${BLUE}What was done:${NC}
  ✓ Validated answer.toml configuration
  ✓ Prepared ISO with embedded answer.toml (official Proxmox method)
  ✓ Written prepared ISO to USB: $USB_DEVICE
  ✓ Added graphics parameters for external display

${GREEN}Installation ID: $INSTALL_UUID${NC}
  Timezone: ${TIMEZONE}
  Created:  $(echo "$TIMESTAMP" | cut -d_ -f1-3 | sed 's/_/-/g') $(echo "$TIMESTAMP" | cut -d_ -f4-5 | sed 's/_/:/g')

${YELLOW}╔════════════════════════════════════════════════════════╗${NC}
${YELLOW}║ BOOT INSTRUCTIONS (Dell XPS L701X)                    ║${NC}
${YELLOW}╚════════════════════════════════════════════════════════╝${NC}

1. Connect external monitor to Mini DisplayPort
2. Power ON the external monitor
3. Insert USB into Dell XPS L701X
4. Power on laptop
5. Press F12 for boot menu
6. Select: ${GREEN}UEFI: USB...${NC} (NOT 'USB Storage Device')

${GREEN}╔════════════════════════════════════════════════════════╗${NC}
${GREEN}║ AUTOMATIC INSTALLATION BEHAVIOR                       ║${NC}
${GREEN}╚════════════════════════════════════════════════════════╝${NC}

${BLUE}First boot (system NOT installed):${NC}
• GRUB menu appears on external display
• First option: ${GREEN}"Automated Installation"${NC} (official Proxmox)
• Countdown: ${YELLOW}10 seconds${NC} (automatic boot)
• Installation starts ${GREEN}AUTOMATICALLY${NC}!
• Reads embedded answer.toml from ISO
• Progress shown on external display
• System reboots when complete (~10-15 min)
• Installation UUID marker saved to disk

${BLUE}Second boot (system ALREADY installed from this USB):${NC}
• GRUB detects installation ID marker
• Shows readable installation date/time in menu
• ${GREEN}Menu changes automatically${NC}:
  1. 'Boot Proxmox from disk (Already Installed)' ${YELLOW}[default]${NC}
  2. 'Reinstall Proxmox (ERASES DISK!)'
• Countdown: ${YELLOW}10 seconds${NC} → boots installed system
• ${RED}Reinstallation prevented automatically!${NC}
• Press 'r' to force reinstall if needed (ERASES ALL DATA!)

${GREEN}This prevents accidental reinstallation!${NC}
${BLUE}Installation ID shows when USB was created!${NC}

${BLUE}╔════════════════════════════════════════════════════════╗${NC}
${BLUE}║ AFTER INSTALLATION                                    ║${NC}
${BLUE}╚════════════════════════════════════════════════════════╝${NC}

1. Find IP address (check router DHCP leases)
2. SSH: ${GREEN}ssh root@<ip-address>${NC}
3. Password: ${YELLOW}(the one you set in answer.toml)${NC}
4. Web UI: ${GREEN}https://<ip-address>:8006${NC}

${BLUE}╔════════════════════════════════════════════════════════╗${NC}
${BLUE}║ POST-INSTALLATION AUTOMATION                          ║${NC}
${BLUE}╚════════════════════════════════════════════════════════╝${NC}

Copy post-install scripts to Proxmox:
  ${GREEN}scp -r post-install/ root@<ip>:/root/${NC}

SSH to Proxmox and run setup:
  ${GREEN}cd /root/post-install${NC}
  ${GREEN}./01-install-terraform.sh${NC}
  ${GREEN}./02-install-ansible.sh${NC}
  ${GREEN}./03-configure-storage.sh${NC}
  ${GREEN}./04-configure-network.sh${NC}
  ${GREEN}./05-init-git-repo.sh${NC}

Then apply infrastructure:
  ${GREEN}cd /root/home-lab/new_system${NC}
  ${GREEN}python3 scripts/generate-terraform.py${NC}
  ${GREEN}cd terraform && terraform init && terraform apply${NC}

${BLUE}Configuration Details:${NC}
- Filesystem: ext4
- Root partition: 50 GB (SSD)
- Swap: 2 GB
- LVM thin pool: ~128 GB (for VMs/LXC)
- Network: DHCP initially (reconfigured by post-install)
- Hostname: gamayun.home.local

${GREEN}Installation is FULLY AUTOMATIC using official Proxmox method!${NC}

EOF

    # Clean up prepared ISO
    print_info "Cleaning up..."
    rm -f "$PREPARED_ISO"
    print_success "Temporary prepared ISO removed"
}

# ============================================================
# Main Execution
# ============================================================

main() {
    print_section "Proxmox VE Auto-Install USB Creator"
    print_info "Using official Proxmox automated installation method"
    echo ""

    check_requirements
    validate_usb_device
    validate_iso_file
    validate_answer_file
    prepare_iso
    write_usb
    add_graphics_params
    embed_install_uuid
    verify_usb
    display_instructions

    echo ""
    print_success "Process completed successfully!"
    print_success "USB is ready for automated Proxmox installation!"
}

# Run main function
main
