#!/usr/bin/env bash
#
# proxmox-auto-install.sh — Production-ready version
#
# Полностью исправленная и улучшенная версия для автоматической установки Proxmox.
#
# Usage:
#   sudo ./proxmox-auto-install.sh <proxmox-original.iso> <answer.toml> <target-disk>
# Example:
#   sudo ./proxmox-auto-install.sh proxmox-ve_9.0-1.iso answer.toml /dev/sdb
#
# Environment variables:
#   ROOT_PASSWORD_HASH - precomputed password hash to embed in answer.toml
#   AUTO_CONFIRM=1     - skip interactive confirmation (for automation)
#
set -euo pipefail
IFS=$'\n\t'

SCRIPT_NAME=$(basename "$0")
TMPDIR=""

cleanup() {
    local rc=${1:-$?}

    # Remove temporary directory
    if [[ -n "${TMPDIR:-}" && -d "${TMPDIR:-}" ]]; then
        rm -rf "${TMPDIR}"
    fi

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

# --- prepare ISO with embedded answer.toml
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

    TMPDIR=$(mktemp -d -t pmxiso.XXXX)
    print_info "Using tempdir $TMPDIR"

    # Generate output ISO filename
    local output_iso="$TMPDIR/$(basename "${iso_src%.iso}")-auto-from-iso.iso"

    print_info "Embedding answer.toml using proxmox-auto-install-assistant..."
    print_info "Command: proxmox-auto-install-assistant prepare-iso --fetch-from iso --answer-file \"$answer\" --output \"$output_iso\" --tmp \"$TMPDIR\" \"$iso_src\""

    if ! proxmox-auto-install-assistant prepare-iso \
        --fetch-from iso \
        --answer-file "$answer" \
        --output "$output_iso" \
        --tmp "$TMPDIR" \
        "$iso_src" 2>&1 | tee /tmp/paa-output.log; then
        print_error "proxmox-auto-install-assistant failed. Output:"
        cat /tmp/paa-output.log >&2
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

        if [[ "$fstype" == "vfat" ]]; then
            if mount -o rw "$part" "$mount_point" 2>/dev/null; then
                local grub_cfg
                grub_cfg=$(find "$mount_point" -type f -name "grub.cfg" 2>/dev/null | head -1 || true)

                if [[ -n "$grub_cfg" && -f "$grub_cfg" ]]; then
                    print_info "Found GRUB config: ${grub_cfg#$mount_point/}"
                    cp -a "$grub_cfg" "${grub_cfg}.backup-$(date +%s)" || true

                    if grep -q "video=vesafb" "$grub_cfg" 2>/dev/null; then
                        print_info "Graphics parameters already present"
                    else
                        print_info "Adding graphics parameters to kernel boot lines..."
                        # Proxmox uses /boot/linux26 path for kernel
                        sed -i '/linux.*\/boot\/linux26/ s|$| video=vesafb:ywrap,mtrr vga=791 nomodeset|' "$grub_cfg" || true
                        print_info "Graphics parameters added"
                        modified=1
                    fi

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

# --- Main ---
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

    validate_usb_device "$target_dev" || return 3
    validate_answer_file "$answer_toml" || return 6

    # Optionally set root password from env var ROOT_PASSWORD_HASH (precomputed)
    if [[ -n "${ROOT_PASSWORD_HASH:-}" ]]; then
        set_root_password "$answer_toml" "$ROOT_PASSWORD_HASH" || return 7
    fi

    # Prepare ISO (prints path to stdout, logs to stderr)
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
    sleep 1
    print_info "Successfully wrote $created_iso to $target_dev"

    # Add graphics parameters (best-effort)
    add_graphics_params "$target_dev" || print_warning "add_graphics_params encountered an issue"

    print_info ""
    print_info "========================================="
    print_info "USB READY FOR AUTOMATED INSTALLATION"
    print_info "========================================="
    print_info ""
    print_info "Boot instructions:"
    print_info "1. Connect external monitor (Mini DisplayPort)"
    print_info "2. Insert USB into Dell XPS L701X"
    print_info "3. Boot and press F12 for boot menu"
    print_info "4. Select: UEFI: USB... (NOT 'USB Storage Device')"
    print_info "5. GRUB menu appears with 'Automated Installation' option"
    print_info "6. Installation starts automatically after 10 seconds"
    print_info ""
    print_info "After installation:"
    print_info "  SSH: ssh root@<proxmox-ip>"
    print_info "  Web: https://<proxmox-ip>:8006"

    return 0
}

# Run main
main "$@"
