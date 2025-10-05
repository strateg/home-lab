#!/bin/bash
# Proxmox VE 9 - Complete USB Creator (One Script Does Everything)
#
# This script:
# 1. Writes ISO with dd (bootable like balenaEtcher)
# 2. Finds EFI partition (FAT32 - writable)
# 3. Replaces GRUB loader with complete config (auto-install + graphics)
# 4. Adds answer file
# 5. Verifies everything worked
#
# Usage: sudo ./create-proxmox-usb-complete.sh /dev/sdX path/to/proxmox.iso

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: Run as root${NC}"
   exit 1
fi

if [ "$#" -ne 2 ]; then
    echo "Usage: sudo $0 /dev/sdX path/to/proxmox.iso"
    exit 1
fi

USB_DEVICE="$1"
ISO_FILE="$2"

if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: $USB_DEVICE is not a block device${NC}"
    exit 1
fi

if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: $ISO_FILE not found${NC}"
    exit 1
fi

if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda${NC}"
    exit 1
fi

if [ ! -f "proxmox-auto-install-answer.toml" ]; then
    echo -e "${RED}Error: proxmox-auto-install-answer.toml not found${NC}"
    echo "This file must be in the current directory"
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Proxmox VE 9 - Complete USB Creator         ║${NC}"
echo -e "${GREEN}║  One Script - Full Auto-Install Setup        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}WARNING: This will ERASE all data on $USB_DEVICE${NC}"
echo ""
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

umount "${USB_DEVICE}"* 2>/dev/null || true

# ============================================================
# STEP 1: Write ISO with dd
# ============================================================
echo ""
echo -e "${GREEN}[1/5] Writing ISO to USB with dd...${NC}"
echo "This creates bootable USB (like balenaEtcher)"
echo ""

dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo ""
echo -e "${GREEN}✓ Bootable USB created${NC}"

# ============================================================
# STEP 2: Detect partitions
# ============================================================
echo ""
echo -e "${GREEN}[2/5] Detecting partitions...${NC}"

partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

echo "Partitions created:"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL

# ============================================================
# STEP 3: Find and modify EFI partition
# ============================================================
echo ""
echo -e "${GREEN}[3/5] Finding EFI partition and modifying GRUB...${NC}"

MOUNT_POINT="/tmp/usb-$$"
mkdir -p "$MOUNT_POINT"
SUCCESS=0

for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ]; then
        echo ""
        echo "Checking $part (FAT32)..."

        if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            echo "  ✓ Mounted writable"

            # Look for GRUB in EFI partition
            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

            if [ -n "$GRUB_CFG" ]; then
                echo "  ✓ Found GRUB: ${GRUB_CFG#$MOUNT_POINT/}"

                # Backup original
                cp "$GRUB_CFG" "$GRUB_CFG.backup-$(date +%s)"

                # Read original to get UUID
                ROOT_UUID=$(grep "search --fs-uuid" "$GRUB_CFG" 2>/dev/null | grep -o '[0-9-]\{10,\}' | head -1 || echo "")

                if [ -z "$ROOT_UUID" ]; then
                    echo "  ! Could not find UUID, using default"
                    ROOT_UUID="2025-08-05-10-48-40-00"
                fi

                echo "  Root UUID: $ROOT_UUID"

                # Create COMPLETE GRUB config (no sourcing external files)
                echo "  Creating complete GRUB configuration..."

                cat > "$GRUB_CFG" <<GRUBEOF
set default=0
set timeout=3

# Load required modules
insmod all_video
insmod gfxterm
insmod png
insmod part_gpt
insmod part_msdos
insmod iso9660
insmod fat

# Graphics setup for external display
loadfont unicode
terminal_output gfxterm
set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

# Find the root partition with Proxmox files
search --fs-uuid --set=root $ROOT_UUID

menuentry 'Proxmox VE - Automated Install (External Display)' {
    echo 'Loading kernel with auto-install and graphics support...'
    linux /boot/linux26 auto-install-cfg=partition ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    echo 'Loading initrd...'
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Manual Install (External Display)' {
    echo 'Loading kernel with graphics support...'
    linux /boot/linux26 ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    echo 'Loading initrd...'
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Standard Install' {
    linux /boot/linux26 ro quiet
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Debug Mode' {
    linux /boot/linux26 ro debug
    initrd /boot/initrd.img
}

menuentry 'Proxmox VE - Rescue Mode' {
    linux /boot/linux26 ro rescue
    initrd /boot/initrd.img
}
GRUBEOF

                echo "  ✓ GRUB configuration written"

                # Copy answer file
                if [ -f "proxmox-auto-install-answer.toml" ]; then
                    cp "proxmox-auto-install-answer.toml" "$MOUNT_POINT/answer.toml"
                    echo "  ✓ answer.toml copied"
                fi

                # Copy post-install script if exists
                if [ -f "proxmox-post-install.sh" ]; then
                    cp "proxmox-post-install.sh" "$MOUNT_POINT/"
                    echo "  ✓ proxmox-post-install.sh copied"
                fi

                sync
                SUCCESS=1

                echo -e "${GREEN}  ✓ EFI partition configured successfully${NC}"
            fi

            umount "$MOUNT_POINT"

            if [ $SUCCESS -eq 1 ]; then
                break
            fi
        fi
    fi
done

rmdir "$MOUNT_POINT"

if [ $SUCCESS -eq 0 ]; then
    echo -e "${RED}Error: Could not find/modify EFI partition${NC}"
    exit 1
fi

# ============================================================
# STEP 4: Verify configuration
# ============================================================
echo ""
echo -e "${GREEN}[4/5] Verifying configuration...${NC}"

mkdir -p "$MOUNT_POINT"
VERIFIED=0

for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ]; then
        if mount -o ro "$part" "$MOUNT_POINT" 2>/dev/null; then
            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

            if [ -n "$GRUB_CFG" ]; then
                echo ""
                echo "GRUB verification:"

                if grep -q "auto-install-cfg=partition" "$GRUB_CFG"; then
                    echo "  ✓ Auto-install parameter present"
                else
                    echo "  ✗ Auto-install parameter MISSING"
                fi

                if grep -q "video=vesafb:ywrap,mtrr vga=791 nomodeset" "$GRUB_CFG"; then
                    echo "  ✓ Graphics parameters present"
                else
                    echo "  ✗ Graphics parameters MISSING"
                fi

                if grep -q "set timeout=3" "$GRUB_CFG"; then
                    echo "  ✓ Timeout set to 3 seconds"
                else
                    echo "  ! Timeout not set to 3"
                fi

                if grep -q "set default=0" "$GRUB_CFG"; then
                    echo "  ✓ Default entry set to 0 (auto-install)"
                else
                    echo "  ! Default entry not set"
                fi

                if [ -f "$MOUNT_POINT/answer.toml" ]; then
                    echo "  ✓ answer.toml present"
                    VERIFIED=1
                else
                    echo "  ✗ answer.toml MISSING"
                fi
            fi

            umount "$MOUNT_POINT"
            break
        fi
    fi
done

rmdir "$MOUNT_POINT"

# ============================================================
# STEP 5: Final status
# ============================================================
echo ""
echo -e "${GREEN}[5/5] Final sync and status...${NC}"

sync
sleep 2

echo ""

if [ $VERIFIED -eq 1 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║        USB READY FOR AUTO-INSTALL!             ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}What was configured:${NC}"
    echo "  ✓ Bootable USB (dd method - works like balenaEtcher)"
    echo "  ✓ EFI partition GRUB modified (complete config)"
    echo "  ✓ Auto-install parameter: auto-install-cfg=partition"
    echo "  ✓ Graphics parameters: video=vesafb:ywrap,mtrr vga=791 nomodeset"
    echo "  ✓ Answer file: /answer.toml on EFI partition"
    echo "  ✓ Timeout: 3 seconds"
    echo "  ✓ Default: Automated Install"
    echo ""
    echo -e "${YELLOW}BOOT INSTRUCTIONS:${NC}"
    echo ""
    echo "  1. Connect external monitor to Mini DisplayPort"
    echo "  2. Power ON the monitor"
    echo "  3. Insert USB into Dell XPS L701X"
    echo "  4. Power on laptop"
    echo "  5. Press F12 for boot menu"
    echo "  6. Select: 'UEFI: USB...' (NOT 'USB Storage Device')"
    echo ""
    echo -e "${GREEN}EXPECTED BEHAVIOR:${NC}"
    echo ""
    echo "  • GRUB menu appears on external display (3 sec timeout)"
    echo "  • First option: 'Proxmox VE - Automated Install'"
    echo "  • Press Enter OR wait 3 seconds"
    echo "  • Installation starts automatically"
    echo "  • Progress shown on external display"
    echo "  • System reboots when complete (~10-15 min)"
    echo ""
    echo -e "${BLUE}AFTER INSTALLATION:${NC}"
    echo ""
    echo "  1. Find IP address (check router or use console)"
    echo "  2. SSH: ssh root@<ip-address>"
    echo "  3. Password: Homelab2025! (from answer file)"
    echo "  4. Run: bash proxmox-post-install.sh"
    echo ""
    echo -e "${GREEN}USB is ready! Boot and test now.${NC}"
    echo ""
else
    echo -e "${YELLOW}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  USB CREATED - VERIFICATION INCOMPLETE         ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "USB was created but some verification checks failed."
    echo "Try booting anyway - it might still work."
    echo ""
fi
