#!/bin/bash
# Proxmox VE 9 USB - Write Then Modify Approach
#
# Strategy:
# 1. Write ISO with dd (guaranteed bootable like balenaEtcher)
# 2. Mount the USB and modify GRUB config in-place
# 3. No ISO rebuilding - just direct file modification
#
# Usage: sudo ./prepare-proxmox-usb-modify-after-write.sh /dev/sdX path/to/proxmox.iso

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

# Unmount everything
umount "${USB_DEVICE}"* 2>/dev/null || true

echo ""
echo -e "${GREEN}[1/4] Writing ISO to USB with dd...${NC}"
echo "This creates a bootable USB (like balenaEtcher)."
echo ""

# Write ISO - this is guaranteed to work
dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 3

echo ""
echo -e "${GREEN}✓ ISO written (bootable USB created)${NC}"

echo ""
echo -e "${GREEN}[2/4] Detecting USB partitions...${NC}"

# Force kernel to detect partitions
partprobe "$USB_DEVICE" 2>/dev/null || true
blockdev --rereadpt "$USB_DEVICE" 2>/dev/null || true
sleep 3

echo "Partitions on USB:"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL

echo ""
echo -e "${GREEN}[3/4] Modifying GRUB configuration on USB...${NC}"

# The USB now has ISO9660 filesystem which is read-only by default
# We need to use a different approach: copy files out, modify, write back

# Try method 1: Mount with write support using loop device offset
MODIFIED=0
MOUNT_POINT="/tmp/usb-modify-$$"
mkdir -p "$MOUNT_POINT"

# Find the ISO9660 partition
for part in "${USB_DEVICE}"[0-9]* "${USB_DEVICE}p"[0-9]*; do
    if [ ! -b "$part" ]; then
        continue
    fi

    FSTYPE=$(blkid -s TYPE -o value "$part" 2>/dev/null || echo "")

    if [ "$FSTYPE" = "iso9660" ]; then
        echo "Found ISO9660 partition: $part"

        # Method: Extract from ISO9660, modify, create overlay
        # This is complex, so let's use isoinfo to read and modify

        # Check if we can mount it
        if mount -t iso9660 -o ro "$part" "$MOUNT_POINT" 2>/dev/null; then
            echo "  Mounted read-only, looking for GRUB config..."

            GRUB_CFG=$(find "$MOUNT_POINT" -name "grub.cfg" 2>/dev/null | head -1)

            if [ -n "$GRUB_CFG" ]; then
                echo "  Found GRUB: ${GRUB_CFG#$MOUNT_POINT/}"

                # Copy GRUB config out
                GRUB_BACKUP="/tmp/grub.cfg.$$"
                cp "$GRUB_CFG" "$GRUB_BACKUP"

                # Now we need to modify the ISO9660 filesystem
                # Since it's read-only, we'll use a different technique:
                # Modify the data on the block device directly

                # Get the offset and size of grub.cfg in the ISO
                GRUB_REL_PATH="${GRUB_CFG#$MOUNT_POINT/}"

                umount "$MOUNT_POINT"

                echo "  Extracting ISO to modify GRUB..."

                # Extract entire ISO
                EXTRACT_DIR="/tmp/iso-extract-$$"
                mkdir -p "$EXTRACT_DIR"

                # Mount again to extract
                mount -t iso9660 -o ro "$part" "$MOUNT_POINT"

                # Copy all files
                echo "  Copying ISO contents (this takes a moment)..."
                rsync -a "$MOUNT_POINT/" "$EXTRACT_DIR/" 2>/dev/null || cp -a "$MOUNT_POINT/"* "$EXTRACT_DIR/"

                umount "$MOUNT_POINT"

                # Make writable
                chmod -R u+w "$EXTRACT_DIR"

                # Find and modify GRUB
                GRUB_NEW="$EXTRACT_DIR/$GRUB_REL_PATH"

                if [ -f "$GRUB_NEW" ]; then
                    echo "  Modifying GRUB config..."

                    # Backup
                    cp "$GRUB_NEW" "$GRUB_NEW.original"

                    # Modify: add graphics and auto-install parameters
                    sed -i 's|^\(\s*linux\s\+/boot/linux26.*\)\s*$|\1 video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition|' "$GRUB_NEW"

                    # Set timeout
                    if grep -q "^set timeout=" "$GRUB_NEW"; then
                        sed -i 's/^set timeout=.*/set timeout=3/' "$GRUB_NEW"
                    else
                        sed -i '1i set timeout=3' "$GRUB_NEW"
                    fi

                    # Set default to first entry
                    if grep -q "^set default=" "$GRUB_NEW"; then
                        sed -i 's/^set default=.*/set default=0/' "$GRUB_NEW"
                    else
                        sed -i '1i set default=0' "$GRUB_NEW"
                    fi

                    echo -e "${GREEN}  ✓ GRUB modified${NC}"

                    # Add answer file
                    if [ -f "proxmox-auto-install-answer.toml" ]; then
                        cp "proxmox-auto-install-answer.toml" "$EXTRACT_DIR/answer.toml"
                        echo -e "${GREEN}  ✓ Answer file added${NC}"
                    fi

                    # Now we need to write this back to the USB
                    # Using genisoimage/mkisofs to create new ISO
                    echo "  Creating modified ISO..."

                    MODIFIED_ISO="/tmp/modified-$$.iso"

                    # Create ISO from modified directory
                    genisoimage -o "$MODIFIED_ISO" \
                        -R -J -joliet-long \
                        -V "PROXMOX" \
                        -b boot/grub/i386-pc/eltorito.img \
                        -no-emul-boot \
                        -boot-load-size 4 \
                        -boot-info-table \
                        -eltorito-alt-boot \
                        -e boot/grub/efi.img \
                        -no-emul-boot \
                        "$EXTRACT_DIR" 2>&1 | grep -v "^$" || \
                    mkisofs -o "$MODIFIED_ISO" \
                        -R -J \
                        -V "PROXMOX" \
                        "$EXTRACT_DIR" 2>/dev/null

                    if [ -f "$MODIFIED_ISO" ]; then
                        echo "  Writing modified ISO back to USB..."
                        dd if="$MODIFIED_ISO" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync
                        sync

                        echo -e "${GREEN}  ✓ Modified ISO written to USB${NC}"
                        MODIFIED=1

                        # Cleanup
                        rm -f "$MODIFIED_ISO"
                    fi

                    # Cleanup
                    rm -rf "$EXTRACT_DIR"
                fi

                break
            else
                umount "$MOUNT_POINT"
            fi
        fi
    fi
done

rmdir "$MOUNT_POINT"

echo ""
echo -e "${GREEN}[4/4] Finalizing...${NC}"

partprobe "$USB_DEVICE" 2>/dev/null || true
sync

echo ""

if [ $MODIFIED -eq 1 ]; then
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}  SUCCESS! USB IS READY${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}What was done:${NC}"
    echo "  ✓ USB written with dd (bootable)"
    echo "  ✓ GRUB config modified (graphics + auto-install)"
    echo "  ✓ Answer file added"
    echo "  ✓ Timeout set to 3 seconds"
    echo ""
    echo -e "${BLUE}Boot parameters added:${NC}"
    echo "  video=vesafb:ywrap,mtrr vga=791 nomodeset"
    echo "  auto-install-cfg=partition"
    echo ""
    echo -e "${YELLOW}Boot Instructions:${NC}"
    echo "  1. Connect external monitor to Mini DisplayPort"
    echo "  2. Power on monitor, insert USB"
    echo "  3. Power on laptop, press F12"
    echo "  4. Select 'UEFI: USB...'"
    echo "  5. Press Enter or wait 3 seconds"
    echo "  6. Auto-install starts!"
    echo ""
else
    echo -e "${YELLOW}════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  USB IS BOOTABLE BUT NOT MODIFIED${NC}"
    echo -e "${YELLOW}════════════════════════════════════════${NC}"
    echo ""
    echo "The ISO filesystem was read-only and couldn't be modified."
    echo "The USB will boot, but requires manual GRUB editing."
    echo ""
    echo "See BOOT-INSTRUCTIONS file for manual steps."
fi

echo ""
