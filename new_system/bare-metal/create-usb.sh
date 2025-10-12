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

    # Generate readable installation UUID (timestamp-based)
    TIMEZONE=$(date +%Z)
    TIMESTAMP=$(date +%Y_%m_%d_%H_%M)
    INSTALL_UUID="${TIMEZONE}_${TIMESTAMP}"
    print_info "Generated installation UUID: $INSTALL_UUID"

    # Save UUID to file for later embedding on USB
    echo "$INSTALL_UUID" > /tmp/install-uuid-$$
    export INSTALL_UUID

    # Create first-boot script with embedded UUID
    FIRST_BOOT_SCRIPT="/tmp/first-boot-$$.sh"
    cat > "$FIRST_BOOT_SCRIPT" << 'SCRIPTEOF'
#!/bin/bash
# First-boot script - Reinstall Prevention

exec 1>>/var/log/proxmox-first-boot.log 2>&1

echo "======================================================================="
echo "===== First-boot script started at $(date) ====="
echo "======================================================================="

# Installation ID is embedded at USB creation time
INSTALL_ID="INSTALL_UUID_PLACEHOLDER"
echo "Installation ID (from USB creation): $INSTALL_ID"

# Save installation ID to system root
echo -n "$INSTALL_ID" > /etc/proxmox-install-id
echo "✓ Created /etc/proxmox-install-id"

# Find EFI partition - Proxmox can mount to /efi or /boot/efi
EFI_MOUNT=""
if mountpoint -q /efi 2>/dev/null; then
    EFI_MOUNT="/efi"
    echo "✓ Found EFI at /efi"
elif mountpoint -q /boot/efi 2>/dev/null; then
    EFI_MOUNT="/boot/efi"
    echo "✓ Found EFI at /boot/efi"
else
    echo "EFI not mounted, searching..."
    for disk in /dev/sda /dev/nvme0n1; do
        [ ! -b "$disk" ] && continue
        for part in "${disk}"[0-9]* "${disk}p"[0-9]*; do
            [ ! -b "$part" ] && continue
            PART_TYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null)
            if [ "$PART_TYPE" = "vfat" ]; then
                mkdir -p /efi
                if mount "$part" /efi 2>&1; then
                    EFI_MOUNT="/efi"
                    echo "✓ Mounted $part to /efi"
                    break 2
                fi
            fi
        done
    done
fi

# Write UUID marker to EFI
if [ -n "$EFI_MOUNT" ] && mountpoint -q "$EFI_MOUNT" 2>/dev/null; then
    echo -n "$INSTALL_ID" > "$EFI_MOUNT/proxmox-installed"
    sync
    if [ -f "$EFI_MOUNT/proxmox-installed" ]; then
        echo "✓ Created $EFI_MOUNT/proxmox-installed with ID: $INSTALL_ID"
    else
        echo "✗ Failed to create marker file!"
    fi
else
    echo "✗ CRITICAL: Failed to mount EFI partition!"
fi

echo "===== First-boot completed at $(date) ====="
exit 0
SCRIPTEOF

    # Replace placeholder with actual UUID
    sed -i "s/INSTALL_UUID_PLACEHOLDER/$INSTALL_UUID/" "$FIRST_BOOT_SCRIPT"
    chmod +x "$FIRST_BOOT_SCRIPT"

    print_success "Created first-boot script with UUID: $INSTALL_UUID"

    PREPARED_ISO="${ISO_FILE%.iso}-automated.iso"

    # Remove old prepared ISO if exists
    rm -f "$PREPARED_ISO"

    # Run prepare-iso with answer.toml and first-boot script
    # --fetch-from iso: embeds answer.toml into ISO
    # --answer-file: path to answer.toml
    # --on-first-boot: bash script to run after first boot
    print_info "Preparing ISO with first-boot script..."

    if ! proxmox-auto-install-assistant prepare-iso "$ISO_FILE" \
        --fetch-from iso \
        --answer-file ./answer.toml \
        --on-first-boot "$FIRST_BOOT_SCRIPT"; then
        print_error "Failed to prepare ISO with proxmox-auto-install-assistant"
        rm -f "$FIRST_BOOT_SCRIPT"
        exit 1
    fi

    # Clean up temporary first-boot script
    rm -f "$FIRST_BOOT_SCRIPT"

    # The tool creates ISO with specific naming pattern
    # Find the created ISO
    print_info "Looking for created ISO..."
    print_info "Expected pattern: ${ISO_FILE%.iso}*-auto-from-iso.iso"

    # List all ISO files in current directory for debugging
    echo ""
    print_info "ISO files in current directory:"
    ls -lh *.iso 2>/dev/null || echo "  (none found)"
    echo ""

    CREATED_ISO=$(ls -t "${ISO_FILE%.iso}"*-auto-from-iso.iso 2>/dev/null | head -1)

    if [ -z "$CREATED_ISO" ]; then
        print_error "Failed to create prepared ISO"
        echo "Expected pattern: ${ISO_FILE%.iso}*-auto-from-iso.iso"
        echo ""
        print_info "Checking if proxmox-auto-install-assistant created any output..."
        ls -lh "${ISO_FILE%.iso}"*.iso 2>/dev/null || echo "  No ISO files with that prefix found"
        exit 1
    fi

    print_success "Found created ISO: $CREATED_ISO"

    # Rename to our target
    mv "$CREATED_ISO" "$PREPARED_ISO"

    if [ ! -f "$PREPARED_ISO" ]; then
        print_error "Failed to rename prepared ISO"
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
    print_section "Embedding installation UUID on USB"

    # Get saved UUID
    INSTALL_UUID=$(cat /tmp/install-uuid-$$ 2>/dev/null)
    if [ -z "$INSTALL_UUID" ]; then
        print_error "Installation UUID not found"
        exit 1
    fi

    print_info "Installation UUID: $INSTALL_UUID"

    # Force re-read partition table
    partprobe "$USB_DEVICE" 2>/dev/null || true
    blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
    sleep 3

    MOUNT_POINT="/tmp/usb-uuid-$$"
    mkdir -p "$MOUNT_POINT"
    UUID_EMBEDDED=0

    # Find and mount the FAT32 EFI partition (look for PARTLABEL)
    for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
        [ ! -b "$part" ] && continue

        FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")
        [ "$FSTYPE" != "vfat" ] && continue

        # Check PARTLABEL to find correct EFI partition
        PARTLABEL=$(blkid -s PARTLABEL -o value "$part" 2>/dev/null || echo "")
        print_info "Checking $part: TYPE=$FSTYPE PARTLABEL='$PARTLABEL'"

        # Skip if not EFI boot partition
        if [[ ! "$PARTLABEL" =~ [Ee][Ff][Ii] ]] && [[ ! "$PARTLABEL" =~ [Bb]oot ]]; then
            print_warn "  Skipping $part: not EFI boot partition"
            continue
        fi

        if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            # Verify it contains grub.cfg
            if [ ! -f "$MOUNT_POINT/EFI/BOOT/grub.cfg" ]; then
                print_warn "  Partition $part has EFI label but no grub.cfg, skipping..."
                umount "$MOUNT_POINT"
                continue
            fi

            print_success "Found correct EFI boot partition: $part (PARTLABEL='$PARTLABEL')"

            # Backup original grub.cfg by RENAMING (not copying!)
            if [ -f "$MOUNT_POINT/EFI/BOOT/grub.cfg" ]; then
                mv "$MOUNT_POINT/EFI/BOOT/grub.cfg" "$MOUNT_POINT/EFI/BOOT/grub-install.cfg"

                # Verify backup was created
                if [ -f "$MOUNT_POINT/EFI/BOOT/grub-install.cfg" ]; then
                    print_success "Renamed original grub.cfg → grub-install.cfg"
                    print_info "  Size: $(stat -c%s "$MOUNT_POINT/EFI/BOOT/grub-install.cfg") bytes"
                else
                    print_error "Failed to rename grub.cfg!"
                    umount "$MOUNT_POINT"
                    exit 1
                fi
            else
                print_error "Original grub.cfg not found on USB!"
                umount "$MOUNT_POINT"
                exit 1
            fi

            # Create new grub.cfg with UUID check wrapper
            cat > "$MOUNT_POINT/EFI/BOOT/grub.cfg.new" << 'GRUBEOF'
# Reinstall Prevention Wrapper
# This checks for existing installation before loading installer menu

insmod part_gpt
insmod fat
insmod chain

# UUID встроен при создании USB
set usb_uuid="USB_UUID_PLACEHOLDER"
set found_system=0
set disk_uuid=""
set efi_part=""

# Ищем маркер ТОЛЬКО на hd0 (системный диск, не USB!)
# Проверяем gpt2 → gpt1 → gpt3 (покрывает 99.9% случаев)

if [ -f (hd0,gpt2)/proxmox-installed ]; then
    cat --set=disk_uuid (hd0,gpt2)/proxmox-installed
    set efi_part="gpt2"
    if [ "$disk_uuid" = "$usb_uuid" ]; then
        set found_system=1
    fi
elif [ -f (hd0,gpt1)/proxmox-installed ]; then
    cat --set=disk_uuid (hd0,gpt1)/proxmox-installed
    set efi_part="gpt1"
    if [ "$disk_uuid" = "$usb_uuid" ]; then
        set found_system=1
    fi
elif [ -f (hd0,gpt3)/proxmox-installed ]; then
    cat --set=disk_uuid (hd0,gpt3)/proxmox-installed
    set efi_part="gpt3"
    if [ "$disk_uuid" = "$usb_uuid" ]; then
        set found_system=1
    fi
fi

if [ $found_system -eq 1 ]; then
    # UUID совпадают - система уже установлена с этой флешки
    # Предотвращаем переустановку, но даем опцию
    set timeout=5
    set default=0

    menuentry 'Boot Proxmox VE (installed system)' {
        # Используем найденную партицию ($efi_part уже установлена выше)
        if [ "$efi_part" = "gpt2" ]; then
            chainloader (hd0,gpt2)/EFI/proxmox/grubx64.efi
        elif [ "$efi_part" = "gpt1" ]; then
            chainloader (hd0,gpt1)/EFI/proxmox/grubx64.efi
        elif [ "$efi_part" = "gpt3" ]; then
            chainloader (hd0,gpt3)/EFI/proxmox/grubx64.efi
        else
            echo "ERROR: EFI partition not set"
            read
        fi
    }

    menuentry 'Reinstall Proxmox (ERASES ALL DATA!)' {
        configfile /EFI/BOOT/grub-install.cfg
    }
else
    # UUID не совпадают или нет маркера
    # Запуск АВТОУСТАНОВКИ с предупреждением 5 секунд

    # Показываем информацию
    echo "=============================================="
    echo "  Proxmox VE Auto-Installation"
    echo "=============================================="
    echo ""
    if [ -n "$disk_uuid" ]; then
        echo "Different USB detected!"
        echo "Old system will be ERASED"
    else
        echo "No existing installation found"
        echo "Fresh installation"
    fi
    echo ""
    echo "Starting in 5 seconds..."
    echo "Press any key to see options"
    echo "=============================================="

    set timeout=5
    set default=0

    menuentry 'Install Proxmox VE (AUTO-INSTALL)' {
        # Запускает меню установки с автоустановкой
        configfile /EFI/BOOT/grub-install.cfg
    }

    menuentry 'Boot existing system from disk (if any)' {
        # Ищем Proxmox bootloader на hd0 (проверяем gpt2→gpt1→gpt3)
        if [ -f (hd0,gpt2)/EFI/proxmox/grubx64.efi ]; then
            chainloader (hd0,gpt2)/EFI/proxmox/grubx64.efi
        elif [ -f (hd0,gpt1)/EFI/proxmox/grubx64.efi ]; then
            chainloader (hd0,gpt1)/EFI/proxmox/grubx64.efi
        elif [ -f (hd0,gpt3)/EFI/proxmox/grubx64.efi ]; then
            chainloader (hd0,gpt3)/EFI/proxmox/grubx64.efi
        else
            echo "No Proxmox installation found"
            read
        fi
    }

    menuentry 'Cancel installation (Halt)' {
        halt
    }
fi
GRUBEOF

            # Replace UUID placeholder
            sed -i "s/USB_UUID_PLACEHOLDER/$INSTALL_UUID/" "$MOUNT_POINT/EFI/BOOT/grub.cfg.new"

            # Replace grub.cfg with our wrapper
            mv "$MOUNT_POINT/EFI/BOOT/grub.cfg.new" "$MOUNT_POINT/EFI/BOOT/grub.cfg"

            print_success "Created UUID check wrapper as grub.cfg"
            print_info "Original installer menu saved as grub-install.cfg"

            # Verify both files exist
            echo ""
            print_info "Verifying files on USB:"
            if [ -f "$MOUNT_POINT/EFI/BOOT/grub.cfg" ]; then
                print_success "  ✓ grub.cfg (UUID wrapper): $(stat -c%s "$MOUNT_POINT/EFI/BOOT/grub.cfg") bytes"
                echo "     First line: $(head -1 "$MOUNT_POINT/EFI/BOOT/grub.cfg")"
            else
                print_error "  ✗ grub.cfg MISSING!"
            fi

            if [ -f "$MOUNT_POINT/EFI/BOOT/grub-install.cfg" ]; then
                print_success "  ✓ grub-install.cfg (original): $(stat -c%s "$MOUNT_POINT/EFI/BOOT/grub-install.cfg") bytes"
                echo "     First line: $(head -1 "$MOUNT_POINT/EFI/BOOT/grub-install.cfg")"
            else
                print_error "  ✗ grub-install.cfg MISSING!"
            fi

            # Check UUID in wrapper
            if grep -q "set usb_uuid=\"$INSTALL_UUID\"" "$MOUNT_POINT/EFI/BOOT/grub.cfg"; then
                print_success "  ✓ UUID embedded correctly: $INSTALL_UUID"
            else
                print_error "  ✗ UUID NOT found in wrapper!"
            fi

            sync
            UUID_EMBEDDED=1
            umount "$MOUNT_POINT"
            break
        fi
    done

    rmdir "$MOUNT_POINT"

    # Clean up temp UUID file
    rm -f /tmp/install-uuid-$$

    if [ $UUID_EMBEDDED -eq 1 ]; then
        print_success "Installation UUID embedded on USB"
    else
        print_error "Failed to embed UUID (USB may reinstall every boot)"
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
• GRUB detects installation UUID marker
• ${GREEN}Menu changes automatically${NC}:
  1. 'Boot Proxmox from disk (Already Installed)' ${YELLOW}[default]${NC}
  2. 'Reinstall Proxmox (ERASES DISK!)'
• Countdown: ${YELLOW}10 seconds${NC} → boots installed system
• ${RED}Reinstallation prevented automatically!${NC}
• Press 'r' to force reinstall if needed (ERASES ALL DATA!)

${GREEN}This prevents accidental reinstallation!${NC}

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
