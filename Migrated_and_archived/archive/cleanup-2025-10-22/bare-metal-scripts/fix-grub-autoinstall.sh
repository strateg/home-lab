#!/bin/bash
#
# Fix GRUB wrapper to activate auto-installer directly
# This bypasses the need for auto-installer-mode.toml
#

set -e

echo "=========================================="
echo "Fixing GRUB for Auto-Install Activation"
echo "=========================================="
echo ""

MOUNT_POINT="/mnt/usb-fix-$$"
sudo mkdir -p "$MOUNT_POINT"

echo "Mounting EFI partition..."
sudo mount /dev/sdc2 "$MOUNT_POINT"

echo "Backing up current grub.cfg..."
sudo cp "$MOUNT_POINT/EFI/BOOT/grub.cfg" "$MOUNT_POINT/EFI/BOOT/grub.cfg.backup-autofix"

echo "Creating fixed GRUB wrapper with direct auto-installer activation..."

sudo tee "$MOUNT_POINT/EFI/BOOT/grub.cfg" > /dev/null << 'GRUB_EOF'
# Reinstall Prevention Wrapper
# Checks for existing installation before loading installer menu

insmod part_gpt
insmod fat
insmod chain

# UUID embedded at USB creation time
set usb_uuid="EEST_2025_10_18_20_09"
set found_system=0
set disk_uuid=""
set efi_part=""
set disk=""

# Search for proxmox-installed marker on system disk (hd1)
if [ $found_system -eq 0 ]; then
    if [ -f (hd1,gpt2)/proxmox-installed ]; then
        cat --set=disk_uuid (hd1,gpt2)/proxmox-installed
        if [ "$disk_uuid" = "$usb_uuid" ]; then
            set found_system=1
            set efi_part="gpt2"
            set disk="hd1"
        fi
    fi
fi

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

if [ $found_system -eq 1 ]; then
    # UUID matches - system already installed with this USB
    set timeout=5
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
        search --no-floppy --fs-uuid --set=root 2025-08-05-10-48-40-00
        set prefix=($root)/boot/grub
        configfile $prefix/grub.cfg
    }
else
    # No installation found - proceed with AUTO-INSTALL
    set timeout=5
    set default=0

    menuentry 'Install Proxmox VE (AUTO-INSTALL)' {
        search --no-floppy --fs-uuid --set=root 2025-08-05-10-48-40-00
        set prefix=($root)/boot/grub
        echo 'Loading kernel with auto-installer...'
        linux $prefix/../linux26 ro ramdisk_size=16777216 rw splash=silent video=vesafb:ywrap,mtrr vga=791 nomodeset proxmox-start-auto-installer
        echo 'Loading initrd...'
        initrd $prefix/../initrd.img
    }

    menuentry 'Boot existing system from disk (if any)' {
        if [ "$disk" = "hd1" ]; then
            if [ "$efi_part" = "gpt2" ]; then
                chainloader (hd1,gpt2)/EFI/proxmox/grubx64.efi
            elif [ "$efi_part" = "gpt1" ]; then
                chainloader (hd1,gpt1)/EFI/proxmox/grubx64.efi
            else
                echo "No Proxmox installation found on hd1"
                read
            fi
        fi
    }
fi
GRUB_EOF

sudo sync

echo ""
echo "Verifying changes..."
echo "First 50 lines of new grub.cfg:"
sudo head -50 "$MOUNT_POINT/EFI/BOOT/grub.cfg"

sudo umount "$MOUNT_POINT"
sudo rmdir "$MOUNT_POINT"

echo ""
echo "=========================================="
echo "✓ GRUB Fixed!"
echo "=========================================="
echo ""
echo "Changes:"
echo "  - Auto-installer activation added directly to GRUB"
echo "  - No need for auto-installer-mode.toml"
echo "  - Kernel command includes: proxmox-start-auto-installer"
echo ""
echo "Boot USB and select 'Install Proxmox VE (AUTO-INSTALL)'"
echo "Auto-installation will start immediately!"
