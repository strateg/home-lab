#!/bin/bash
# Proxmox VE 9 - Automated Installation USB Creator
#
# CORRECT METHOD for Proxmox 8+:
# 1. Write ISO with dd (bootable, preserves hybrid boot structure)
# 2. Add auto-installer.yaml to /proxmox/ folder on FAT32 partition
# 3. Modify GRUB to add graphics parameters for external display
# 4. Boot and press 'a' to start automated installation
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

if [ ! -f "auto-installer.yaml" ]; then
    echo -e "${RED}Error: auto-installer.yaml not found in current directory${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Proxmox VE 9 - Automated USB Creator        ║${NC}"
echo -e "${GREEN}║  Built-in auto-installer (Proxmox 8+)        ║${NC}"
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
echo -e "${GREEN}[1/4] Writing ISO to USB with dd...${NC}"
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
echo -e "${GREEN}[2/4] Detecting partitions...${NC}"

partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

echo "Partitions:"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL

# ============================================================
# STEP 3: Add auto-installer.yaml to /proxmox/
# ============================================================
echo ""
echo -e "${GREEN}[3/4] Adding auto-installer.yaml...${NC}"

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

            # Create /proxmox directory if it doesn't exist
            mkdir -p "$MOUNT_POINT/proxmox"

            # Copy auto-installer.yaml
            cp auto-installer.yaml "$MOUNT_POINT/proxmox/auto-installer.yaml"
            echo "  ✓ auto-installer.yaml copied to /proxmox/"

            # Copy post-install script if exists
            if [ -f "proxmox-post-install.sh" ]; then
                cp "proxmox-post-install.sh" "$MOUNT_POINT/proxmox/"
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
# STEP 4: Modify GRUB for external display
# ============================================================
echo ""
echo -e "${GREEN}[4/4] Adding graphics parameters to GRUB...${NC}"

GRUB_MODIFIED=0

# Find GRUB config on the mounted partition
GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" -type f 2>/dev/null | head -1)

if [ -n "$GRUB_CFG" ]; then
    echo "Found GRUB config: ${GRUB_CFG#$MOUNT_POINT/}"

    # Backup original
    cp "$GRUB_CFG" "$GRUB_CFG.backup-$(date +%s)"

    # Add graphics parameters to all linux boot lines
    # These parameters enable external display on Dell XPS L701X:
    # video=vesafb:ywrap,mtrr vga=791 nomodeset

    if grep -q "video=vesafb" "$GRUB_CFG"; then
        echo "  ℹ Graphics parameters already present"
    else
        echo "  Adding graphics parameters to boot entries..."

        # Add parameters to all 'linux' lines that load linux26 kernel
        sed -i '/linux.*\/boot\/linux26/ s|$| video=vesafb:ywrap,mtrr vga=791 nomodeset|' "$GRUB_CFG"

        echo "  ✓ Graphics parameters added to all boot entries"
    fi

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

if [ $CONFIG_ADDED -eq 1 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║        USB READY FOR AUTO-INSTALL!             ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}What was configured:${NC}"
    echo "  ✓ Bootable USB created with dd"
    echo "  ✓ auto-installer.yaml added to /proxmox/"
    if [ $GRUB_MODIFIED -eq 1 ]; then
        echo "  ✓ Graphics parameters added to GRUB"
    fi
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
    echo -e "${GREEN}AT GRUB MENU:${NC}"
    echo ""
    echo "  7. Press 'a' key to start AUTOMATED INSTALLATION"
    echo "     (or wait for default boot and press 'a' at installer menu)"
    echo ""
    echo -e "${BLUE}AUTOMATED INSTALL PROCESS:${NC}"
    echo ""
    echo "  • Reads /proxmox/auto-installer.yaml from USB"
    echo "  • Partitions /dev/sda (250GB SSD)"
    echo "  • Installs Proxmox VE 9"
    echo "  • Configures network (DHCP)"
    echo "  • Sets hostname: proxmox.home.lan"
    echo "  • Sets root password: Homelab2025!"
    echo "  • Total time: ~10-15 minutes"
    echo "  • Reboots automatically when done"
    echo ""
    echo -e "${BLUE}AFTER INSTALLATION:${NC}"
    echo ""
    echo "  1. Find IP address (check router DHCP leases)"
    echo "  2. SSH: ssh root@<ip-address>"
    echo "  3. Password: Homelab2025!"
    echo "  4. Web UI: https://<ip-address>:8006"
    echo ""
    if [ -f "proxmox-post-install.sh" ]; then
        echo "  5. Run post-install script:"
        echo "     bash /root/proxmox-post-install.sh"
        echo ""
    fi
    echo -e "${GREEN}USB is ready! Boot and press 'a' to start auto-install.${NC}"
    echo ""
else
    echo -e "${RED}Error: Could not configure USB${NC}"
    exit 1
fi
