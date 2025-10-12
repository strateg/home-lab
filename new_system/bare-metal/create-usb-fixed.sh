#!/bin/bash
#
# proxmox-auto-install.sh
#
# Безопасный скрипт подготовки USB с автоматической установкой Proxmox.
# Исправления:
# - IFS синтаксис исправлен
# - Добавлена проверка root прав
# - Упрощена add_graphics_params (работает с записанным USB, не с ISO)
# - Улучшена обработка ошибок
# - Убран бесполезный fallback в prepare_iso
#
# Usage:
#   sudo ./proxmox-auto-install.sh <proxmox-original.iso> <answer.toml> <target-disk>
# Example:
#   sudo ./proxmox-auto-install.sh proxmox-ve_*.iso answer.toml /dev/sdb
#

set -euo pipefail
IFS=$'\n\t'  # ✅ ИСПРАВЛЕНО: правильный синтаксис

SCRIPT_NAME=$(basename "$0")
TMPDIR=""

cleanup() {
    local rc=$?
    if [[ -n "${TMPDIR:-}" && -d "${TMPDIR:-}" ]]; then
        rm -rf "${TMPDIR}"
    fi
    if [[ $rc -ne 0 ]]; then
        echo >&2 "${SCRIPT_NAME}: ERROR: Exited with status $rc"
    fi
    exit $rc
}
trap cleanup EXIT INT TERM

# --- logging helpers ---
print_info()    { printf '%s\n' "INFO: $*"; }
print_error()   { printf '%s\n' "ERROR: $*" >&2; }
print_warning() { printf '%s\n' "WARNING: $*"; }

# --- root check ---
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        return 1
    fi
    return 0
}

# --- requirements check ---
check_requirements() {
    local missing=()
    local cmds=(lsblk mktemp dd awk sed findmnt find grep mount umount cp mv date sync)

    for cmd in "${cmds[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -ne 0 ]]; then
        print_error "Missing required commands: ${missing[*]}"
        return 2
    fi

    # Check for proxmox-auto-install-assistant (critical)
    if ! command -v proxmox-auto-install-assistant >/dev/null 2>&1; then
        print_error "proxmox-auto-install-assistant not found (REQUIRED)"
        print_info "Install with: apt update && apt install proxmox-auto-install-assistant"
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

    # Check lsblk for type 'disk'
    if ! lsblk -dn -o NAME,TYPE | awk -v n="$devname" '$1==n && $2=="disk"{found=1} END{exit !found}'; then
        print_error "Target '$target' is not a whole-disk device (must be /dev/sdX or /dev/nvme0n1)"
        return 4
    fi

    # Protect root disk
    local root_src root_disk pkname
    root_src=$(findmnt -n -o SOURCE / || true)
    if [[ -n "$root_src" ]]; then
        pkname=$(lsblk -no PKNAME "$root_src" 2>/dev/null || true)
        if [[ -n "$pkname" ]]; then
            root_disk="$pkname"
        else
            root_disk=$(basename "${root_src}" | sed -E 's/p?[0-9]+$//')
        fi
        if [[ "$root_disk" == "$devname" ]]; then
            print_error "Refusing to operate on system root disk ($target)"
            return 5
        fi
    fi

    print_info "Validated target: $target (device: $devname)"
    return 0
}

# --- validate answer file ---
validate_answer_file() {
    local ans_file="$1"
    if [[ -z "$ans_file" || ! -f "$ans_file" ]]; then
        print_error "answer.toml not found: ${ans_file:-<empty>}"
        return 6
    fi

    # Validate with official tool
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

    # Replace root_password line or add if missing
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
    END{ if (replaced==0) print "root_password = \"" hv "\"" }
    ' "$ans_file" > "$tmp"

    cp -a "$ans_file" "${ans_file}.bak" 2>/dev/null || true
    mv -f "$tmp" "$ans_file"
    print_info "Updated root_password in $ans_file (backup at ${ans_file}.bak)"
    return 0
}

# --- prepare ISO with embedded answer.toml ---
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

    # Use proxmox-auto-install-assistant (REQUIRED for auto-install)
    print_info "Embedding answer.toml using proxmox-auto-install-assistant..."

    if ! proxmox-auto-install-assistant prepare-iso "$iso_src" \
        --fetch-from iso \
        --answer-file "$answer" \
        --outdir "$TMPDIR"; then
        print_error "proxmox-auto-install-assistant failed"
        return 9
    fi

    # Find created ISO (pattern: *-auto-from-iso.iso)
    local created_iso
    created_iso=$(find "$TMPDIR" -maxdepth 1 -type f -name '*-auto-from-iso.iso' -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n1 | awk '{print $2}')

    if [[ -z "$created_iso" || ! -f "$created_iso" ]]; then
        print_error "Assistant did not produce ISO (expected pattern: *-auto-from-iso.iso)"
        return 9
    fi

    print_info "Created ISO: $created_iso"
    echo "$created_iso"
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
    sleep 2

    local mount_point
    mount_point=$(mktemp -d -t usbmnt.XXXX)
    local modified=0

    # Find EFI/FAT32 partition on USB
    for part in "${usb_device}"[0-9]* "${usb_device}p"[0-9]*; do
        [[ ! -b "$part" ]] && continue

        local fstype
        fstype=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

        if [[ "$fstype" == "vfat" ]]; then
            if mount -o rw "$part" "$mount_point" 2>/dev/null; then
                # Find grub.cfg
                local grub_cfg
                grub_cfg=$(find "$mount_point" -name "grub.cfg" -type f 2>/dev/null | head -1)

                if [[ -n "$grub_cfg" ]]; then
                    print_info "Found GRUB config: ${grub_cfg#$mount_point/}"

                    # Backup
                    cp "$grub_cfg" "${grub_cfg}.backup-$(date +%s)"

                    # Check if already modified
                    if grep -q "video=vesafb" "$grub_cfg"; then
                        print_info "Graphics parameters already present"
                    else
                        print_info "Adding graphics parameters to kernel boot lines..."

                        # Add to all linux boot lines (Proxmox uses /boot/linux26 path)
                        sed -i '/linux.*\/boot\/linux26/ s|$| video=vesafb:ywrap,mtrr vga=791 nomodeset|' "$grub_cfg"

                        print_info "Graphics parameters added"
                        modified=1
                    fi

                    sync
                fi

                umount "$mount_point"
                break
            fi
        fi
    done

    rmdir "$mount_point"

    if [[ $modified -eq 1 ]]; then
        print_info "GRUB configuration updated for external display support"
    else
        print_warning "Could not modify GRUB (external display may not work)"
    fi

    return 0
}

# --- main flow ---
main() {
    check_root
    check_requirements

    local iso_src="${1:-}"
    local answer_toml="${2:-}"
    local target_dev="${3:-}"

    if [[ -z "$iso_src" || -z "$answer_toml" || -z "$target_dev" ]]; then
        print_error "Usage: $SCRIPT_NAME <proxmox-iso> <answer.toml> <target-disk>"
        print_error "Example: sudo $SCRIPT_NAME proxmox-ve_9.0-1.iso answer.toml /dev/sdb"
        return 1
    fi

    # Validate inputs
    validate_usb_device "$target_dev"
    validate_answer_file "$answer_toml"

    # Optionally set root password from env var ROOT_PASSWORD_HASH
    if [[ -n "${ROOT_PASSWORD_HASH:-}" ]]; then
        set_root_password "$answer_toml" "$ROOT_PASSWORD_HASH"
    fi

    # Create prepared ISO
    local created_iso
    created_iso=$(prepare_iso "$iso_src" "$answer_toml")
    if [[ -z "${created_iso:-}" || ! -f "$created_iso" ]]; then
        print_error "Failed to create prepared ISO"
        return 9
    fi

    # Confirm before writing
    print_warning "About to write ISO to $target_dev - THIS WILL DESTROY ALL DATA ON THE DEVICE"
    read -r -p "Type YES to confirm: " confirm
    if [[ "$confirm" != "YES" ]]; then
        print_warning "Aborted by user"
        return 0
    fi

    # Write ISO to USB
    print_info "Writing prepared ISO to $target_dev (this may take 5-10 minutes)..."
    if ! dd if="$created_iso" of="$target_dev" bs=4M status=progress conv=fsync oflag=direct; then
        print_error "dd failed writing ISO to $target_dev"
        return 11
    fi
    sync
    sleep 2
    print_info "Successfully wrote $created_iso to $target_dev"

    # Add graphics parameters for Dell XPS L701X
    add_graphics_params "$target_dev"

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
    print_info ""

    return 0
}

# Execute
main "$@"
