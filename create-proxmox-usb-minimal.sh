#!/bin/bash
# Proxmox USB - MINIMAL APPROACH
#
# Simplest possible:
# 1. dd write (boots - guaranteed)
# 2. Change source path in GRUB loader to OUR file
# 3. Our file has everything
#
# Usage: sudo ./create-proxmox-usb-minimal.sh /dev/sdX proxmox.iso

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

[ $EUID -ne 0 ] && echo -e "${RED}Run as root${NC}" && exit 1
[ $# -ne 2 ] && echo "Usage: sudo $0 /dev/sdX proxmox.iso" && exit 1

USB="$1"
ISO="$2"

[ ! -b "$USB" ] || [ ! -f "$ISO" ] && echo -e "${RED}Invalid device/ISO${NC}" && exit 1
[ ! -f "proxmox-auto-install-answer.toml" ] && echo -e "${RED}answer.toml not found${NC}" && exit 1

echo "ERASE $USB?"
read -p "yes/no: " c
[ "$c" != "yes" ] && exit 0

umount "${USB}"* 2>/dev/null || true

# Step 1: dd write
echo "Writing ISO..."
dd if="$ISO" of="$USB" bs=4M status=progress oflag=direct conv=fsync
sync
sleep 3

# Step 2: Modify GRUB
partprobe "$USB" 2>/dev/null || true
sleep 2

MNT="/tmp/u$$"
mkdir -p "$MNT"

for p in "${USB}"[0-9]* "${USB}p"[0-9]*; do
    [ ! -b "$p" ] && continue
    [ "$(blkid -s TYPE -o value "$p" 2>/dev/null)" != "vfat" ] && continue

    mount -o rw "$p" "$MNT" 2>/dev/null || continue

    GRUB=$(find "$MNT" -name "grub.cfg" 2>/dev/null | head -1)
    [ -z "$GRUB" ] && { umount "$MNT"; continue; }

    echo "Modifying GRUB..."

    UUID=$(grep "search.*fs-uuid" "$GRUB" | grep -o '[0-9-]\{10,\}' | head -1)
    [ -z "$UUID" ] && UUID="2025-08-05-10-48-40-00"

    # Create our own grub config
    cat > "$MNT/grub-auto.cfg" <<EOF
set default=0
set timeout=3
search --fs-uuid --set=root $UUID

menuentry 'Auto Install' {
    linux /boot/linux26 auto-install-cfg=partition ro video=vesafb:ywrap,mtrr vga=791 nomodeset
    initrd /boot/initrd.img
}
EOF

    # Change original to source OUR file
    sed -i "s|source \${prefix}/grub.cfg|source (hd0,gpt2)/grub-auto.cfg|" "$GRUB"

    # Add answer
    cp "proxmox-auto-install-answer.toml" "$MNT/answer.toml"

    sync
    umount "$MNT"

    echo -e "${GREEN}Done!${NC}"
    rmdir "$MNT"
    exit 0
done

rmdir "$MNT"
echo -e "${RED}Failed${NC}"
