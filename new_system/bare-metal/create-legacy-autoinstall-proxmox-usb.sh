#!/usr/bin/env bash
#
# create-legacy-autoinstall-proxmox-usb.sh
# Create Proxmox VE 9 Auto-Install USB for Legacy BIOS (MBR boot)
#
# Adapted for Dell XPS L701X with Phoenix BIOS (no UEFI support)
#
# Usage:
#   sudo ./create-legacy-autoinstall-proxmox-usb.sh <iso> <answer.toml> <usb-device>
#
# Example:
#   sudo ./create-legacy-autoinstall-proxmox-usb.sh ~/Downloads/proxmox-ve_9.0-1.iso answer.toml /dev/sdc
#
# Note:
#   If topology.yaml exists in project root, answer.toml will be auto-generated
#   from topology data (hostname, disk config, network) before creating USB.
#   This ensures the answer file matches your infrastructure definition.
#

set -euo pipefail
IFS=$'\n\t'

SCRIPT_NAME=$(basename "$0")
TMPDIR=""

cleanup() {
    local rc=${1:-$?}

    if [[ -n "${TMPDIR:-}" && -d "${TMPDIR:-}" ]]; then
        printf '%s\n' "INFO: Cleaning up temporary files..." >&2
        rm -rf "${TMPDIR}"
    fi

    # Clean up mount points
    for dir in /tmp/usbmnt.* /mnt/usb-legacy.*; do
        if [[ -d "$dir" ]] && mountpoint -q "$dir" 2>/dev/null; then
            umount "$dir" 2>/dev/null || true
        fi
        [[ -d "$dir" ]] && rmdir "$dir" 2>/dev/null || true
    done

    if [[ $rc -ne 0 ]]; then
        printf '%s\n' "${SCRIPT_NAME}: ERROR: Exited with status $rc" >&2
    fi
    exit "$rc"
}
trap 'cleanup $?' EXIT INT TERM

# Logging helpers
print_info()    { printf '%s\n' "INFO: $*" >&2; }
print_error()   { printf '%s\n' "ERROR: $*" >&2; }
print_warning() { printf '%s\n' "WARNING: $*" >&2; }
print_success() { printf '%s\n' "SUCCESS: $*" >&2; }

# Root check
check_root() {
    if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        return 1
    fi
}

# Requirements check
check_requirements() {
    local missing=()
    local cmds=(lsblk mktemp dd syslinux extlinux awk sed grep mount umount mkfs.vfat sync blkid parted proxmox-auto-install-assistant)

    for cmd in "${cmds[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -ne 0 ]]; then
        print_error "Missing required commands: ${missing[*]}"
        print_error "Install with: apt update && apt install syslinux extlinux parted dosfstools proxmox-auto-install-assistant"
        return 2
    fi
}

# Validate USB device
validate_usb_device() {
    local target="$1"
    target=$(readlink -f "$target" || echo "$target")

    if [[ ! -b "$target" ]]; then
        print_error "Target '$target' is not a block device"
        return 3
    fi

    local devname=$(basename "$target")

    if ! lsblk -dn -o NAME,TYPE | awk -v n="$devname" '$1==n && $2=="disk"{found=1} END{exit !found}'; then
        print_error "Target '$target' is not a whole-disk device"
        return 4
    fi

    # Protect root disk
    local root_src=$(findmnt -n -o SOURCE / || true)
    if [[ -n "$root_src" ]]; then
        local root_pkname=$(lsblk -no PKNAME "$root_src" 2>/dev/null || true)
        local root_disk="${root_pkname:-$(basename "$root_src" | sed -E 's/p?[0-9]+$//')}"
        if [[ "$root_disk" == "$devname" ]]; then
            print_error "Refusing to operate on system root disk ($target)"
            return 5
        fi
    fi

    print_info "Validated target: $target (device: $devname)"
}

# Generate answer.toml from topology.yaml
generate_answer_from_topology() {
    local answer_file="$1"
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local project_root="$(dirname "$script_dir")"
    local topology_file="$project_root/topology.yaml"
    local generator_script="$project_root/scripts/generate-proxmox-answer.py"

    # Check if topology.yaml exists
    if [[ ! -f "$topology_file" ]]; then
        print_warning "topology.yaml not found at: $topology_file"
        print_warning "Skipping auto-generation from topology"
        return 0
    fi

    # Check if generator script exists
    if [[ ! -f "$generator_script" ]]; then
        print_warning "Generator script not found: $generator_script"
        print_warning "Skipping auto-generation from topology"
        return 0
    fi

    # Check if Python 3 is available
    if ! command -v python3 >/dev/null 2>&1; then
        print_warning "Python 3 not found, skipping auto-generation"
        return 0
    fi

    print_info "Found topology.yaml at: $topology_file"
    print_info "Generating answer.toml from topology..."

    # Generate answer.toml
    if python3 "$generator_script" "$topology_file" "$answer_file"; then
        print_success "Generated answer.toml from topology.yaml"
        return 0
    else
        print_error "Failed to generate answer.toml from topology"
        return 6
    fi
}

# Validate answer.toml
validate_answer_file() {
    local ans_file="$1"
    if [[ ! -f "$ans_file" ]]; then
        print_error "answer.toml not found: $ans_file"
        return 6
    fi

    if ! proxmox-auto-install-assistant validate-answer "$ans_file"; then
        print_error "answer.toml validation failed"
        return 6
    fi

    print_info "answer.toml validated successfully"
}

# Update password in answer.toml
update_password_in_answer() {
    local answer_file="$1"
    local new_password="$2"

    print_info "Updating password in answer.toml..."

    # Generate password hash
    local password_hash
    password_hash=$(openssl passwd -6 "$new_password")

    # Create temporary file
    local temp_file="${answer_file}.tmp"

    # Replace password hash in answer.toml
    awk -v hash="$password_hash" '
        /^root_password = / {
            print "root_password = \"" hash "\""
            next
        }
        { print }
    ' "$answer_file" > "$temp_file"

    # Replace original file
    mv "$temp_file" "$answer_file"

    print_info "Password hash updated successfully"
}

# Create first-boot script with UUID
create_first_boot_script() {
    local install_uuid="$1"
    local script_path="$2"

    cat > "$script_path" << 'FIRSTBOOT_EOF'
#!/bin/bash
# First-boot script - Legacy BIOS Reinstall Prevention

exec 1>>/var/log/proxmox-first-boot.log 2>&1

echo "======================================================================="
echo "===== First-boot script started at $(date) ====="
echo "======================================================================="

INSTALL_ID="INSTALL_UUID_PLACEHOLDER"
echo "Installation ID: $INSTALL_ID"

# Save to system
echo -n "$INSTALL_ID" > /etc/proxmox-install-id
echo "✓ Created /etc/proxmox-install-id"

# Find MBR disk boot sector area and save marker
ROOT_DEV=$(findmnt -n -o SOURCE / | sed 's/[0-9]*$//')
if [ -n "$ROOT_DEV" ]; then
    # Save UUID marker to a file in /boot (accessible from GRUB)
    echo -n "$INSTALL_ID" > /boot/proxmox-installed
    echo "✓ Created /boot/proxmox-installed on $ROOT_DEV"
fi

echo "===== First-boot completed at $(date) ====="
FIRSTBOOT_EOF

    sed -i "s/INSTALL_UUID_PLACEHOLDER/$install_uuid/" "$script_path"
    chmod +x "$script_path"
    print_info "Created first-boot script with UUID: $install_uuid"
}

# Prepare ISO with embedded answer.toml
prepare_iso() {
    local iso_src="$1"
    local answer="$2"

    if [[ ! -f "$iso_src" || ! -f "$answer" ]]; then
        print_error "ISO or answer.toml not found"
        return 8
    fi

    if [[ -d /var/tmp ]] && [[ $(df --output=avail /var/tmp | tail -1) -gt 2000000 ]]; then
        TMPDIR=$(mktemp -d /var/tmp/pmxiso.XXXX)
    else
        TMPDIR=$(mktemp -d ./pmxiso.XXXX)
    fi
    print_info "Using tempdir $TMPDIR"

    # Use INSTALL_UUID from global scope
    local install_uuid="$INSTALL_UUID"
    echo "$install_uuid" > "$TMPDIR/install-uuid"

    # Create first-boot script OUTSIDE the --tmp directory
    # (proxmox-auto-install-assistant may clean/use the --tmp directory)
    local first_boot_script="/tmp/proxmox-first-boot-${install_uuid}.sh"
    create_first_boot_script "$install_uuid" "$first_boot_script"

    # Generate output ISO
    local output_iso="$TMPDIR/$(basename "${iso_src%.iso}")-auto-legacy.iso"

    print_info "Embedding answer.toml and first-boot script..."

    # Run proxmox-auto-install-assistant (output goes to stderr to not interfere with return value)
    set +e
    proxmox-auto-install-assistant prepare-iso \
        --fetch-from iso \
        --answer-file "$answer" \
        --output "$output_iso" \
        --tmp "$TMPDIR" \
        --on-first-boot "$first_boot_script" \
        "$iso_src" >&2
    local prepare_exit=$?
    set -e

    if [[ $prepare_exit -ne 0 ]]; then
        print_error "proxmox-auto-install-assistant failed with exit code $prepare_exit"
        rm -f "$first_boot_script"
        return 9
    fi

    if [[ ! -f "$output_iso" ]]; then
        print_error "Assistant did not create ISO"
        rm -f "$first_boot_script"
        return 9
    fi

    # Clean up temporary first-boot script
    rm -f "$first_boot_script"

    printf '%s\n' "$output_iso"
}

# Create Legacy BIOS bootable USB with MBR
create_legacy_usb() {
    local usb_device="$1"
    local iso_file="$2"

    print_info "Creating Legacy BIOS bootable USB (MBR)..."

    # Unmount partitions
    print_info "Unmounting partitions on $usb_device..."
    while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        local dev="/dev/${p##*/}"
        if findmnt "$dev" >/dev/null 2>&1; then
            umount "$dev" || true
        fi
    done < <(lsblk -ln -o NAME "$usb_device" | tail -n +2)

    # Write ISO directly (hybrid ISO supports both Legacy and UEFI)
    print_info "Writing ISO to $usb_device..."
    if ! dd if="$iso_file" of="$usb_device" bs=4M status=progress conv=fsync oflag=direct; then
        print_error "Failed to write ISO"
        return 11
    fi
    sync
    sleep 2

    print_info "USB created successfully (hybrid boot mode)"
}

# Add GRUB wrapper for reinstall prevention (Legacy BIOS version)
add_legacy_grub_wrapper() {
    local usb_device="$1"
    local install_uuid="$INSTALL_UUID"

    print_warning "=============================================="
    print_warning "LEGACY BIOS REINSTALL PREVENTION LIMITATION"
    print_warning "=============================================="
    print_warning ""
    print_warning "⚠️  Reinstall prevention does NOT work with Legacy BIOS!"
    print_warning ""
    print_warning "Why: Hybrid ISO uses read-only ISO9660 filesystem"
    print_warning "     → Cannot modify GRUB to add UUID check wrapper"
    print_warning ""
    print_warning "WORKAROUND: Manually remove USB after installation"
    print_warning ""
    print_warning "What happens:"
    print_warning "  1. Dell boots → Proxmox installer starts automatically"
    print_warning "  2. Installation completes (system powers off)"
    print_warning "  3. ⚠️  REMOVE USB BEFORE POWERING ON!"
    print_warning "  4. System boots from hard drive"
    print_warning ""
    print_warning "If you forget to remove USB:"
    print_warning "  → Dell will boot from USB again"
    print_warning "  → Installer will start (blue menu)"
    print_warning "  → Press Ctrl+C or press F12 and select hard drive"
    print_warning ""
    print_warning "Alternative: Use UEFI mode if your hardware supports it"
    print_warning "            (UEFI has full reinstall prevention)"
    print_warning ""
    print_warning "=============================================="
}

# Main function
main() {
    check_root || return 1
    check_requirements || return 2

    local iso_src="${1:-}"
    local answer_toml="${2:-}"
    local target_dev="${3:-}"

    if [[ -z "$iso_src" || -z "$answer_toml" || -z "$target_dev" ]]; then
        print_error "Usage: $SCRIPT_NAME <proxmox-iso> <answer.toml> <target-disk>"
        print_error "Example: sudo $SCRIPT_NAME proxmox-ve_9.0-1.iso answer.toml /dev/sdc"
        return 1
    fi

    # Convert to absolute paths (important when running with sudo)
    iso_src=$(realpath "$iso_src")
    answer_toml=$(realpath "$answer_toml")

    validate_usb_device "$target_dev" || return 3

    # Generate answer.toml from topology.yaml if available
    # This will overwrite existing answer.toml with topology data
    generate_answer_from_topology "$answer_toml" || true

    validate_answer_file "$answer_toml" || return 6

    # Ask for root password (unless AUTO_CONFIRM is set)
    if [[ "${AUTO_CONFIRM:-0}" != "1" ]]; then
        print_info ""
        print_info "=========================================="
        print_info "Proxmox Root Password Configuration"
        print_info "=========================================="
        print_info ""
        print_info "You can set a custom root password for Proxmox installation."
        print_info "Current password in answer.toml: proxmox"
        print_info ""
        read -p "Do you want to change the password? (y/N): " change_password

        if [[ "$change_password" =~ ^[Yy]$ ]]; then
            while true; do
                read -sp "Enter new root password: " new_password
                echo ""

                if [[ ${#new_password} -lt 5 ]]; then
                    print_error "Password too short (minimum 5 characters)"
                    continue
                fi

                read -sp "Confirm password: " new_password_confirm
                echo ""

                if [[ "$new_password" != "$new_password_confirm" ]]; then
                    print_error "Passwords don't match. Try again."
                    continue
                fi

                # Update password in answer.toml
                update_password_in_answer "$answer_toml" "$new_password"
                ROOT_PASSWORD="$new_password"
                print_success "Password updated successfully"
                break
            done
        else
            ROOT_PASSWORD="proxmox"
            print_info "Using default password: proxmox"
        fi
        print_info ""
    else
        ROOT_PASSWORD="proxmox"
        print_info "Using default password from answer.toml: proxmox"
    fi

    # Generate installation UUID
    local timezone timestamp
    timezone=$(date +%Z)
    timestamp=$(date +%Y_%m_%d_%H_%M)
    INSTALL_UUID="${timezone}_${timestamp}"
    print_info "Generated installation UUID: $INSTALL_UUID"

    # Prepare ISO
    local created_iso=""
    created_iso=$(prepare_iso "$iso_src" "$answer_toml")
    if [[ -z "$created_iso" || ! -f "$created_iso" ]]; then
        print_error "Failed to create prepared ISO"
        return 9
    fi
    print_info "Prepared ISO: $created_iso"

    # Confirm
    if [[ "${AUTO_CONFIRM:-0}" != "1" ]]; then
        print_warning "About to write ISO to $target_dev - THIS WILL DESTROY ALL DATA"
        read -r -p "Type YES to confirm: " confirm
        if [[ "$confirm" != "YES" ]]; then
            print_warning "Aborted by user"
            return 0
        fi
    fi

    # Create Legacy USB
    create_legacy_usb "$target_dev" "$created_iso" || return 11

    # Add GRUB wrapper
    add_legacy_grub_wrapper "$target_dev" || print_warning "GRUB wrapper setup encountered issues"

    print_info ""
    print_success "=========================================="
    print_success "LEGACY BIOS USB READY"
    print_success "=========================================="
    print_info ""
    print_info "Boot instructions for Dell XPS L701X (Phoenix BIOS):"
    print_info "1. Connect external monitor (Mini DisplayPort)"
    print_info "2. Insert USB into Dell XPS L701X"
    print_info "3. Power on and press F12 for boot menu"
    print_info "4. Select: 'Removable Devices' or 'USB HDD'"
    print_info "5. Proxmox installer will start automatically"
    print_info "6. Installation completes in ~10-15 minutes"
    print_info "7. System will power off after installation"
    print_info ""
    print_warning "⚠️  IMPORTANT: REMOVE USB BEFORE POWERING ON!"
    print_warning "   (Legacy BIOS doesn't support reinstall prevention)"
    print_info ""
    print_info "8. Remove USB and power on to boot Proxmox"
    print_info ""
    print_info "Installation UUID: $INSTALL_UUID"
    print_info ""
    print_info "Login credentials:"
    print_info "  Username: root"
    print_info "  Password: ${ROOT_PASSWORD:-proxmox}"
    print_info ""
    print_info "Web UI: https://<proxmox-ip>:8006"
    print_info ""
    print_warning "=============================================="
    print_warning "IF PASSWORD DOESN'T WORK AFTER INSTALLATION"
    print_warning "=============================================="
    print_warning ""
    print_warning "Legacy BIOS auto-install may not work correctly."
    print_warning "If you can't login, boot from this USB again and:"
    print_warning ""
    print_warning "1. At GRUB menu, press 'c' for command line"
    print_warning "2. Type: linux (hd0,gpt3)/vmlinuz root=/dev/sda3 init=/bin/bash"
    print_warning "3. Type: boot"
    print_warning "4. At prompt: mount -o remount,rw /"
    print_warning "5. Type: passwd root"
    print_warning "6. Enter new password"
    print_warning "7. Type: sync && reboot -f"
    print_warning ""
    print_warning "OR use UEFI mode instead (recommended)"
    print_warning ""

    return 0
}

main "$@"
