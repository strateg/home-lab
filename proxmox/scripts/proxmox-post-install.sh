#!/bin/bash
# Proxmox VE 9 Post-Installation Configuration Script
# Target: Dell XPS L701X Home Lab
#
# This script configures Proxmox after unattended installation:
# - Disables enterprise repository
# - Configures network interfaces with udev rules
# - Sets up HDD storage (smart detection or forced init)
# - Enables optimizations (KSM, USB power management)
# - Applies home-lab network configuration
#
# Usage:
#   ssh root@<proxmox-ip>
#   bash proxmox-post-install.sh [OPTIONS]
#
# Options:
#   --init-hdd       Force HDD initialization (create partition & format)
#                    Use for NEW systems where HDD needs to be set up
#   --preserve-hdd   Preserve HDD data (default, mount without formatting)
#   --help           Show this help message
#
# Examples:
#   # New system - initialize HDD automatically
#   bash proxmox-post-install.sh --init-hdd
#
#   # Existing system - preserve data (default)
#   bash proxmox-post-install.sh
#   bash proxmox-post-install.sh --preserve-hdd

set -e  # Exit on error

# Parse command line arguments
INIT_HDD=false
PRESERVE_HDD=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --init-hdd)
            INIT_HDD=true
            PRESERVE_HDD=false
            shift
            ;;
        --preserve-hdd)
            INIT_HDD=false
            PRESERVE_HDD=true
            shift
            ;;
        --help|-h)
            echo "Proxmox Post-Installation Configuration Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --init-hdd       Force HDD initialization (NEW systems)"
            echo "  --preserve-hdd   Preserve existing data (default)"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --init-hdd          # New system setup"
            echo "  $0                     # Preserve existing data"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Proxmox Post-Installation Configuration${NC}"
echo -e "${GREEN}Dell XPS L701X Home Lab${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Configuration mode:"
if [ "$INIT_HDD" = true ]; then
    echo -e "  ${YELLOW}HDD: Initialize mode (will format HDD if needed)${NC}"
else
    echo -e "  ${GREEN}HDD: Preserve mode (will NOT format existing data)${NC}"
fi
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}"
   exit 1
fi

# Check if running on Proxmox
if [ ! -f /etc/pve/.version ]; then
    echo -e "${RED}Error: This doesn't appear to be a Proxmox system${NC}"
    exit 1
fi

# Step 1: Repository Configuration
echo -e "${BLUE}[1/8] Configuring repositories...${NC}"

# Disable enterprise repository
if [ -f /etc/apt/sources.list.d/pve-enterprise.list ]; then
    mv /etc/apt/sources.list.d/pve-enterprise.list /etc/apt/sources.list.d/pve-enterprise.list.disabled
    echo "Enterprise repository disabled"
fi

# Add no-subscription repository
if [ ! -f /etc/apt/sources.list.d/pve-no-subscription.list ]; then
    echo "deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription" > /etc/apt/sources.list.d/pve-no-subscription.list
    echo "No-subscription repository added"
fi

# Update package lists
apt-get update

echo -e "${GREEN}✓ Repositories configured${NC}"
echo ""

# Step 2: Install essential packages
echo -e "${BLUE}[2/8] Installing essential packages...${NC}"

apt-get install -y \
    ethtool \
    lm-sensors \
    smartmontools \
    iperf3 \
    htop \
    net-tools \
    bridge-utils

echo -e "${GREEN}✓ Essential packages installed${NC}"
echo ""

# Step 3: Network Interface Detection and Configuration
echo -e "${BLUE}[3/8] Detecting network interfaces...${NC}"

# Show all interfaces
echo "Available network interfaces:"
ip link show | grep -E "^[0-9]+" | awk '{print $2}' | sed 's/:$//'
echo ""

# Detect built-in and USB Ethernet
BUILTIN_IF=$(ip link show | grep -E "en(o|p)" | head -1 | awk '{print $2}' | sed 's/:$//' || echo "")
USB_IF=$(ip link show | grep -E "enx|eth1" | head -1 | awk '{print $2}' | sed 's/:$//' || echo "")

if [ -z "$BUILTIN_IF" ]; then
    echo -e "${YELLOW}Warning: Could not auto-detect built-in Ethernet${NC}"
    echo "Please identify it manually:"
    read -p "Enter built-in Ethernet interface name: " BUILTIN_IF
fi

if [ -z "$USB_IF" ]; then
    echo -e "${YELLOW}Warning: USB-Ethernet not detected (this is normal if not connected)${NC}"
    echo "You can configure it later by re-running this script"
    USB_IF="eth-usb"  # Use target name
fi

echo "Built-in Ethernet: $BUILTIN_IF"
echo "USB-Ethernet: $USB_IF"
echo ""

# Get MAC addresses
BUILTIN_MAC=$(ip link show "$BUILTIN_IF" 2>/dev/null | grep -o 'link/ether [^ ]*' | awk '{print $2}' || echo "")
if [ -n "$USB_IF" ] && [ "$USB_IF" != "eth-usb" ]; then
    USB_MAC=$(ip link show "$USB_IF" 2>/dev/null | grep -o 'link/ether [^ ]*' | awk '{print $2}' || echo "")
else
    USB_MAC=""
fi

echo "Built-in MAC: $BUILTIN_MAC"
if [ -n "$USB_MAC" ]; then
    echo "USB MAC: $USB_MAC"
fi
echo ""

# Create udev rules for persistent naming
echo -e "${BLUE}[4/8] Creating udev rules for persistent interface names...${NC}"

cat > /etc/udev/rules.d/70-persistent-net.rules <<EOF
# Persistent network interface names for Dell XPS L701X
# Auto-generated by proxmox-post-install.sh

# Built-in Ethernet
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="$BUILTIN_MAC", NAME="eth-builtin"

EOF

if [ -n "$USB_MAC" ]; then
cat >> /etc/udev/rules.d/70-persistent-net.rules <<EOF
# USB-Ethernet adapter
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="$USB_MAC", NAME="eth-usb"
EOF
fi

echo -e "${GREEN}✓ udev rules created${NC}"
echo ""

# Step 5: Network Configuration
echo -e "${BLUE}[5/8] Configuring network bridges...${NC}"

# Backup current network config
cp /etc/network/interfaces /etc/network/interfaces.backup

# Apply home-lab network configuration
cat > /etc/network/interfaces <<'EOF'
# Proxmox Network Configuration - Dell XPS L701X Home Lab
# Auto-generated by proxmox-post-install.sh

# Loopback
auto lo
iface lo inet loopback

# Built-in Ethernet - LAN (to OpenWRT)
auto eth-builtin
iface eth-builtin inet manual

# USB-Ethernet adapter - WAN (to ISP Router)
auto eth-usb
iface eth-usb inet manual

# vmbr0 - WAN Bridge (to ISP Router via USB-Ethernet)
auto vmbr0
iface vmbr0 inet manual
    bridge-ports eth-usb
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094
    comment WAN Bridge - OPNsense WAN to ISP Router

# vmbr1 - LAN Bridge (to OpenWRT WAN via built-in Ethernet)
auto vmbr1
iface vmbr1 inet manual
    bridge-ports eth-builtin
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094
    comment LAN Bridge - OPNsense LAN to OpenWRT

# vmbr2 - Internal Bridge (for LXC containers)
auto vmbr2
iface vmbr2 inet static
    address 10.0.30.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    comment Internal Network - LXC containers

# vmbr99 - Management Bridge (emergency access)
auto vmbr99
iface vmbr99 inet static
    address 10.0.99.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    comment Management Network - Emergency access
EOF

echo -e "${GREEN}✓ Network configuration applied${NC}"
echo -e "${YELLOW}Note: Network changes will take effect after reboot${NC}"
echo ""

# Step 6: Storage Configuration (HDD)
# ====================================
# IMPORTANT: This preserves existing data on HDD!
# - Checks if HDD has existing filesystem
# - Mounts WITHOUT formatting if data exists
# - Only formats if HDD is completely new
echo -e "${BLUE}[6/8] Configuring HDD storage (preserving existing data)...${NC}"

# Check if HDD exists
if [ -b /dev/sdb ]; then
    echo "HDD detected: /dev/sdb"

    HDD_DEVICE="/dev/sdb"
    HDD_PARTITION="${HDD_DEVICE}1"
    HDD_MOUNT_POINT="/mnt/hdd"
    HDD_FORMATTED=false

    # Check if partition exists
    if fdisk -l "$HDD_DEVICE" | grep -q "^${HDD_PARTITION}"; then
        echo "Partition exists: ${HDD_PARTITION}"

        # Check if partition has a filesystem
        FS_TYPE=$(blkid -s TYPE -o value "$HDD_PARTITION" 2>/dev/null || echo "")

        if [ -n "$FS_TYPE" ]; then
            if [ "$INIT_HDD" = true ]; then
                echo -e "${YELLOW}⚠ Existing filesystem detected: $FS_TYPE${NC}"
                echo -e "${YELLOW}⚠ --init-hdd flag set, but data exists!${NC}"
                read -p "ERASE all data and reformat? (yes/no): " confirm_erase

                if [ "$confirm_erase" = "yes" ]; then
                    echo "Formatting HDD (destroying existing data)..."
                    mkfs.ext4 -F -L "proxmox-hdd" "$HDD_PARTITION"
                    HDD_FORMATTED=true
                else
                    echo -e "${GREEN}✓ Preserving existing data${NC}"
                    HDD_FORMATTED=true
                fi
            else
                echo -e "${GREEN}✓ Existing filesystem detected: $FS_TYPE${NC}"
                echo -e "${GREEN}✓ Preserving existing data (no formatting)${NC}"
                HDD_FORMATTED=true
            fi
        else
            echo -e "${YELLOW}Partition exists but no filesystem detected${NC}"

            if [ "$INIT_HDD" = true ]; then
                echo "Creating ext4 filesystem (auto mode)..."
                mkfs.ext4 -F -L "proxmox-hdd" "$HDD_PARTITION"
                HDD_FORMATTED=true
            else
                read -p "Format partition as ext4? (yes/no): " format_confirm

                if [ "$format_confirm" = "yes" ]; then
                    echo "Creating ext4 filesystem..."
                    mkfs.ext4 -F -L "proxmox-hdd" "$HDD_PARTITION"
                    HDD_FORMATTED=true
                else
                    echo "Skipping HDD configuration"
                    HDD_FORMATTED=false
                fi
            fi
        fi
    else
        echo -e "${YELLOW}No partition found on HDD${NC}"

        if [ "$INIT_HDD" = true ]; then
            echo "Creating partition and formatting (auto mode)..."
            echo -e "n\np\n1\n\n\nw" | fdisk "$HDD_DEVICE" || true
            sleep 2

            # Reload partition table
            partprobe "$HDD_DEVICE" 2>/dev/null || blockdev --rereadpt "$HDD_DEVICE" 2>/dev/null || true
            sleep 2

            echo "Creating ext4 filesystem..."
            mkfs.ext4 -F -L "proxmox-hdd" "$HDD_PARTITION"
            HDD_FORMATTED=true
        else
            read -p "Create new partition and format as ext4? This will ERASE all data! (yes/no): " create_confirm

            if [ "$create_confirm" = "yes" ]; then
                echo "Creating partition on HDD..."
                echo -e "n\np\n1\n\n\nw" | fdisk "$HDD_DEVICE" || true
                sleep 2

                # Reload partition table
                partprobe "$HDD_DEVICE" 2>/dev/null || blockdev --rereadpt "$HDD_DEVICE" 2>/dev/null || true
                sleep 2

                echo "Creating ext4 filesystem..."
                mkfs.ext4 -F -L "proxmox-hdd" "$HDD_PARTITION"
                HDD_FORMATTED=true
            else
                echo "Skipping HDD configuration"
                HDD_FORMATTED=false
            fi
        fi
    fi

    # Mount and configure if formatted
    if [ "$HDD_FORMATTED" = true ]; then
        # Create mount point
        mkdir -p "$HDD_MOUNT_POINT"

        # Get UUID for reliable mounting
        HDD_UUID=$(blkid -s UUID -o value "$HDD_PARTITION" 2>/dev/null || echo "")

        if [ -n "$HDD_UUID" ]; then
            echo "HDD UUID: $HDD_UUID"

            # Add to fstab using UUID (more reliable than /dev/sdb1)
            if ! grep -q "$HDD_UUID" /etc/fstab; then
                echo "# HDD storage (preserves data across reboots)" >> /etc/fstab
                echo "UUID=$HDD_UUID $HDD_MOUNT_POINT ext4 defaults,nofail 0 2" >> /etc/fstab
                echo "✓ Added to fstab with UUID"
            else
                echo "✓ Already in fstab"
            fi
        else
            # Fallback to device name
            echo -e "${YELLOW}Warning: Could not get UUID, using device name${NC}"
            if ! grep -q "$HDD_MOUNT_POINT" /etc/fstab; then
                echo "$HDD_PARTITION $HDD_MOUNT_POINT ext4 defaults,nofail 0 2" >> /etc/fstab
            fi
        fi

        # Mount HDD
        echo "Mounting HDD..."
        if mount -a; then
            echo -e "${GREEN}✓ HDD mounted at $HDD_MOUNT_POINT${NC}"

            # Show existing data
            if [ -n "$(ls -A $HDD_MOUNT_POINT 2>/dev/null)" ]; then
                echo ""
                echo "Existing data found on HDD:"
                du -sh "$HDD_MOUNT_POINT"/* 2>/dev/null || echo "  (empty directories)"
                echo ""
                df -h "$HDD_MOUNT_POINT"
            else
                echo "HDD is empty (newly formatted)"
            fi

            # Add to Proxmox storage
            echo ""
            echo "Adding HDD to Proxmox storage pool..."
            if pvesm status | grep -q "local-hdd"; then
                echo "✓ Storage 'local-hdd' already exists"
            else
                pvesm add dir local-hdd --path "$HDD_MOUNT_POINT" --content backup,iso,vztmpl,rootdir
                echo "✓ Storage 'local-hdd' added to Proxmox"
            fi

            # Create standard directories for organization
            mkdir -p "$HDD_MOUNT_POINT"/{backups,photos,archives,iso,templates}
            chmod 755 "$HDD_MOUNT_POINT"/{backups,photos,archives,iso,templates}

            echo -e "${GREEN}✓ HDD configured successfully${NC}"
            echo "  Mount point: $HDD_MOUNT_POINT"
            echo "  Filesystem: $(blkid -s TYPE -o value $HDD_PARTITION)"
            echo "  Directories: backups/, photos/, archives/, iso/, templates/"
        else
            echo -e "${RED}✗ Failed to mount HDD${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Warning: HDD (/dev/sdb) not detected${NC}"
    echo "This is normal if:"
    echo "  - HDD is not connected yet"
    echo "  - You're using a single-disk setup"
    echo "  - HDD has a different device name"
    echo ""
    echo "You can configure HDD later by re-running this script"
fi
echo ""

# Step 7: Optimizations
echo -e "${BLUE}[7/8] Applying optimizations...${NC}"

# Enable KSM (Kernel Samepage Merging) for RAM efficiency
cat > /etc/systemd/system/ksm.service <<'EOF'
[Unit]
Description=Enable Kernel Same-page Merging
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo 1 > /sys/kernel/mm/ksm/run'
ExecStart=/bin/sh -c 'echo 1000 > /sys/kernel/mm/ksm/pages_to_scan'

[Install]
WantedBy=multi-user.target
EOF

systemctl enable ksm.service
systemctl start ksm.service
echo "✓ KSM (memory deduplication) enabled"

# Disable USB autosuspend for USB-Ethernet stability
cat > /etc/rc.local <<'EOF'
#!/bin/sh -e
# Disable USB autosuspend for stability
for i in /sys/bus/usb/devices/*/power/control; do
  echo on > $i 2>/dev/null || true
done
exit 0
EOF

chmod +x /etc/rc.local
bash /etc/rc.local
echo "✓ USB autosuspend disabled"

# Configure laptop lid behavior (don't suspend when closed)
if [ -f /etc/systemd/logind.conf ]; then
    sed -i 's/^#*HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf
    sed -i 's/^#*HandleLidSwitchDocked=.*/HandleLidSwitchDocked=ignore/' /etc/systemd/logind.conf
    systemctl restart systemd-logind
    echo "✓ Laptop lid behavior configured (no suspend on close)"
fi

# Setup sensors for temperature monitoring
sensors-detect --auto >/dev/null 2>&1 || true
echo "✓ Temperature sensors configured"

echo -e "${GREEN}✓ Optimizations applied${NC}"
echo ""

# Step 8: Final Summary
echo -e "${BLUE}[8/8] Configuration Summary${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Post-installation complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Configuration applied:"
echo "  ✓ Repositories configured (no-subscription)"
echo "  ✓ Network interfaces: eth-builtin, eth-usb"
echo "  ✓ Bridges: vmbr0 (WAN), vmbr1 (LAN), vmbr2 (Internal), vmbr99 (Mgmt)"
if [ -b /dev/sdb ] && mountpoint -q /mnt/hdd; then
    echo "  ✓ HDD storage mounted at /mnt/hdd (existing data preserved)"
fi
echo "  ✓ KSM enabled for RAM optimization"
echo "  ✓ USB power management optimized"
echo "  ✓ Laptop lid behavior configured"
echo ""
echo -e "${YELLOW}IMPORTANT: Reboot required to apply network changes${NC}"
echo ""
echo "Next steps:"
echo "  1. Reboot: systemctl reboot"
echo "  2. Verify network: ip link show"
echo "  3. Create OPNsense VM"
echo "  4. Configure according to home-lab documentation"
echo ""
echo "Useful commands:"
echo "  - Check bridges: brctl show"
echo "  - Check storage: pvesm status"
echo "  - Check memory: free -h"
echo "  - Check KSM: cat /sys/kernel/mm/ksm/pages_sharing"
echo "  - Monitor temp: watch -n 2 sensors"
echo ""

# Ask for reboot
read -p "Reboot now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Rebooting..."
    systemctl reboot
else
    echo "Please reboot manually when ready: systemctl reboot"
fi
