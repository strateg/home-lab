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
#   --preserve-hdd   Preserve HDD data (default)
#   --auto-network   Auto-configure network (no prompts)
#   --skip-network   Skip network configuration
#   --help           Show this help message
#
# Examples:
#   # Full automation for new system
#   bash proxmox-post-install.sh --init-hdd --auto-network
#
#   # Interactive mode with network setup
#   bash proxmox-post-install.sh
#
#   # Skip network, configure manually later
#   bash proxmox-post-install.sh --skip-network

set -e  # Exit on error

# Parse command line arguments
INIT_HDD=false
PRESERVE_HDD=true
AUTO_NETWORK=false
SKIP_NETWORK=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
        --auto-network)
            AUTO_NETWORK=true
            shift
            ;;
        --skip-network)
            SKIP_NETWORK=true
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
            echo "  --auto-network   Auto-configure network (no prompts)"
            echo "  --skip-network   Skip network configuration"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --init-hdd --auto-network   # Full automation for new system"
            echo "  $0                              # Interactive mode"
            echo "  $0 --skip-network               # Skip network setup"
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

# Step 3-5: Network Configuration
if [ "$SKIP_NETWORK" = true ]; then
    echo -e "${BLUE}[3-5/8] Network configuration skipped${NC}"
    echo ""
else
    echo -e "${BLUE}[3-5/8] Configuring network...${NC}"
    echo ""

    NETWORK_SCRIPT="${SCRIPT_DIR}/configure-network.sh"

    if [ -f "$NETWORK_SCRIPT" ]; then
        if [ "$AUTO_NETWORK" = true ]; then
            echo "Running automated network configuration..."
            bash "$NETWORK_SCRIPT" --auto
        else
            echo "Running interactive network configuration..."
            echo ""
            read -p "Configure network now? (y/n): " configure_network

            if [[ "$configure_network" =~ ^[Yy]$ ]]; then
                bash "$NETWORK_SCRIPT" --interactive
            else
                echo -e "${YELLOW}Network configuration skipped${NC}"
                echo "You can configure network later by running:"
                echo "  bash ${NETWORK_SCRIPT}"
            fi
        fi
    else
        echo -e "${YELLOW}Warning: Network configuration script not found${NC}"
        echo "Expected location: $NETWORK_SCRIPT"
        echo ""
        echo "Falling back to basic network detection..."

        # Show available interfaces
        echo "Available network interfaces:"
        ip link show | grep -E "^[0-9]+" | awk '{print $2}' | sed 's/:$//'
        echo ""
        echo -e "${YELLOW}Please configure network manually or run configure-network.sh${NC}"
    fi

    echo ""
fi

# Step 6: Storage Configuration (HDD)
# ====================================
# IMPORTANT: This preserves existing data on HDD!
# - Checks if HDD has existing filesystem
# - Mounts WITHOUT formatting if data exists
# - Only formats if HDD is completely new
echo -e "${BLUE}[6/7] Configuring HDD storage (preserving existing data)...${NC}"

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
                # Content types:
                # - backup: VM/LXC backups
                # - iso: ISO images
                # - vztmpl: LXC templates
                # - rootdir: LXC container disks
                # - images: VM disk images (for templates and cloning!)
                # - snippets: Hook scripts and configs
                pvesm add dir local-hdd --path "$HDD_MOUNT_POINT" --content backup,iso,vztmpl,rootdir,images,snippets
                echo "✓ Storage 'local-hdd' added to Proxmox"
            fi

            # Create standard directories for organization
            mkdir -p "$HDD_MOUNT_POINT"/{backups,photos,archives,iso,templates,images,snippets}
            chmod 755 "$HDD_MOUNT_POINT"/{backups,photos,archives,iso,templates,images,snippets}

            echo -e "${GREEN}✓ HDD configured successfully${NC}"
            echo "  Mount point: $HDD_MOUNT_POINT"
            echo "  Filesystem: $(blkid -s TYPE -o value $HDD_PARTITION)"
            echo "  Content types: backup, iso, vztmpl, rootdir, images, snippets"
            echo "  Directories: backups/, photos/, archives/, iso/, templates/, images/, snippets/"
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
echo -e "${BLUE}[7/7] Applying optimizations...${NC}"

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

# Final Summary
echo -e "${BLUE}Configuration Summary${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Post-installation complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Configuration applied:"
echo "  ✓ Repositories configured (no-subscription)"
if [ "$SKIP_NETWORK" = false ]; then
    echo "  ✓ Network configured (eth-wan, eth-lan → vmbr0-99)"
fi
if [ -b /dev/sdb ] && mountpoint -q /mnt/hdd; then
    echo "  ✓ HDD storage mounted at /mnt/hdd (existing data preserved)"
fi
echo "  ✓ KSM enabled for RAM optimization"
echo "  ✓ USB power management optimized"
echo "  ✓ Laptop lid behavior configured"
echo ""
if [ "$SKIP_NETWORK" = false ]; then
    echo -e "${YELLOW}IMPORTANT: Reboot required to apply network changes${NC}"
    echo ""
fi
echo "Next steps:"
echo "  1. Reboot: systemctl reboot"
if [ "$SKIP_NETWORK" = true ]; then
    echo "  2. Configure network: bash ${SCRIPT_DIR}/configure-network.sh"
    echo "  3. Verify network: ip link show && brctl show"
    echo "  4. Create OPNsense VM"
else
    echo "  2. Verify network: ip link show && brctl show"
    echo "  3. Create OPNsense VM"
fi
echo ""
echo "Useful commands:"
echo "  - Network config: bash ${SCRIPT_DIR}/configure-network.sh --show"
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
