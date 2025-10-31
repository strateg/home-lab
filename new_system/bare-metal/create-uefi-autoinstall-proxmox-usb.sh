#!/usr/bin/env bash
#
# create-uefi-autoinstall-proxmox-usb.sh — Production-ready UEFI USB creator
#
# Creates auto-installing Proxmox VE USB for UEFI systems with optional reinstall prevention.
#
# Features:
#   - Auto-generates answer.toml from topology.yaml (Infrastructure-as-Data)
#   - UEFI boot support (recommended for modern systems)
#   - UUID-based reinstall prevention (optional)
#   - Interactive password configuration
#
# Usage:
#   sudo ./create-uefi-autoinstall-proxmox-usb.sh <proxmox-iso> <answer.toml> <target-disk>
# Example:
#   sudo ./create-uefi-autoinstall-proxmox-usb.sh proxmox-ve_9.0-1.iso answer.toml /dev/sdb
#
# Password Configuration:
#   1. Default hash is read from topology/security.yaml → proxmox.root_password_hash
#   2. Generate answer.toml calls generate-proxmox-answer.py which reads the hash
#   3. Interactive mode: user can override by entering custom password
#   4. Non-interactive mode: can override with ROOT_PASSWORD_HASH env var
#   Single source of truth: topology/security.yaml (unless explicitly overridden)
#
# Environment variables:
#   ROOT_PASSWORD_HASH       - precomputed password hash to override topology default
#   AUTO_CONFIRM=1           - skip interactive confirmation (for automation)
#   SKIP_UUID_PROTECTION=1   - disable UUID-based reinstall prevention (allows forced reinstall)
#
set -euo pipefail
IFS=$'\n\t'

# Set restrictive umask for temporary files (no access for group/others)
umask 077

SCRIPT_NAME=$(basename "$0")
TMPDIR=""

cleanup() {
    local rc=${1:-$?}

    # Remove temporary directory (includes temporary ISO)
    if [[ -n "${TMPDIR:-}" && -d "${TMPDIR:-}" ]]; then
        printf '%s\n' "INFO: Cleaning up temporary files in $TMPDIR..." >&2
        rm -rf "${TMPDIR}"
    fi

    # Clean up any leftover temp directories from previous runs
    for pattern in /tmp/pmxiso.* /var/tmp/pmxiso.* ./pmxiso.*; do
        for dir in $pattern; do
            if [[ -d "$dir" ]]; then
                rm -rf "$dir" 2>/dev/null || true
            fi
        done
    done

    # Unmount any temporary mount points (best-effort)
    for dir in /tmp/usbmnt.* /tmp/usb-uuid.*; do
        if [[ -d "$dir" ]] && mountpoint -q "$dir" 2>/dev/null; then
            umount "$dir" 2>/dev/null || true
        fi
        if [[ -d "$dir" ]]; then
            rmdir "$dir" 2>/dev/null || true
        fi
    done

    if [[ $rc -ne 0 ]]; then
        printf '%s\n' "${SCRIPT_NAME}: ERROR: Exited with status $rc" >&2
    fi
    exit "$rc"
}
trap 'cleanup $?' EXIT INT TERM

# --- logging helpers (info -> stderr, data -> stdout) ---
print_info()    { printf '%s\n' "INFO: $*" >&2; }
print_error()   { printf '%s\n' "ERROR: $*" >&2; }
print_warning() { printf '%s\n' "WARNING: $*" >&2; }
print_success() { printf '%s\n' "SUCCESS: $*" >&2; }

# --- root check ---
check_root() {
    if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        return 1
    fi
    return 0
}

# --- requirements check ---
check_requirements() {
    local missing=()
    local cmds=(lsblk mktemp dd awk sed findmnt find grep mount umount cp mv date sync blkid partprobe blockdev proxmox-auto-install-assistant)

    for cmd in "${cmds[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -ne 0 ]]; then
        print_error "Missing required commands: ${missing[*]}"
        print_error "Install with: apt update && apt install ${missing[*]}"
        return 2
    fi

    return 0
}

# --- check available disk space (in KB) ---
check_disk_space() {
    local path="$1"
    local required_mb="$2"
    local purpose="${3:-operations}"

    if [[ -z "$path" || -z "$required_mb" ]]; then
        print_error "check_disk_space requires <path> <required_mb>"
        return 1
    fi

    # Check if path exists
    if [[ ! -e "$path" ]]; then
        print_error "Path does not exist: $path"
        return 1
    fi

    # Get available space in KB
    local avail_kb
    avail_kb=$(df --output=avail "$path" 2>/dev/null | tail -1)

    # Check if df succeeded and returned valid number
    if [[ -z "$avail_kb" ]]; then
        print_error "Cannot determine available space on: $path"
        return 1
    fi

    # Validate it's a number and positive
    if ! [[ "$avail_kb" =~ ^[0-9]+$ ]] || [[ "$avail_kb" -le 0 ]]; then
        print_error "Invalid disk space value for: $path (got: $avail_kb)"
        return 1
    fi

    # Convert to MB
    local avail_mb=$((avail_kb / 1024))
    local required_kb=$((required_mb * 1024))

    print_info "Disk space check for $purpose:"
    print_info "  Location: $path"
    print_info "  Available: ${avail_mb} MB"
    print_info "  Required: ${required_mb} MB"

    if [[ $avail_kb -lt $required_kb ]]; then
        print_error "Insufficient disk space for $purpose"
        print_error "  Need at least ${required_mb} MB, but only ${avail_mb} MB available"
        return 1
    fi

    print_info "  ✓ Sufficient space available"
    return 0
}

# --- wait for device to be ready (handles race conditions) ---
wait_for_device_ready() {
    local device="$1"
    local max_retries="${2:-10}"
    local retry=0

    if [[ -z "$device" || ! -b "$device" ]]; then
        print_error "wait_for_device_ready: invalid device: $device"
        return 1
    fi

    print_info "Waiting for device $device to be ready..."

    # Force kernel to re-read partition table
    partprobe "$device" 2>/dev/null || true
    blockdev --rereadpt "$device" 2>/dev/null || true

    # Wait for udev to settle (process device changes)
    if command -v udevadm >/dev/null 2>&1; then
        udevadm settle --timeout=10 2>/dev/null || true
    fi

    # Retry loop: wait for partitions to appear
    while [[ $retry -lt $max_retries ]]; do
        # Check if device has readable partitions
        if lsblk -ln -o NAME "$device" 2>/dev/null | tail -n +2 | grep -q .; then
            if [[ $retry -eq 0 ]]; then
                print_info "Device ready immediately"
            else
                print_info "Device ready after $retry retries"
            fi
            sleep 1  # Extra settling time
            return 0
        fi

        retry=$((retry + 1))
        print_info "Waiting for partitions... (attempt $retry/$max_retries)"
        sleep 1
    done

    print_warning "Device partitions not detected after $max_retries retries (may be normal for some devices)"
    return 0  # Don't fail, might be OK
}

# --- validate that provided device is a whole-disk and not system disk ---
validate_usb_device() {
    local target="$1"
    if [[ -z "$target" ]]; then
        print_error "No target device provided"
        return 2
    fi

    target=$(readlink -f "$target" || echo "$target")
    if [[ ! -b "$target" ]]; then
        print_error "Target '$target' is not a block device"
        return 3
    fi

    local devname
    devname=$(basename "$target")

    # Ensure it's type 'disk' according to lsblk
    if ! lsblk -dn -o NAME,TYPE | awk -v n="$devname" '$1==n && $2=="disk"{found=1} END{exit !found}'; then
        print_error "Target '$target' is not a whole-disk device (must be /dev/sdX or /dev/nvme0n1)"
        return 4
    fi

    # Protect root disk: find what disk contains '/'
    local root_src root_pkname root_disk
    root_src=$(findmnt -n -o SOURCE / || true)
    if [[ -n "$root_src" ]]; then
        # try to get PKNAME (parent disk) via lsblk for partitions; fallback to stripping partition suffix
        root_pkname=$(lsblk -no PKNAME "$root_src" 2>/dev/null || true)
        if [[ -n "$root_pkname" ]]; then
            root_disk="$root_pkname"
        else
            root_disk=$(basename "$root_src" | sed -E 's/p?[0-9]+$//')
        fi
        if [[ "$root_disk" == "$devname" ]]; then
            print_error "Refusing to operate on system root disk ($target)"
            return 5
        fi
    fi

    print_info "Validated target: $target (device: $devname)"
    return 0
}

# --- generate answer.toml from topology.yaml ---
generate_answer_from_topology() {
    local answer_file="$1"
    local script_dir
    local project_root
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    project_root="$(dirname "$script_dir")"
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

    # Backup existing answer.toml if it exists
    if [[ -f "$answer_file" ]]; then
        cp "$answer_file" "${answer_file}.backup-$(date +%s)" 2>/dev/null || true
        print_info "Backed up existing answer.toml"
    fi

    # Generate answer.toml
    if python3 "$generator_script" "$topology_file" "$answer_file"; then
        print_success "Generated answer.toml from topology.yaml"

        # Verify generated file is valid
        if [[ ! -f "$answer_file" ]]; then
            print_error "Generator succeeded but answer.toml not created"
            return 6
        fi

        if [[ ! -s "$answer_file" ]]; then
            print_error "Generated answer.toml is empty"
            return 6
        fi

        return 0
    else
        print_error "Failed to generate answer.toml from topology"

        # Try to restore backup if generation failed
        local backup_file
        backup_file=$(find "$(dirname "$answer_file")" -maxdepth 1 -name "$(basename "$answer_file").backup-*" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
        if [[ -n "$backup_file" && -f "$backup_file" ]]; then
            print_warning "Attempting to restore backup: $backup_file"
            cp "$backup_file" "$answer_file" || true
        fi

        return 6
    fi
}

# --- validate ISO file (security checks) ---
# Returns canonical path via stdout, error messages via stderr
validate_iso_file() {
    local iso_file="$1"

    if [[ -z "$iso_file" ]]; then
        print_error "No ISO file provided"
        return 1
    fi

    # Resolve to canonical path (prevents path traversal and symlink attacks)
    local iso_path
    iso_path=$(readlink -f "$iso_file" 2>/dev/null || echo "")
    if [[ -z "$iso_path" ]]; then
        print_error "Cannot resolve path to ISO: $iso_file"
        return 1
    fi

    # Check file exists and is a regular file (not device, socket, etc.)
    if [[ ! -f "$iso_path" ]]; then
        print_error "ISO file not found or not a regular file: $iso_path"
        return 1
    fi

    # Check file is readable
    if [[ ! -r "$iso_path" ]]; then
        print_error "ISO file not readable: $iso_path"
        return 1
    fi

    # Basic magic number check (ISO9660 signature at offset 0x8001)
    if command -v file >/dev/null 2>&1; then
        local file_type
        file_type=$(file -b "$iso_path" 2>/dev/null || echo "")
        if [[ ! "$file_type" =~ [Ii][Ss][Oo] ]]; then
            print_warning "File does not appear to be an ISO image: $file_type"
            print_warning "Proceeding anyway, but this may fail..."
        fi
    fi

    print_info "ISO file validated: $iso_path"

    # Return canonical path to caller (via stdout)
    printf '%s' "$iso_path"
    return 0
}

# --- validate answer file (via official tool) ---
validate_answer_file() {
    local ans_file="$1"
    if [[ -z "$ans_file" || ! -f "$ans_file" ]]; then
        print_error "answer.toml not found: ${ans_file:-<empty>}"
        return 6
    fi

    if ! proxmox-auto-install-assistant validate-answer "$ans_file"; then
        print_error "answer.toml validation failed"
        return 6
    fi

    print_info "answer.toml validated successfully"
    return 0
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

# --- safely set (or replace) root_password in answer.toml ---
set_root_password() {
    local ans_file="$1"
    local hash_value="$2"
    if [[ -z "$ans_file" || -z "$hash_value" ]]; then
        print_error "set_root_password requires <file> and <hash>"
        return 7
    fi
    if [[ ! -f "$ans_file" ]]; then
        print_error "answer file missing: $ans_file"
        return 6
    fi

    local tmp
    tmp="$(mktemp "${ans_file}.tmp.XXXX")"

    # Replace root_password line or add if missing (safe, preserves other file content)
    awk -v hv="$hash_value" '
    BEGIN{re="^[[:space:]]*root_password[[:space:]]*="; replaced=0}
    {
      if ($0 ~ re) {
        print "root_password = \"" hv "\"";
        replaced=1;
      } else {
        print $0;
      }
    }
    END{ if (replaced==0) print "root_password = \"" hv "\""}
    ' "$ans_file" > "$tmp"

    cp -a "$ans_file" "${ans_file}.bak" 2>/dev/null || true
    mv -f "$tmp" "$ans_file"
    print_info "Updated root_password in $ans_file (backup at ${ans_file}.bak)"
    return 0
}

# --- create first-boot script with UUID marker ---
create_first_boot_script() {
    local install_uuid="$1"
    local script_path="$2"

    if [[ -z "$install_uuid" || -z "$script_path" ]]; then
        print_error "create_first_boot_script requires <uuid> <path>"
        return 7
    fi

    cat > "$script_path" << 'FIRSTBOOT_EOF'
#!/bin/bash
# First-boot script - Reinstall Prevention
# This script runs after Proxmox installation to mark the system as installed

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

# Find EFI partition ON THE SAME DISK as root filesystem (not USB!)
EFI_MOUNT=""
if mountpoint -q /efi 2>/dev/null; then
    EFI_MOUNT="/efi"
    echo "✓ Found EFI at /efi"
elif mountpoint -q /boot/efi 2>/dev/null; then
    EFI_MOUNT="/boot/efi"
    echo "✓ Found EFI at /boot/efi"
else
    echo "EFI not mounted, searching on root device..."
    # Find device where root is installed
    # Handle both traditional (sda3) and NVMe (nvme0n1p3) naming
    ROOT_SRC=$(findmnt -n -o SOURCE /)
    ROOT_DEV=$(echo "$ROOT_SRC" | sed -E 's/p?[0-9]+$//')
    echo "Root source: $ROOT_SRC"
    echo "Root device: $ROOT_DEV"

    if [ -n "$ROOT_DEV" ]; then
        for part in "${ROOT_DEV}"[0-9]* "${ROOT_DEV}p"[0-9]*; do
            [ ! -b "$part" ] && continue
            PART_TYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null)
            if [ "$PART_TYPE" = "vfat" ]; then
                mkdir -p /efi
                echo "Attempting to mount $part to /efi..."
                if mount "$part" /efi 2>&1 | tee -a /var/log/proxmox-first-boot.log; then
                    EFI_MOUNT="/efi"
                    echo "✓ Mounted $part to /efi"
                    break
                else
                    echo "✗ Failed to mount $part"
                fi
            fi
        done
    fi
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
FIRSTBOOT_EOF

    # Replace placeholder with actual UUID
    sed -i "s/INSTALL_UUID_PLACEHOLDER/$install_uuid/" "$script_path"
    chmod +x "$script_path"

    print_info "Created first-boot script with UUID: $install_uuid"
    return 0
}

# --- prepare ISO with embedded answer.toml and first-boot script ---
# Outputs: prints the path to created ISO to stdout only (all informational text -> stderr)
prepare_iso() {
    local iso_src="$1"
    local answer="$2"

    if [[ -z "$iso_src" || -z "$answer" ]]; then
        print_error "prepare_iso requires <original-iso> <answer.toml>"
        return 8
    fi
    if [[ ! -f "$iso_src" ]]; then
        print_error "Original ISO not found: $iso_src"
        return 9
    fi
    if [[ ! -f "$answer" ]]; then
        print_error "answer.toml not found: $answer"
        return 6
    fi

    # Calculate required space: ISO size * 3 (for extraction + modifications)
    local iso_size_kb
    iso_size_kb=$(du -k "$iso_src" | cut -f1)
    local required_mb=$(( (iso_size_kb * 3) / 1024 ))

    print_info "ISO size: $((iso_size_kb / 1024)) MB"
    print_info "Required temp space: ~${required_mb} MB (3x ISO size for extraction)"

    # Try /var/tmp first (on disk, not RAM)
    if [[ -d /var/tmp ]] && check_disk_space /var/tmp "$required_mb" "temporary ISO processing"; then
        TMPDIR=$(mktemp -d /var/tmp/pmxiso.XXXX)
        print_info "Using /var/tmp for temporary files"
    # Fallback to current directory
    elif check_disk_space . "$required_mb" "temporary ISO processing"; then
        print_warning "/var/tmp has insufficient space, using current directory"
        TMPDIR=$(mktemp -d ./pmxiso.XXXX)
        print_info "Using current directory for temporary files"
    else
        print_error "Insufficient disk space for ISO processing"
        print_error "Need at least ${required_mb} MB free space"
        return 13
    fi

    # Use INSTALL_UUID from global scope (set by main() before calling prepare_iso)
    local install_uuid="$INSTALL_UUID"

    # Save UUID to temp file for later use (if needed)
    echo "$install_uuid" > "$TMPDIR/install-uuid"

    # Create first-boot script with UUID
    local first_boot_script="$TMPDIR/first-boot.sh"
    create_first_boot_script "$install_uuid" "$first_boot_script"

    # Generate output ISO filename
    local output_iso
    output_iso="$TMPDIR/$(basename "${iso_src%.iso}")-auto-from-iso.iso"

    print_info "Embedding answer.toml and first-boot script using proxmox-auto-install-assistant..."

    # Run prepare-iso with first-boot script (capture output but preserve exit code)
    local paa_output paa_exit
    paa_output=$(proxmox-auto-install-assistant prepare-iso \
        --fetch-from iso \
        --answer-file "$answer" \
        --output "$output_iso" \
        --tmp "$TMPDIR" \
        --on-first-boot "$first_boot_script" \
        "$iso_src" 2>&1)
    paa_exit=$?

    # Print output to stderr (logs)
    echo "$paa_output" >&2

    if [[ $paa_exit -ne 0 ]]; then
        print_error "proxmox-auto-install-assistant failed with exit code: $paa_exit"
        return 9
    fi

    # Verify created ISO exists
    local created_iso="$output_iso"
    if [[ ! -f "$created_iso" ]]; then
        print_error "Assistant did not create ISO at: $created_iso"
        print_info "Contents of $TMPDIR:"
        ls -la "$TMPDIR" >&2 || true
        print_info "Looking for any ISO files in tempdir:"
        find "$TMPDIR" -type f -name "*.iso" >&2 || true
        return 9
    fi

    # Print created ISO path to stdout (machine-consumable)
    printf '%s\n' "$created_iso"
    return 0
}

# NOTE: add_auto_installer_mode() function was removed as dead code
# proxmox-auto-install-assistant already embeds auto-installer-mode.toml in the ISO
# After dd, ISO partitions become read-only, so manual addition is not possible anyway

# --- add graphics params for Dell XPS L701X to USB (after write) ---
add_graphics_params() {
    local usb_device="$1"
    if [[ -z "$usb_device" || ! -b "$usb_device" ]]; then
        print_error "add_graphics_params requires valid USB device"
        return 10
    fi

    print_info "Adding graphics parameters for Dell XPS L701X (external display)..."

    # Wait for device to be ready (handles race conditions)
    wait_for_device_ready "$usb_device"

    local mount_point
    mount_point=$(mktemp -d -t usbmnt.XXXX)
    local modified=0

    # Use lsblk to list partition names (handles nvme, mmcblk, sd, etc.)
    while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        local part="/dev/${p##*/}"
        [[ ! -b "$part" ]] && continue

        local fstype
        fstype=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

        # Check both vfat and hfsplus (Proxmox ISO hybrid)
        if [[ "$fstype" == "vfat" || "$fstype" == "hfsplus" ]]; then
            if mount -o rw "$part" "$mount_point" 2>/dev/null; then
                # Modify both grub.cfg (UUID wrapper) and grub-install.cfg (original installer menu)
                local grub_files=()

                # Find all GRUB config files
                while IFS= read -r grub_file; do
                    grub_files+=("$grub_file")
                done < <(find "$mount_point" -type f \( -name "grub.cfg" -o -name "grub-install.cfg" \) 2>/dev/null)

                if [[ ${#grub_files[@]} -gt 0 ]]; then
                    for grub_cfg in "${grub_files[@]}"; do
                        print_info "Found GRUB config: ${grub_cfg#"$mount_point"/}"

                        # Backup before modification
                        cp -a "$grub_cfg" "${grub_cfg}.backup-$(date +%s)" || true

                        if grep -q "video=vesafb" "$grub_cfg" 2>/dev/null; then
                            print_info "  Graphics parameters already present in ${grub_cfg##*/}"
                        else
                            print_info "  Adding graphics parameters to ${grub_cfg##*/}..."
                            # Proxmox uses /boot/linux26 path for kernel
                            sed -i '/linux.*\/boot\/linux26/ s|$| video=vesafb:ywrap,mtrr vga=791 nomodeset|' "$grub_cfg" || true
                            print_info "  ✓ Graphics parameters added to ${grub_cfg##*/}"
                            modified=1
                        fi
                    done

                    sync
                fi

                umount "$mount_point" >/dev/null 2>&1 || true
                break
            fi
        fi
    done < <(lsblk -ln -o NAME "$usb_device" | tail -n +2)

    rmdir "$mount_point" >/dev/null 2>&1 || true

    if [[ $modified -eq 1 ]]; then
        print_info "GRUB configuration updated for external display support"
    else
        print_warning "Could not modify GRUB (external display may not work) — manual edit may be required"
    fi

    return 0
}

# --- embed UUID wrapper in grub.cfg (prevents reinstallation loop) ---
embed_uuid_wrapper() {
    local usb_device="$1"
    if [[ -z "$usb_device" || ! -b "$usb_device" ]]; then
        print_error "embed_uuid_wrapper requires valid USB device"
        return 10
    fi

    # Get UUID from environment variable (exported by prepare_iso)
    # Skip UUID check if SKIP_UUID_PROTECTION=1
    local install_uuid=""
    if [[ "${SKIP_UUID_PROTECTION:-0}" != "1" ]]; then
        if [[ -n "${INSTALL_UUID:-}" ]]; then
            install_uuid="$INSTALL_UUID"
            print_info "Embedding UUID wrapper in GRUB (prevents reinstallation loop)..."
            print_info "Installation UUID: $install_uuid"
        else
            print_warning "Installation UUID not found in environment, skipping UUID wrapper"
            return 0
        fi
    else
        print_info "UUID protection disabled (SKIP_UUID_PROTECTION=1)"
    fi

    # Wait for device to be ready (handles race conditions)
    wait_for_device_ready "$usb_device"

    local mount_point
    mount_point=$(mktemp -d -t usbmnt.XXXX)
    local embedded=0

    # Find EFI partition (can be vfat or hfsplus for Proxmox ISO)
    while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        local part="/dev/${p##*/}"
        [[ ! -b "$part" ]] && continue

        local fstype
        fstype=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

        # Check both vfat (standard EFI) and hfsplus (Proxmox ISO hybrid)
        if [[ "$fstype" == "vfat" || "$fstype" == "hfsplus" ]]; then
            if mount -o rw "$part" "$mount_point" 2>/dev/null; then
                # Check if this has EFI/BOOT/grub.cfg
                if [[ -f "$mount_point/EFI/BOOT/grub.cfg" ]]; then
                    print_info "Found EFI boot partition: $part ($fstype)"

                    # Backup original grub.cfg by RENAMING
                    if [[ -f "$mount_point/EFI/BOOT/grub.cfg" ]]; then
                        mv "$mount_point/EFI/BOOT/grub.cfg" "$mount_point/EFI/BOOT/grub-install.cfg"
                        print_info "Renamed original grub.cfg → grub-install.cfg"
                    fi

                    # Check if UUID protection should be skipped
                    if [[ "${SKIP_UUID_PROTECTION:-0}" == "1" ]]; then
                        print_warning "UUID protection DISABLED (SKIP_UUID_PROTECTION=1)"
                        print_warning "This USB will ALWAYS reinstall Proxmox on boot!"
                        print_warning "Remove USB after installation to prevent reinstall loops!"

                        # Find and copy REAL installer menu from HFS+ partition
                        local hfs_mount
                        hfs_mount=$(mktemp -d -t hfs-mount.XXXX)
                        local found_installer=0

                        # Search for HFS+ partition with installer grub.cfg
                        while IFS= read -r hp; do
                            [[ -z "$hp" ]] && continue
                            local hfs_part="/dev/${hp##*/}"
                            [[ ! -b "$hfs_part" ]] && continue

                            local hfs_fstype
                            hfs_fstype=$(blkid -s TYPE -o value "$hfs_part" 2>/dev/null || echo "")

                            if [[ "$hfs_fstype" == "hfsplus" ]] || [[ "$hfs_fstype" == "iso9660" ]]; then
                                if mount -o ro "$hfs_part" "$hfs_mount" 2>/dev/null; then
                                    if [[ -f "$hfs_mount/boot/grub/grub.cfg" ]]; then
                                        print_info "Found installer menu on $hfs_part"
                                        cp "$hfs_mount/boot/grub/grub.cfg" "$mount_point/EFI/BOOT/grub.cfg"
                                        print_info "Copied real installer menu to EFI/BOOT/grub.cfg"
                                        found_installer=1
                                        umount "$hfs_mount" 2>/dev/null || true
                                        break
                                    else
                                        umount "$hfs_mount" 2>/dev/null || true
                                    fi
                                fi
                            fi
                        done < <(lsblk -ln -o NAME "$usb_device" | tail -n +2)

                        rmdir "$hfs_mount" 2>/dev/null || true

                        if [[ $found_installer -eq 0 ]]; then
                            print_error "Could not find installer menu on HFS+/ISO9660 partition"
                            print_error "USB may not boot correctly!"
                        fi

                        sync
                        embedded=1
                        umount "$mount_point" >/dev/null 2>&1 || true
                        break
                    fi

                    # Create UUID check wrapper (default behavior)
                    cat > "$mount_point/EFI/BOOT/grub.cfg" << 'GRUB_EOF'
# Reinstall Prevention Wrapper
# Checks for existing installation before loading installer menu

insmod part_gpt
insmod fat
insmod chain

# UUID embedded at USB creation time
set usb_uuid="USB_UUID_PLACEHOLDER"
set found_system=0
set disk_uuid=""
set efi_part=""
set disk=""

# Debug output
echo "======================================"
echo "Proxmox Auto-Installer (UUID Protection)"
echo "======================================"
echo "USB UUID: $usb_uuid"
echo "Searching for existing installation..."
echo ""

# Search for proxmox-installed marker on system disks
# The first-boot script creates this file only on the system disk EFI partition
# Check multiple disks (hd0-hd3) and partitions (gpt1-gpt3) to handle various configurations

# Loop through disks: hd0, hd1, hd2, hd3 (covers most systems)
for check_disk in hd0 hd1 hd2 hd3; do
    if [ $found_system -eq 1 ]; then
        break
    fi

    # Loop through common EFI partition locations: gpt1, gpt2, gpt3
    for check_part in gpt1 gpt2 gpt3; do
        if [ $found_system -eq 1 ]; then
            break
        fi

        # Check if marker file exists
        if test -f "($check_disk,$check_part)/proxmox-installed"; then
            # Read UUID from marker file
            cat --set=disk_uuid "($check_disk,$check_part)/proxmox-installed"
            echo "Found marker on ($check_disk,$check_part): $disk_uuid"

            # Compare UUIDs
            if [ "$disk_uuid" = "$usb_uuid" ]; then
                set found_system=1
                set efi_part="$check_part"
                set disk="$check_disk"
                echo "UUID MATCH! System installed with this USB."
                echo "Disk: $disk, Partition: $efi_part"
            else
                echo "UUID MISMATCH on ($check_disk,$check_part)"
                echo "  Expected: $usb_uuid"
                echo "  Found: $disk_uuid"
                echo "  (Different USB was used for installation)"
            fi
        fi
    done
done

echo ""
if [ $found_system -eq 1 ]; then
    # UUID matches - system already installed with this USB
    # Boot installed system by default, offer reinstall option
    echo "======================================"
    echo "DECISION: Boot installed system (UUID matches)"
    echo "======================================"
    echo ""
    echo "Press any key to see menu..."
    sleep 3

    set timeout=5
    set default=0

    menuentry 'Boot Proxmox VE (Already Installed)' {
        # Build boot path dynamically from detected disk and partition
        echo "Detected installation:"
        echo "  Disk: $disk"
        echo "  EFI Partition: $efi_part"
        echo ""
        echo "Chainloading from: ($disk,$efi_part)/EFI/proxmox/grubx64.efi"

        # Verify bootloader exists before attempting chainload
        # Note: test -f in GRUB requires direct path substitution, not string variables
        if test -f "($disk,$efi_part)/EFI/proxmox/grubx64.efi"; then
            chainloader "($disk,$efi_part)/EFI/proxmox/grubx64.efi"
            boot
        else
            echo "ERROR: Proxmox bootloader not found at: ($disk,$efi_part)/EFI/proxmox/grubx64.efi"
            echo ""
            echo "Attempting alternative locations..."

            # Try alternative paths (in case Proxmox installed differently)
            for alt_part in gpt1 gpt2 gpt3; do
                if test -f "($disk,$alt_part)/EFI/proxmox/grubx64.efi"; then
                    echo "Found at: ($disk,$alt_part)/EFI/proxmox/grubx64.efi"
                    chainloader "($disk,$alt_part)/EFI/proxmox/grubx64.efi"
                    boot
                fi
            done

            echo "ERROR: Could not find Proxmox bootloader on any partition!"
            echo "Press any key to return to menu..."
            read
        fi
    }

    menuentry 'Reinstall Proxmox (ERASES ALL DATA!)' {
        configfile /EFI/BOOT/grub-install.cfg
    }
else
    # UUID doesn't match or no marker found - proceed with installation
    echo "======================================"
    echo "DECISION: Proceed with installation"
    echo "Reason: No marker found OR UUID mismatch"
    echo "======================================"
    echo ""
    echo "Press any key to see menu..."
    sleep 3

    set timeout=5
    set default=0

    menuentry 'Install Proxmox VE (AUTO-INSTALL)' {
        # Search for Proxmox ISO partition by trying different methods
        # Method 1: Search by common Proxmox labels (version-agnostic pattern)
        set isopart=""

        # Try labels: pve-9, pve-8, pve-10, etc (common pattern)
        for label in pve-9 pve-8 pve-10 pve-11 pve-7; do
            search --no-floppy --label --set=isopart "$label"
            if [ -n "$isopart" ]; then
                break
            fi
        done

        # Method 2: Fallback - search for kernel file directly on known partition locations
        if [ -z "$isopart" ]; then
            # Most Proxmox USBs after dd have layout: gpt1=EFI, gpt2/gpt3=ISO data
            for part in (hd0,gpt3) (hd0,gpt2) (hd0,gpt1); do
                if [ -f "$part/boot/linux26" ]; then
                    set isopart="$part"
                    break
                fi
            done
        fi

        # Method 3: Last resort - try to find by ISO9660 volume ID pattern
        if [ -z "$isopart" ]; then
            search --no-floppy --file /boot/linux26 --set=isopart
        fi

        # Check if we found ISO partition
        if [ -z "$isopart" ]; then
            echo "======================================"
            echo "ERROR: Cannot find Proxmox ISO data!"
            echo "======================================"
            echo ""
            echo "Tried:"
            echo "  - Searching by volume labels (pve-9, pve-8, etc.)"
            echo "  - Checking partitions (hd0,gpt1/2/3)"
            echo "  - Searching for /boot/linux26 file"
            echo ""
            echo "Press any key to open manual installer menu..."
            read
            configfile /EFI/BOOT/grub-install.cfg
        else
            # Found ISO partition - delegate to original grub-install.cfg
            # which was created by proxmox-auto-install-assistant
            # This preserves all auto-installer configuration including answer.toml path
            # Video parameters are added by add_graphics_params() to grub-install.cfg
            echo "Found Proxmox ISO on: $isopart"
            echo ""
            echo "Loading auto-installer from original configuration..."
            echo "(includes video params for external display)"
            configfile /EFI/BOOT/grub-install.cfg
        fi
    }

    menuentry 'Install Proxmox VE (Manual - use if auto fails)' {
        configfile /EFI/BOOT/grub-install.cfg
    }
fi
GRUB_EOF

                    # Replace UUID placeholder
                    sed -i "s/USB_UUID_PLACEHOLDER/$install_uuid/" "$mount_point/EFI/BOOT/grub.cfg"

                    print_success "UUID wrapper created in grub.cfg"
                    print_info "Original installer menu saved as grub-install.cfg"

                    sync
                    embedded=1
                    umount "$mount_point" >/dev/null 2>&1 || true
                    break
                else
                    umount "$mount_point" >/dev/null 2>&1 || true
                fi
            fi
        fi
    done < <(lsblk -ln -o NAME "$usb_device" | tail -n +2)

    rmdir "$mount_point" >/dev/null 2>&1 || true

    if [[ $embedded -eq 1 ]]; then
        print_success "UUID wrapper embedded successfully"
        print_info "After installation, USB will automatically boot installed system"
    else
        print_warning "Could not embed UUID wrapper (EFI partition not found or read-only)"
    fi

    return 0
}

# --- Main ---
# --- validate created USB (comprehensive post-creation check) ---
validate_created_usb() {
    local usb_device="$1"
    if [[ -z "$usb_device" || ! -b "$usb_device" ]]; then
        print_error "validate_created_usb requires valid USB device"
        return 10
    fi

    print_info ""
    print_info "========================================="
    print_info "VALIDATING CREATED USB"
    print_info "========================================="

    local validation_failed=0
    local mount_point
    mount_point=$(mktemp -d -t usb-validate.XXXX)

    # Wait for device to be ready (handles race conditions)
    wait_for_device_ready "$usb_device"

    # Check 1: Partition table
    print_info "Checking partition table..."
    local efi_part="" hfs_part=""
    while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        local part="/dev/${p##*/}"
        [[ ! -b "$part" ]] && continue

        local fstype
        fstype=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

        if [[ "$fstype" == "vfat" ]]; then
            efi_part="$part"
            print_info "  ✓ EFI partition found: $part (vfat)"
        elif [[ "$fstype" == "hfsplus" ]]; then
            hfs_part="$part"
            print_info "  ✓ HFS+ partition found: $part (installer data)"
        fi
    done < <(lsblk -ln -o NAME "$usb_device" | tail -n +2)

    if [[ -z "$efi_part" ]]; then
        print_error "  ✗ EFI partition (vfat) NOT FOUND!"
        validation_failed=1
    fi

    if [[ -z "$hfs_part" ]]; then
        print_warning "  ⚠ HFS+ partition NOT FOUND (may be ISO9660 instead)"
    fi

    # Check 2: EFI partition contents
    if [[ -n "$efi_part" ]]; then
        print_info "Checking EFI partition contents..."
        if mount -o ro "$efi_part" "$mount_point" 2>/dev/null; then
            # Check bootloader
            if [[ -f "$mount_point/EFI/BOOT/grubx64.efi" ]]; then
                print_info "  ✓ UEFI bootloader: EFI/BOOT/grubx64.efi"
            else
                print_error "  ✗ MISSING: EFI/BOOT/grubx64.efi"
                validation_failed=1
            fi

            # Check grub.cfg
            if [[ -f "$mount_point/EFI/BOOT/grub.cfg" ]]; then
                print_info "  ✓ GRUB config: EFI/BOOT/grub.cfg"

                # Validate grub.cfg content based on mode
                if [[ "${SKIP_UUID_PROTECTION:-0}" == "1" ]]; then
                    # Should NOT contain UUID wrapper
                    if grep -q "usb_uuid=" "$mount_point/EFI/BOOT/grub.cfg" 2>/dev/null; then
                        print_error "  ✗ grub.cfg contains UUID wrapper (SKIP_UUID_PROTECTION=1 mode)"
                        print_error "    Expected: direct installer menu"
                        print_error "    Found: UUID protection wrapper"
                        validation_failed=1
                    else
                        print_info "  ✓ grub.cfg: direct installer menu (no UUID check)"
                    fi
                else
                    # Should contain UUID wrapper
                    if grep -q "usb_uuid=" "$mount_point/EFI/BOOT/grub.cfg" 2>/dev/null; then
                        print_info "  ✓ grub.cfg: UUID protection wrapper active"

                        # Check for backup installer menu
                        if [[ -f "$mount_point/EFI/BOOT/grub-install.cfg" ]]; then
                            print_info "  ✓ Backup installer menu: grub-install.cfg"
                        else
                            print_warning "  ⚠ grub-install.cfg NOT FOUND (UUID wrapper may fail)"
                        fi
                    else
                        print_warning "  ⚠ grub.cfg does not contain UUID wrapper"
                        print_warning "    This may be direct installer menu (check manually)"
                    fi
                fi

                # Show first 10 lines of grub.cfg for debugging
                print_info "  First 10 lines of grub.cfg:"
                head -10 "$mount_point/EFI/BOOT/grub.cfg" | sed 's/^/    /' >&2
            else
                print_error "  ✗ MISSING: EFI/BOOT/grub.cfg"
                validation_failed=1
            fi

            umount "$mount_point" 2>/dev/null || true
        else
            print_error "  ✗ Cannot mount EFI partition"
            validation_failed=1
        fi
    fi

    # Check 3: HFS+ partition (installer data)
    if [[ -n "$hfs_part" ]]; then
        print_info "Checking HFS+ partition (installer data)..."
        if mount -o ro "$hfs_part" "$mount_point" 2>/dev/null; then
            if [[ -d "$mount_point/boot" ]]; then
                print_info "  ✓ Installer data: boot/ directory found"
            else
                print_warning "  ⚠ boot/ directory NOT FOUND in HFS+ partition"
            fi

            if [[ -f "$mount_point/boot/grub/grub.cfg" ]]; then
                print_info "  ✓ Installer GRUB menu: boot/grub/grub.cfg"
            else
                print_warning "  ⚠ boot/grub/grub.cfg NOT FOUND"
            fi

            # Check for answer.toml (CRITICAL for auto-installation)
            print_info "  Checking for answer.toml (auto-installer configuration)..."
            local answer_found=0
            # Try common locations where proxmox-auto-install-assistant embeds answer.toml
            for location in "answer.toml" "proxmox/answer.toml" ".proxmox-auto-installer/answer.toml"; do
                if [[ -f "$mount_point/$location" ]]; then
                    print_info "    ✓ answer.toml found at: $location"

                    # Verify it's not empty
                    if [[ -s "$mount_point/$location" ]]; then
                        local file_size
                        file_size=$(stat -c%s "$mount_point/$location" 2>/dev/null || echo "0")
                        print_info "    ✓ File size: $file_size bytes"

                        # Check for key configuration items
                        if grep -q "root_password" "$mount_point/$location" 2>/dev/null; then
                            print_info "    ✓ Contains root_password configuration"
                        else
                            print_warning "    ⚠ root_password NOT FOUND in answer.toml"
                        fi

                        if grep -q "\\[disk-setup\\]" "$mount_point/$location" 2>/dev/null; then
                            print_info "    ✓ Contains disk-setup configuration"
                        else
                            print_warning "    ⚠ disk-setup section NOT FOUND in answer.toml"
                        fi

                        answer_found=1
                    else
                        print_error "    ✗ answer.toml is EMPTY at $location!"
                        validation_failed=1
                    fi
                    break
                fi
            done

            if [[ $answer_found -eq 0 ]]; then
                print_error "  ✗ answer.toml NOT FOUND in ISO!"
                print_error "    Auto-installation will fail - system will use defaults"
                print_error "    Locations checked:"
                print_error "      - answer.toml"
                print_error "      - proxmox/answer.toml"
                print_error "      - .proxmox-auto-installer/answer.toml"
                validation_failed=1
            fi

            umount "$mount_point" 2>/dev/null || true
        else
            print_warning "  ⚠ Cannot mount HFS+ partition (may be read-only ISO9660)"
        fi
    fi

    rmdir "$mount_point" 2>/dev/null || true

    print_info "========================================="
    if [[ $validation_failed -eq 0 ]]; then
        print_info "✓ VALIDATION PASSED: USB is ready for boot"
    else
        print_error "✗ VALIDATION FAILED: USB may not boot correctly"
        print_error "  Check errors above and recreate USB if needed"
    fi
    print_info "========================================="
    print_info ""

    return $validation_failed
}

main() {
    check_root || return 1
    check_requirements || return 2

    local iso_src="${1:-}"
    local answer_toml="${2:-}"
    local target_dev="${3:-}"

    if [[ -z "$iso_src" || -z "$answer_toml" || -z "$target_dev" ]]; then
        print_error "Usage: $SCRIPT_NAME <proxmox-iso> <answer.toml> <target-disk>"
        print_error "Example: sudo $SCRIPT_NAME proxmox-ve_9.0-1.iso answer.toml /dev/sdb"
        return 1
    fi

    # Validate ISO file (security checks) and normalize path
    local iso_canonical
    iso_canonical=$(validate_iso_file "$iso_src") || return 15
    iso_src="$iso_canonical"  # Use canonical path from now on

    validate_usb_device "$target_dev" || return 3

    # Check USB device has enough space for ISO
    if [[ -f "$iso_src" ]]; then
        local iso_size_mb
        iso_size_mb=$(du -m "$iso_src" | cut -f1)
        local usb_size_mb
        usb_size_mb=$(lsblk -bdn -o SIZE "$target_dev" 2>/dev/null | awk '{print int($1/1024/1024)}')

        if [[ -n "$usb_size_mb" && $usb_size_mb -gt 0 ]]; then
            print_info "USB device size: ${usb_size_mb} MB"
            print_info "ISO size: ${iso_size_mb} MB"

            if [[ $usb_size_mb -lt $iso_size_mb ]]; then
                print_error "USB device is too small for this ISO"
                print_error "  USB: ${usb_size_mb} MB, ISO: ${iso_size_mb} MB"
                return 14
            fi
            print_info "✓ USB device has sufficient space"
        fi
    fi

    # Generate answer.toml from topology.yaml if available
    # This will overwrite existing answer.toml with topology data
    if ! generate_answer_from_topology "$answer_toml"; then
        # Generation failed - check if answer.toml exists and is valid
        if [[ ! -f "$answer_toml" ]]; then
            print_error "No answer.toml found and topology generation failed"
            print_error "Please provide a valid answer.toml file"
            return 6
        fi
        print_warning "Topology generation failed, using existing answer.toml"
        print_warning "This may contain outdated configuration"
    fi

    validate_answer_file "$answer_toml" || return 6

    # Ask for root password (unless AUTO_CONFIRM is set)
    if [[ "${AUTO_CONFIRM:-0}" != "1" ]] && [[ -t 0 ]]; then
        print_info ""
        print_info "=========================================="
        print_info "Proxmox Root Password Configuration"
        print_info "=========================================="
        print_info ""
        print_info "You can set a custom root password for Proxmox installation."
        print_info "Default password from topology.yaml will be used if not changed."
        print_info ""
        read -r -p "Do you want to set a custom password? (y/N): " change_password

        if [[ "$change_password" =~ ^[Yy]$ ]]; then
            while true; do
                read -r -s -p "Enter new root password: " new_password
                echo ""

                if [[ ${#new_password} -lt 5 ]]; then
                    print_error "Password too short (minimum 5 characters)"
                    continue
                fi

                read -r -s -p "Confirm password: " new_password_confirm
                echo ""

                if [[ "$new_password" != "$new_password_confirm" ]]; then
                    print_error "Passwords don't match. Try again."
                    continue
                fi

                # Update password in answer.toml
                update_password_in_answer "$answer_toml" "$new_password"
                ROOT_PASSWORD="$new_password"

                # Clear password from variable (security)
                unset new_password new_password_confirm

                print_success "Password updated successfully"
                break
            done
        else
            ROOT_PASSWORD="proxmox"
            print_info "Using default password: proxmox"
        fi
        print_info ""
    else
        # Optionally set root password from env var ROOT_PASSWORD_HASH (precomputed)
        if [[ -n "${ROOT_PASSWORD_HASH:-}" ]]; then
            set_root_password "$answer_toml" "$ROOT_PASSWORD_HASH" || return 7
        fi
        ROOT_PASSWORD="${ROOT_PASSWORD:-proxmox}"
        print_info "Using default password from answer.toml: proxmox"
    fi

    # Generate installation UUID BEFORE prepare_iso (so it's accessible globally)
    local timezone timestamp
    timezone=$(date +%Z)
    timestamp=$(date +%Y_%m_%d_%H_%M)
    INSTALL_UUID="${timezone}_${timestamp}"  # GLOBAL variable
    print_info "Generated installation UUID: $INSTALL_UUID"

    # Prepare ISO (prints path to stdout, logs to stderr)
    # UUID is passed via INSTALL_UUID global variable
    local created_iso=""
    created_iso=$(prepare_iso "$iso_src" "$answer_toml")
    if [[ -z "${created_iso:-}" || ! -f "$created_iso" ]]; then
        print_error "Failed to create prepared ISO"
        return 9
    fi
    print_info "Prepared ISO located at: $created_iso"

    # Confirm before writing: interactive or AUTO_CONFIRM env
    if [[ -t 0 ]]; then
        print_warning "About to write ISO to $target_dev - THIS WILL DESTROY ALL DATA ON THE DEVICE"
        read -r -p "Type YES to confirm: " confirm
        if [[ "$confirm" != "YES" ]]; then
            print_warning "Aborted by user"
            return 0
        fi
    else
        # non-interactive: require AUTO_CONFIRM=1 environment variable
        if [[ "${AUTO_CONFIRM:-0}" != "1" ]]; then
            print_error "Non-interactive session: set AUTO_CONFIRM=1 to allow writing without prompt"
            return 12
        fi
        print_info "Auto-confirm enabled (non-interactive)"
    fi

    # Unmount any mounted partitions on target device
    print_info "Unmounting potential mounted partitions on $target_dev ..."
    while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        local dev="/dev/${p##*/}"
        if findmnt "$dev" >/dev/null 2>&1; then
            print_info "Unmounting $dev"
            umount "$dev" || true
        fi
    done < <(lsblk -ln -o NAME "$target_dev" | tail -n +2)

    # Final write
    print_info "Writing prepared ISO to $target_dev (this may take several minutes)..."
    if ! dd if="$created_iso" of="$target_dev" bs=4M status=progress conv=fsync oflag=direct; then
        print_error "dd failed writing ISO to $target_dev"
        return 11
    fi
    sync

    # Wait for device to be ready after dd (critical for partition detection)
    print_info "Synchronizing device changes..."
    wait_for_device_ready "$target_dev" 15  # Longer timeout after dd

    print_info "Successfully wrote $created_iso to $target_dev"

    # NOTE: auto-installer-mode.toml is already embedded by proxmox-auto-install-assistant
    # No need to add it manually - ISO partition is read-only after dd
    print_info "auto-installer-mode.toml and answer.toml embedded in ISO by proxmox-auto-install-assistant"

    # Embed UUID wrapper in GRUB (PREVENTS REINSTALLATION LOOP)
    # Note: This is best-effort. USB will work without UUID protection, just won't prevent reinstall loops
    embed_uuid_wrapper "$target_dev" || print_warning "UUID wrapper embedding failed - reinstall protection disabled"

    # Add graphics parameters (best-effort for external display)
    add_graphics_params "$target_dev" || print_warning "Graphics parameters not added - external display may not work"

    # Validate created USB (CRITICAL: if this fails, USB may not boot)
    if ! validate_created_usb "$target_dev"; then
        print_error ""
        print_error "========================================="
        print_error "USB VALIDATION FAILED"
        print_error "========================================="
        print_error "USB may not be bootable. Check errors above."
        print_error "Consider recreating the USB or checking:"
        print_error "  - USB device health"
        print_error "  - Filesystem support (vfat, hfsplus)"
        print_error "  - USB write permissions"
        return 16
    fi

    print_info ""
    print_info "========================================="
    print_info "✓ USB READY FOR AUTOMATED INSTALLATION"
    print_info "========================================="
    print_info ""

    # Different instructions for SKIP_UUID_PROTECTION mode
    if [[ "${SKIP_UUID_PROTECTION:-0}" == "1" ]]; then
        print_warning "UUID PROTECTION DISABLED MODE"
        print_warning "=================================================="
        print_warning "⚠️  THIS USB WILL REINSTALL PROXMOX ON EVERY BOOT!"
        print_warning "⚠️  REMOVE USB IMMEDIATELY AFTER INSTALLATION!"
        print_warning ""
        print_info "Boot instructions:"
        print_info "1. Connect external monitor (Mini DisplayPort)"
        print_info "2. Insert USB into Dell XPS L701X"
        print_info "3. Boot and press F12 for boot menu"
        print_info "4. Select: UEFI: USB... (NOT 'USB Storage Device')"
        print_info "5. GRUB menu: 'Install Proxmox VE (AUTO-INSTALL)'"
        print_info "6. Installation starts automatically after 5 seconds"
        print_info "7. System powers off after installation (~10-15 min)"
        print_info "8. ⚠️  REMOVE USB BEFORE POWERING ON!"
        print_info "9. Power on system - Proxmox boots from SSD"
        print_info ""
        print_warning "If you forget to remove USB: Proxmox will be reinstalled!"
    else
        print_info "Boot instructions (FIRST BOOT):"
        print_info "1. Connect external monitor (Mini DisplayPort)"
        print_info "2. Insert USB into Dell XPS L701X"
        print_info "3. Boot and press F12 for boot menu"
        print_info "4. Select: UEFI: USB... (NOT 'USB Storage Device')"
        print_info "5. GRUB menu: 'Install Proxmox VE (AUTO-INSTALL)'"
        print_info "6. Installation starts automatically after 5 seconds"
        print_info "7. System reboots after installation (~10-15 min)"
        print_info ""
        print_info "Boot instructions (AFTER INSTALLATION):"
        print_info "1. Leave USB inserted and reboot"
        print_info "2. GRUB menu changes to: 'Boot Proxmox VE (Already Installed)'"
        print_info "3. Boots installed system automatically after 5 seconds"
        print_info "4. No reinstallation - UUID protection active!"
        print_info ""
        print_info "To force reinstall: Select 'Reinstall Proxmox (ERASES ALL DATA!)'"
    fi

    print_info ""
    print_info "After first successful boot:"
    print_info "  Username: root"
    print_info "  Password: ${ROOT_PASSWORD:-proxmox}"
    print_info "  SSH: ssh root@<proxmox-ip>"
    print_info "  Web: https://<proxmox-ip>:8006"
    print_info ""
    print_info "Note: Temporary ISO will be automatically cleaned up on exit."

    return 0
}

# Run main
main "$@"
