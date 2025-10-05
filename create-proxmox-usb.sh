#!/bin/bash
# Proxmox VE 9 - Fully Automated Installation USB Creator
#
# Creates USB with COMPLETELY AUTOMATIC installation:
# 1. Boots automatically (5 second timeout)
# 2. Starts auto-installer without pressing 'a'
# 3. Works with external display (Dell XPS L701X)
#
# Based on official Proxmox automated installation:
# - Boot parameter: proxmox-start-auto-installer
# - Answer file: answer.toml (TOML format)
# - Partition label: PROXMOX-AIS
#
# Usage: sudo ./create-proxmox-usb.sh /dev/sdX path/to/proxmox.iso

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

# Validate inputs
if [ ! -b "$USB_DEVICE" ]; then
    echo -e "${RED}Error: $USB_DEVICE is not a block device${NC}"
    exit 1
fi

if [ ! -f "$ISO_FILE" ]; then
    echo -e "${RED}Error: $ISO_FILE not found${NC}"
    exit 1
fi

if [[ "$USB_DEVICE" == "/dev/sda" ]]; then
    echo -e "${RED}Error: Cannot use /dev/sda (safety check)${NC}"
    exit 1
fi

if [ ! -f "answer.toml" ]; then
    echo -e "${RED}Error: answer.toml not found in current directory${NC}"
    echo "Create answer.toml file with Proxmox installation configuration"
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Proxmox VE 9 - Fully Automated USB         ║${NC}"
echo -e "${GREEN}║  Auto-starts in 5 seconds (no 'a' needed)   ║${NC}"
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

# Unmount any mounted partitions
umount "${USB_DEVICE}"* 2>/dev/null || true

# ============================================================
# STEP 1: Write ISO to USB with dd
# ============================================================
echo ""
echo -e "${GREEN}[1/5] Writing ISO to USB with dd...${NC}"
echo "This creates bootable USB (preserves hybrid boot structure)"
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

echo "Partitions:"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL

# ============================================================
# STEP 3: Set partition label and add answer.toml
# ============================================================
echo ""
echo -e "${GREEN}[3/5] Setting up answer file...${NC}"

MOUNT_POINT="/tmp/usb-$$"
mkdir -p "$MOUNT_POINT"
CONFIG_ADDED=0

# Find and mount the FAT32 EFI partition
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    [ ! -b "$part" ] && continue

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "vfat" ]; then
        echo ""
        echo "Mounting $part (FAT32)..."

        if mount -o rw "$part" "$MOUNT_POINT" 2>/dev/null; then
            echo "  ✓ Mounted writable"

            # Set partition label to PROXMOX-AIS (required for auto-installer)
            CURRENT_LABEL=$(blkid -s LABEL -o value "$part" 2>/dev/null || echo "")
            if [ "$CURRENT_LABEL" != "PROXMOX-AIS" ]; then
                fatlabel "$part" "PROXMOX-AIS"
                echo "  ✓ Partition label set to: PROXMOX-AIS"
            else
                echo "  ✓ Partition label already: PROXMOX-AIS"
            fi

            # Copy answer.toml to root of partition
            cp answer.toml "$MOUNT_POINT/answer.toml"
            echo "  ✓ answer.toml copied to partition root"

            # Copy post-install script if exists
            if [ -f "proxmox-post-install.sh" ]; then
                cp "proxmox-post-install.sh" "$MOUNT_POINT/"
                echo "  ✓ proxmox-post-install.sh copied"
            fi

            sync
            CONFIG_ADDED=1

            # Don't unmount yet - we need to modify GRUB in next step
            break
        fi
    fi
done

if [ $CONFIG_ADDED -eq 0 ]; then
    rmdir "$MOUNT_POINT"
    echo -e "${RED}Error: Could not find FAT32 partition${NC}"
    exit 1
fi

# ============================================================
# STEP 4: Create GRUB config with auto-start
# ============================================================
echo ""
echo -e "${GREEN}[4/5] Creating GRUB config with AUTO-START...${NC}"

GRUB_MODIFIED=0

# Find GRUB config on the mounted partition
GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

if [ -n "$GRUB_CFG" ]; then
    echo "Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}"

    # Backup original
    cp "$GRUB_CFG" "$GRUB_CFG.backup-$(date +%s)"

    # Extract UUID from original config
    UUID=$(grep "search.*fs-uuid" "$GRUB_CFG" 2>/dev/null | grep -o '[0-9-]\{10,\}' | head -1 || echo "")
    if [ -z "$UUID" ]; then
        UUID="2025-08-05-10-48-40-00"
        echo "  ! Using default UUID: $UUID"
    else
        echo "  ✓ Found UUID: $UUID"
    fi

    # Create new GRUB config with AUTOMATED ENTRY FIRST
    cat > "$GRUB_CFG" <<'GRUBEOF'
# Proxmox VE - Fully Automated Installation
# Auto-starts in 5 seconds (no manual interaction needed)

set default=0
set timeout=5

# Graphics setup for external display
insmod all_video
insmod gfxterm
insmod png
loadfont unicode
terminal_output gfxterm
set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

# Find root partition
GRUBEOF

    echo "search --fs-uuid --set=root $UUID" >> "$GRUB_CFG"

    cat >> "$GRUB_CFG" <<'GRUBEOF'

# AUTOMATED INSTALLATION (starts automatically after 5 seconds)
menuentry 'Proxmox VE - AUTOMATED INSTALL (External Display)' {
    echo 'Starting fully automated installation...'
    echo 'No manual interaction required!'
    linux /boot/linux26 proxmox-start-auto-installer ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

# Manual install with external display
menuentry 'Proxmox VE - Manual Install (External Display)' {
    echo 'Starting manual installation...'
    linux /boot/linux26 ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}

# Standard install
menuentry 'Proxmox VE - Standard Install' {
    linux /boot/linux26 ro quiet
    initrd /boot/initrd.img
}

# Debug mode
menuentry 'Proxmox VE - Debug Mode' {
    linux /boot/linux26 ro debug video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}
GRUBEOF

    echo "  ✓ GRUB config created with AUTOMATED entry"
    echo "  ✓ Boot parameter: proxmox-start-auto-installer"
    echo "  ✓ Graphics parameters: video=vesafb:ywrap,mtrr vga=791 nomodeset"
    echo "  ✓ Timeout: 5 seconds (auto-start)"

    GRUB_MODIFIED=1
else
    echo "  ⚠ GRUB config not found on FAT32 partition"
fi

sync
umount "$MOUNT_POINT"
rmdir "$MOUNT_POINT"

# ============================================================
# STEP 5: Final verification
# ============================================================
echo ""
echo -e "${GREEN}[5/5] Final sync and verification...${NC}"

sync
sleep 2

echo ""

if [ $CONFIG_ADDED -eq 1 ] && [ $GRUB_MODIFIED -eq 1 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║  USB READY FOR FULLY AUTOMATED INSTALL!        ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}What was configured:${NC}"
    echo "  ✓ Bootable USB created with dd"
    echo "  ✓ Partition labeled: PROXMOX-AIS"
    echo "  ✓ answer.toml placed on partition"
    echo "  ✓ GRUB: proxmox-start-auto-installer parameter"
    echo "  ✓ GRUB: Graphics parameters for external display"
    echo "  ✓ GRUB: 5-second timeout (AUTO-START)"
    echo ""
    echo -e "${YELLOW}BOOT INSTRUCTIONS:${NC}"
    echo ""
    echo "  1. Connect external monitor to Mini DisplayPort"
    echo "  2. Power ON the external monitor"
    echo "  3. Insert USB into Dell XPS L701X"
    echo "  4. Power on laptop"
    echo "  5. Press F12 for boot menu"
    echo "  6. Select: 'UEFI: USB...' (NOT 'USB Storage Device')"
    echo ""
    echo -e "${GREEN}AUTOMATIC BEHAVIOR:${NC}"
    echo ""
    echo "  • GRUB menu appears on external display"
    echo "  • First option: 'Proxmox VE - AUTOMATED INSTALL'"
    echo "  • Countdown: 5 seconds"
    echo "  • Installation starts AUTOMATICALLY (no 'a' needed!)"
    echo "  • Reads answer.toml from PROXMOX-AIS partition"
    echo "  • Progress shown on external display"
    echo "  • System reboots when complete (~10-15 min)"
    echo ""
    echo -e "${BLUE}AFTER INSTALLATION:${NC}"
    echo ""
    echo "  1. Find IP address (check router DHCP leases)"
    echo "  2. SSH: ssh root@<ip-address>"
    echo "  3. Password: Homelab2025!"
    echo "  4. Web UI: https://<ip-address>:8006"
    echo ""
    echo -e "${GREEN}Installation is FULLY AUTOMATIC - just boot and wait!${NC}"
    echo ""
else
    echo -e "${RED}Error: Could not configure USB properly${NC}"
    exit 1
fi
