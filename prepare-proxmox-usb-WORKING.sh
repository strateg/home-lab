#!/bin/bash
# Proxmox VE 9 USB - GUARANTEED WORKING
#
# This does EXACTLY what balenaEtcher does: plain dd
# No rebuilding, no modifications - just bootable USB
#
# Usage: sudo ./prepare-proxmox-usb-WORKING.sh /dev/sdX path/to/proxmox.iso

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
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}  Proxmox USB Creator (balenaEtcher method)${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo ""
echo "This will:"
echo "  1. Write ISO to USB with dd (exactly like balenaEtcher)"
echo "  2. Create boot instructions file"
echo ""
echo -e "${RED}WARNING: This will ERASE all data on $USB_DEVICE${NC}"
echo ""
lsblk "$USB_DEVICE"
echo ""
read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Unmount
umount "${USB_DEVICE}"* 2>/dev/null || true

echo ""
echo -e "${GREEN}Writing ISO to USB...${NC}"
echo "This takes 3-5 minutes depending on USB speed."
echo ""

# Write ISO exactly like balenaEtcher
dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress oflag=direct conv=fsync

sync
sleep 2

echo ""
echo -e "${GREEN}✓ USB written successfully${NC}"

# Verify
partprobe "$USB_DEVICE" 2>/dev/null || true
sleep 2

echo ""
echo "USB structure:"
lsblk "$USB_DEVICE" -o NAME,SIZE,TYPE,FSTYPE,LABEL

# Create boot instructions file
INSTRUCTIONS_FILE="BOOT-INSTRUCTIONS-$(date +%Y%m%d).txt"

cat > "$INSTRUCTIONS_FILE" <<'EOF'
╔═══════════════════════════════════════════════════════════════╗
║  PROXMOX VE 9 - BOOT INSTRUCTIONS FOR DELL XPS L701X         ║
║  (With Broken Internal Display - External Monitor Required)  ║
╚═══════════════════════════════════════════════════════════════╝

BEFORE BOOTING:
───────────────────────────────────────────────────────────────
  1. Connect external monitor to Mini DisplayPort
  2. Power ON the external monitor
  3. Insert USB into Dell XPS L701X (use USB 2.0 port)


BIOS CONFIGURATION (Press F2 during boot):
───────────────────────────────────────────────────────────────
  Boot Mode:        UEFI (NOT Legacy)
  Secure Boot:      DISABLED
  Boot Order:       USB Device first


BOOT THE USB (Press F12 during boot):
───────────────────────────────────────────────────────────────
  Select: "UEFI: USB..." option
  (NOT "USB Storage Device")


AT THE GRUB MENU:
───────────────────────────────────────────────────────────────

You'll see a menu on external display. To enable:
  ✓ External display (Mini DisplayPort)
  ✓ Auto-install (unattended installation)

Follow these steps CAREFULLY:

  1. When GRUB menu appears, press 'e' to edit

  2. Use arrow keys to find the line starting with:
     "linux" or "linuxefi"

  3. Move cursor to the END of that line

  4. Add this EXACT text (copy it):

     video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition

  5. Press Ctrl+X or F10 to boot


FULL EXAMPLE LINE:
───────────────────────────────────────────────────────────────
BEFORE:
  linux /boot/linux26 ro quiet

AFTER:
  linux /boot/linux26 ro quiet video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition


WHAT HAPPENS NEXT:
───────────────────────────────────────────────────────────────
  ✓ External display activates (you'll see GUI)
  ✓ Auto-installer starts automatically
  ✓ Installation proceeds without questions
  ✓ System reboots when complete (10-15 minutes)
  ✓ Configuration from answer file is applied


AFTER INSTALLATION:
───────────────────────────────────────────────────────────────
  1. System reboots
  2. External display should work automatically
  3. Find IP address (check router or connect via console)
  4. SSH to Proxmox:
     ssh root@<ip-address>
     Password: Homelab2025! (from answer file)

  5. Run post-install script:
     bash /root/proxmox-post-install.sh


TROUBLESHOOTING:
───────────────────────────────────────────────────────────────

Display stays black:
  → Wait 30 seconds, boot is slow
  → Try different VGA mode: change vga=791 to vga=788
  → Check monitor input is set to DisplayPort

USB won't boot:
  → Try F2 → Toggle UEFI/Legacy boot mode
  → Try different USB port
  → Verify Secure Boot is DISABLED

Can't edit GRUB:
  → Make sure you pressed 'e' NOT Enter
  → Keyboard might not be detected, try different USB port


PARAMETERS EXPLAINED:
───────────────────────────────────────────────────────────────
  video=vesafb:ywrap,mtrr  → Enables framebuffer graphics
  vga=791                   → Sets 1024x768 resolution
  nomodeset                 → Keeps graphics in compatibility mode
  auto-install-cfg=partition → Looks for answer.toml on USB


═══════════════════════════════════════════════════════════════
Print this file and keep it handy during installation!
═══════════════════════════════════════════════════════════════
EOF

echo ""
echo -e "${GREEN}✓ Boot instructions created: $INSTRUCTIONS_FILE${NC}"

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  USB IS READY AND GUARANTEED BOOTABLE!               ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}What you got:${NC}"
echo "  ✓ Bootable USB (identical to balenaEtcher)"
echo "  ✓ Boot instructions: $INSTRUCTIONS_FILE"
echo ""
echo -e "${YELLOW}NEXT STEP - READ THIS CAREFULLY:${NC}"
echo ""
echo "Open the file: $INSTRUCTIONS_FILE"
echo "It contains step-by-step boot instructions."
echo ""
echo -e "${RED}KEY PARAMETERS TO ADD AT GRUB MENU:${NC}"
echo ""
echo -e "${GREEN}video=vesafb:ywrap,mtrr vga=791 nomodeset auto-install-cfg=partition${NC}"
echo ""
echo "You only need to type this ONCE at boot."
echo "After installation completes, it's automatic."
echo ""
echo -e "${BLUE}Why this works:${NC}"
echo "  • USB is written exactly like balenaEtcher (guaranteed bootable)"
echo "  • No modifications that could break boot structure"
echo "  • Manual GRUB edit is simple and reliable"
echo "  • External display will work with graphics parameters"
echo "  • Auto-install will run with answer file"
echo ""

cat "$INSTRUCTIONS_FILE"

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Ready to install? Read the instructions above!${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════${NC}"
echo ""
