#!/usr/bin/env bash
#
# create-uefi-autoinstall-proxmox-usb.sh — Production-ready UEFI USB creator
#
# Creates auto-installing Proxmox VE USB for UEFI systems with optional reinstall prevention.
#
# Features:
#   - Auto-generates answer.toml from topology.yaml (Infrastructure-as-Data)
#   - Automatically modifies ISO to enable auto-installer by default (fixes GRUB HFS+ issue)
#   - UEFI boot support (recommended for modern systems)
#   - UUID-based reinstall prevention (optional)
#   - Interactive password configuration
#
# How it works:
#   1. Modifies Proxmox ISO /boot/grub/grub.cfg to remove auto-installer-mode.toml check
#      (Fixes issue where GRUB loads config from HFS+ partition without the file)
#   2. Embeds answer.toml and first-boot script using proxmox-auto-install-assistant
#   3. Creates bootable USB with UUID-based reinstall prevention wrapper
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
            [[ -d "$dir" ]] && rm -rf "$dir" 2>/dev/null || true
        done
    done

    # Unmount any temporary mount points (best-effort)
    for dir in /tmp/usbmnt.* /tmp/usb-uuid.*; do
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
    local cmds=(lsblk mktemp dd awk sed findmnt find grep mount umount cp mv date sync blkid partprobe blockdev proxmox-auto-install-assistant xorriso isoinfo)

    for cmd in "${cmds[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -ne 0 ]]; then
        print_error "Missing required commands: ${missing[*]}"
        print_error "Install proxmox-auto-install-assistant: wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg && echo 'deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription' > /etc/apt/sources.list.d/pve-install-repo.list && apt update && apt install -y proxmox-auto-install-assistant"
        print_error "Install xorriso and isoinfo: apt update && apt install -y xorriso genisoimage"
        return 2
    fi

    return 0
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
    ROOT_DEV=$(findmnt -n -o SOURCE / | sed 's/[0-9]*$//')
    echo "Root device: $ROOT_DEV"

    if [ -n "$ROOT_DEV" ]; then
        for part in "${ROOT_DEV}"[0-9]* "${ROOT_DEV}p"[0-9]*; do
            [ ! -b "$part" ] && continue
            PART_TYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null)
            if [ "$PART_TYPE" = "vfat" ]; then
                mkdir -p /efi
                if mount "$part" /efi 2>&1; then
                    EFI_MOUNT="/efi"
                    echo "✓ Mounted $part to /efi"
                    break
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

# --- modify ISO to enable auto-installer by default ---
# Modifies Proxmox ISO /boot/grub/grub.cfg to remove the check for auto-installer-mode.toml
# This fixes the issue where GRUB loads config from HFS+ partition which doesn't have the file
# Returns: path to modified ISO (or original if already modified) via stdout
modify_iso_for_autoinstall() {
    local iso_src="$1"

    if [[ -z "$iso_src" ]]; then
        print_error "modify_iso_for_autoinstall requires <iso-path>"
        return 1
    fi

    if [[ ! -f "$iso_src" ]]; then
        print_error "ISO file not found: $iso_src"
        return 1
    fi

    print_info "Checking if ISO needs modification for auto-installer..."

    # Create temporary mount point to check ISO
    local check_mount=$(mktemp -d -t iso-check.XXXX)

    # Mount ISO to check if already modified
    if mount -o loop,ro "$iso_src" "$check_mount" 2>/dev/null; then
        local already_modified=0

        if [[ -f "$check_mount/boot/grub/grub.cfg" ]]; then
            if grep -q "AUTO-INSTALLER ENABLED BY DEFAULT" "$check_mount/boot/grub/grub.cfg" 2>/dev/null; then
                already_modified=1
                print_success "ISO already modified (auto-installer enabled by default)"
            fi
        fi

        umount "$check_mount" 2>/dev/null || true
        rmdir "$check_mount" 2>/dev/null || true

        if [[ $already_modified -eq 1 ]]; then
            # Return original ISO path
            printf '%s\n' "$iso_src"
            return 0
        fi
    else
        rmdir "$check_mount" 2>/dev/null || true
    fi

    # ISO needs modification
    print_info "ISO needs modification - enabling auto-installer by default..."
    print_info "This fixes GRUB loading config from HFS+ partition without auto-installer files"

    # Create temp directory for ISO modification
    local mod_tmpdir=$(mktemp -d -t iso-mod.XXXX)
    local iso_extract="$mod_tmpdir/iso"
    mkdir -p "$iso_extract"

    # Extract ISO
    print_info "Extracting ISO (this may take a few minutes)..."
    xorriso -osirrox on -indev "$iso_src" -extract / "$iso_extract" 2>&1 | grep -v "^xorriso" || true

    local grub_cfg="$iso_extract/boot/grub/grub.cfg"

    if [[ ! -f "$grub_cfg" ]]; then
        print_error "GRUB config not found in ISO: $grub_cfg"
        rm -rf "$mod_tmpdir"
        return 1
    fi

    # Backup original
    cp "$grub_cfg" "$grub_cfg.original"

    # Modify GRUB config: remove 'if [ -f auto-installer-mode.toml ]' check
    # and make auto-installer menu always available
    print_info "Modifying GRUB config to enable auto-installer by default..."

    cat > "$grub_cfg.new" << 'GRUB_MOD_EOF'
insmod gzio
insmod iso9660

if [ x$feature_default_font_path = xy ] ; then
   font=unicode
else
   font=$prefix/unicode.pf2
fi

set gfxmode=1024x768,640x480
set gfxpayload=1024x768

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
insmod usbserial_common
insmod usbserial_ftdi
insmod usbserial_pl2303
insmod usbserial_usbdebug
if serial --unit=0 --speed=115200; then
    terminal_input --append serial
    terminal_output --append serial
    set show_serial_entry=y
fi

# AUTO-INSTALLER ENABLED BY DEFAULT (modified by create-uefi-autoinstall-proxmox-usb.sh)
# Original check removed: if [ -f auto-installer-mode.toml ]; then
# This fixes the issue where GRUB loads config from HFS+ partition which doesn't have auto-installer files
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
GRUB_MOD_EOF

    # Replace GRUB config
    mv "$grub_cfg.new" "$grub_cfg"
    print_success "GRUB config modified"

    # Get ISO info
    local iso_label
    iso_label=$(isoinfo -d -i "$iso_src" 2>/dev/null | grep "Volume id:" | cut -d: -f2 | xargs || echo "PVE")

    # Extract MBR from original ISO
    dd if="$iso_src" bs=1 count=432 of="$mod_tmpdir/isohdpfx.bin" 2>/dev/null

    # Generate output filename
    local output_iso="${iso_src%.iso}-autoinstall.iso"

    # Rebuild ISO with xorriso
    print_info "Rebuilding ISO with modified GRUB config..."

    # Redirect all xorriso output to stderr to not interfere with function return value
    xorriso -as mkisofs \
        -o "$output_iso" \
        -V "$iso_label" \
        -J -joliet-long -r \
        --grub2-mbr "$mod_tmpdir/isohdpfx.bin" \
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
        "$iso_extract" >&2 2>&1

    # Cleanup temp directory
    rm -rf "$mod_tmpdir"

    if [[ ! -f "$output_iso" ]]; then
        print_error "Failed to create modified ISO: $output_iso"
        return 1
    fi

    local input_size=$(du -h "$iso_src" | cut -f1)
    local output_size=$(du -h "$output_iso" | cut -f1)

    print_success "ISO modified successfully: $output_iso"
    print_info "Original ISO: $input_size → Modified ISO: $output_size"
    print_info "Changes: Auto-installer enabled by default (no file check required)"

    # Return modified ISO path
    printf '%s\n' "$output_iso"
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

    # Use /var/tmp instead of /tmp to avoid tmpfs size limits
    # /var/tmp is usually on disk, not in RAM
    # If /var/tmp doesn't have enough space, use current directory
    if [[ -d /var/tmp ]] && [[ $(df --output=avail /var/tmp | tail -1) -gt 2000000 ]]; then
        TMPDIR=$(mktemp -d /var/tmp/pmxiso.XXXX)
    else
        print_warning "/var/tmp has insufficient space, using current directory"
        TMPDIR=$(mktemp -d ./pmxiso.XXXX)
    fi
    print_info "Using tempdir $TMPDIR"

    # Use INSTALL_UUID from global scope (set by main() before calling prepare_iso)
    local install_uuid="$INSTALL_UUID"

    # Save UUID to temp file for later use (if needed)
    echo "$install_uuid" > "$TMPDIR/install-uuid"

    # Create first-boot script with UUID
    local first_boot_script="$TMPDIR/first-boot.sh"
    create_first_boot_script "$install_uuid" "$first_boot_script"

    # Generate output ISO filename
    local output_iso="$TMPDIR/$(basename "${iso_src%.iso}")-auto-from-iso.iso"

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

# --- add auto-installer-mode.toml to USB (critical for auto-installer to work) ---
add_auto_installer_mode() {
    local usb_device="$1"
    if [[ -z "$usb_device" || ! -b "$usb_device" ]]; then
        print_error "add_auto_installer_mode requires valid USB device"
        return 10
    fi

    print_info "Adding auto-installer-mode.toml to USB..."

    # Force re-read partition table
    partprobe "$usb_device" 2>/dev/null || true
    blockdev --rereadpt "$usb_device" 2>/dev/null || true
    sleep 1

    local mount_point
    mount_point=$(mktemp -d -t usbmnt.XXXX)
    local added=0

    # Find the main ISO partition (usually HFS+ or ISO9660)
    while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        local part="/dev/${p##*/}"
        [[ ! -b "$part" ]] && continue

        local fstype
        fstype=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

        # Try to mount HFS+ or iso9660 partitions
        if [[ "$fstype" == "hfsplus" || "$fstype" == "iso9660" ]]; then
            if mount -o rw "$part" "$mount_point" 2>/dev/null; then
                # Check if this is the right partition (has boot/ directory)
                if [[ -d "$mount_point/boot" ]]; then
                    print_info "Found ISO root partition: $part"

                    # Check if auto-installer-mode.toml already exists
                    if [[ -f "$mount_point/auto-installer-mode.toml" ]]; then
                        print_info "auto-installer-mode.toml already exists"
                        added=1
                    else
                        # Create auto-installer-mode.toml
                        cat > "$mount_point/auto-installer-mode.toml" << 'EOF'
mode = "iso"
EOF
                        sync
                        if [[ -f "$mount_point/auto-installer-mode.toml" ]]; then
                            print_info "Created auto-installer-mode.toml"
                            added=1
                        else
                            print_warning "Failed to create auto-installer-mode.toml (read-only filesystem?)"
                        fi
                    fi

                    umount "$mount_point" >/dev/null 2>&1 || true
                    break
                else
                    umount "$mount_point" >/dev/null 2>&1 || true
                fi
            fi
        fi
    done < <(lsblk -ln -o NAME "$usb_device" | tail -n +2)

    rmdir "$mount_point" >/dev/null 2>&1 || true

    if [[ $added -eq 1 ]]; then
        print_info "auto-installer-mode.toml is present on USB"
    else
        print_warning "Could not add auto-installer-mode.toml (filesystem may be read-only)"
        print_warning "WORKAROUND: Boot to GRUB, press 'e' on any entry, add 'proxmox-start-auto-installer' to linux line"
    fi

    return 0
}

# --- add graphics params for Dell XPS L701X to USB (after write) ---
add_graphics_params() {
    local usb_device="$1"
    if [[ -z "$usb_device" || ! -b "$usb_device" ]]; then
        print_error "add_graphics_params requires valid USB device"
        return 10
    fi

    print_info "Adding graphics parameters for Dell XPS L701X (external display)..."

    # Force re-read partition table
    partprobe "$usb_device" 2>/dev/null || true
    blockdev --rereadpt "$usb_device" 2>/dev/null || true
    sleep 1

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
                # Modify BOTH grub.cfg (UUID wrapper) AND grub-install.cfg (original installer menu)
                # This ensures video params work regardless of which path is taken
                local grub_files=()
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

    # Force re-read partition table
    partprobe "$usb_device" 2>/dev/null || true
    blockdev --rereadpt "$usb_device" 2>/dev/null || true
    sleep 1

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

                        # CRITICAL FIX: Remove 'set prefix' from grub-install.cfg
                        # The original Proxmox grub.cfg contains 'set prefix=($root)/boot/grub'
                        # which breaks auto-installer-mode.toml file detection
                        if grep -q "^set prefix=" "$mount_point/EFI/BOOT/grub-install.cfg" 2>/dev/null; then
                            sed -i '/^set prefix=/d' "$mount_point/EFI/BOOT/grub-install.cfg"
                            print_success "Removed 'set prefix' from grub-install.cfg (fixes auto-installer detection)"
                        fi
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

# Search for proxmox-installed marker on system disk (hd1)
# The first-boot script creates this file only on the system disk

# hd1,gpt2 (most common EFI location)
if [ $found_system -eq 0 ]; then
    if [ -f (hd1,gpt2)/proxmox-installed ]; then
        cat --set=disk_uuid (hd1,gpt2)/proxmox-installed
        echo "✓ Found installation marker on (hd1,gpt2)"
        echo "  Disk UUID: $disk_uuid"
        echo "  USB  UUID: $usb_uuid"
        if [ "$disk_uuid" = "$usb_uuid" ]; then
            set found_system=1
            set efi_part="gpt2"
            set disk="hd1"
            echo "  Result: UUIDs MATCH!"
        else
            echo "  Result: UUIDs DON'T MATCH (different USB)"
        fi
    fi
fi

# hd1,gpt1
if [ $found_system -eq 0 ]; then
    if [ -f (hd1,gpt1)/proxmox-installed ]; then
        cat --set=disk_uuid (hd1,gpt1)/proxmox-installed
        if [ "$disk_uuid" = "$usb_uuid" ]; then
            set found_system=1
            set efi_part="gpt1"
            set disk="hd1"
        fi
    fi
fi

# hd0,gpt2 (fallback if USB is hd1)
if [ $found_system -eq 0 ]; then
    if [ -f (hd0,gpt2)/proxmox-installed ]; then
        cat --set=disk_uuid (hd0,gpt2)/proxmox-installed
        if [ "$disk_uuid" = "$usb_uuid" ]; then
            set found_system=1
            set efi_part="gpt2"
            set disk="hd0"
        fi
    fi
fi

# hd0,gpt1
if [ $found_system -eq 0 ]; then
    if [ -f (hd0,gpt1)/proxmox-installed ]; then
        cat --set=disk_uuid (hd0,gpt1)/proxmox-installed
        if [ "$disk_uuid" = "$usb_uuid" ]; then
            set found_system=1
            set efi_part="gpt1"
            set disk="hd0"
        fi
    fi
fi

echo ""
echo "══════════════════════════════════════"
echo "UUID Check Result:"
echo "══════════════════════════════════════"
if [ $found_system -eq 1 ]; then
    # UUID matches - system already installed with this USB
    echo "✓ MATCH: System was installed with THIS USB"
    echo "  Location: ($disk,$efi_part)"
    echo ""
    echo "DECISION: Boot installed Proxmox system"
    echo "          (To reinstall, select 'Reinstall' from menu)"
    echo ""
    echo "Press any key to show menu (or wait 10 seconds)..."
    sleep 10

    set timeout=30
    set default=0

    menuentry 'Boot Proxmox VE (Already Installed)' {
        if [ "$disk" = "hd1" ]; then
            if [ "$efi_part" = "gpt2" ]; then
                chainloader (hd1,gpt2)/EFI/proxmox/grubx64.efi
            elif [ "$efi_part" = "gpt1" ]; then
                chainloader (hd1,gpt1)/EFI/proxmox/grubx64.efi
            fi
        else
            if [ "$efi_part" = "gpt2" ]; then
                chainloader (hd0,gpt2)/EFI/proxmox/grubx64.efi
            elif [ "$efi_part" = "gpt1" ]; then
                chainloader (hd0,gpt1)/EFI/proxmox/grubx64.efi
            fi
        fi
    }

    menuentry 'Reinstall Proxmox (ERASES ALL DATA!)' {
        configfile /EFI/BOOT/grub-install.cfg
    }
else
    # UUID doesn't match or no marker found - proceed with installation
    echo "✗ NO MATCH: No installation found for this USB"
    echo "  (Either first install or different USB was used)"
    echo ""
    echo "DECISION: Proceed with AUTO-INSTALLATION"
    echo "          (To install manually, select 'Manual' from menu)"
    echo ""
    echo "Press any key to show menu (or wait 10 seconds)..."
    echo "Auto-installer will start automatically..."
    sleep 10

    set timeout=30
    set default=0

    menuentry 'Install Proxmox VE (AUTO-INSTALL)' {
        # Dynamic ISO partition search (replaces hardcoded UUID)
        # This makes USB work with any Proxmox ISO version
        set isopart=""

        # Method 1: Search by common Proxmox ISO labels (version-agnostic)
        for label in pve-9 pve-8 pve-10 pve-11 pve-7 pve-12; do
            search --no-floppy --label --set=isopart "$label"
            if [ -n "$isopart" ]; then
                echo "Found ISO by label: $label"
                break
            fi
        done

        # Method 2: Search by filesystem UUID (try known Proxmox patterns)
        if [ -z "$isopart" ]; then
            search --no-floppy --fs-uuid --set=isopart 2025-08-05-10-48-40-00 2>/dev/null || true
        fi

        # Method 3: Search for kernel file directly
        if [ -z "$isopart" ]; then
            search --no-floppy --file /boot/linux26 --set=isopart
        fi

        # Boot with found partition
        if [ -n "$isopart" ]; then
            set root=$isopart
            echo "Loading Proxmox kernel with auto-installer..."
            echo "ISO partition: $isopart"
            linux ($root)/boot/linux26 ro ramdisk_size=16777216 rw splash=silent video=vesafb:ywrap,mtrr vga=791 nomodeset proxmox-start-auto-installer
            echo "Loading initrd..."
            initrd ($root)/boot/initrd.img
        else
            echo "ERROR: Cannot find Proxmox ISO partition!"
            echo "Falling back to manual installer menu..."
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

    # Force re-read partition table
    partprobe "$usb_device" 2>/dev/null || true
    sleep 1

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

    # Expand tilde in paths (important for ~ to work correctly in all contexts)
    iso_src="${iso_src/#\~/$HOME}"
    answer_toml="${answer_toml/#\~/$HOME}"

    validate_usb_device "$target_dev" || return 3

    # Generate answer.toml from topology.yaml if available
    # This will overwrite existing answer.toml with topology data
    generate_answer_from_topology "$answer_toml" || true

    validate_answer_file "$answer_toml" || return 6

    # Ask for root password (unless AUTO_CONFIRM is set)
    if [[ "${AUTO_CONFIRM:-0}" != "1" ]] && [[ -t 0 ]]; then
        print_info ""
        print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_info "Root Password Configuration"
        print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_info ""
        print_info "answer.toml was generated from topology/security.yaml"
        print_info "Default password from topology: 'proxmox' (CHANGE IN PRODUCTION!)"
        print_info ""
        print_info "Options:"
        print_info "  [N] Keep password from topology/security.yaml (default)"
        print_info "  [Y] Set custom password for this USB only"
        print_info ""
        read -p "Do you want to set a custom password? (y/N): " change_password

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
            print_success "Using password from topology/security.yaml"
            print_info "Password: 'proxmox' (from topology default)"
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

    # Modify ISO if needed (enables auto-installer by default)
    # This fixes GRUB loading config from HFS+ partition without auto-installer files
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_info "Step 1: Modify ISO for auto-installer (if needed)"
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    local modified_iso=""
    modified_iso=$(modify_iso_for_autoinstall "$iso_src")
    local modify_exit=$?

    if [[ $modify_exit -ne 0 ]]; then
        print_error "Failed to modify ISO (exit code: $modify_exit)"
        return 9
    fi

    if [[ -z "${modified_iso:-}" ]]; then
        print_error "Failed to modify ISO (empty output)"
        return 9
    fi

    # Extract just the last line (the file path) - xorriso may output multiple lines
    modified_iso=$(echo "$modified_iso" | tail -1)

    if [[ ! -f "$modified_iso" ]]; then
        print_error "Failed to modify ISO (file not found: $modified_iso)"
        return 9
    fi

    print_info "Using ISO: $modified_iso"

    # Prepare ISO (prints path to stdout, logs to stderr)
    # UUID is passed via INSTALL_UUID global variable
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_info "Step 2: Embed answer.toml and first-boot script"
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    local created_iso=""
    created_iso=$(prepare_iso "$modified_iso" "$answer_toml")
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
    sleep 1
    print_info "Successfully wrote $created_iso to $target_dev"

    # NOTE: auto-installer-mode.toml is already embedded by proxmox-auto-install-assistant
    # No need to add it manually - ISO partition is read-only after dd
    print_info "auto-installer-mode.toml and answer.toml embedded in ISO by proxmox-auto-install-assistant"

    # Embed UUID wrapper in GRUB (PREVENTS REINSTALLATION LOOP)
    embed_uuid_wrapper "$target_dev" || print_warning "embed_uuid_wrapper encountered an issue"

    # Add graphics parameters (best-effort)
    add_graphics_params "$target_dev" || print_warning "add_graphics_params encountered an issue"

    # Validate created USB (comprehensive check)
    validate_created_usb "$target_dev" || print_warning "Validation encountered issues (see above)"

    print_info ""
    print_info "========================================="
    print_info "USB READY FOR AUTOMATED INSTALLATION"
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
