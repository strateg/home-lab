#!/bin/bash
# Post-Install Script 03: Configure Storage
# Proxmox VE 9 - Dell XPS L701X
# Configure HDD storage pool

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Configuring Storage${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""

# Storage configuration
HDD_MOUNT_POINT="/mnt/hdd"
HDD_DEVICE="/dev/sdb"
HDD_PARTITION="${HDD_DEVICE}1"
STORAGE_ID="local-hdd"

# ============================================================
# Detect HDD
# ============================================================

echo -e "${BLUE}[1/7]${NC} Detecting HDD..."

# List all disks
echo "Available disks:"
lsblk -d -o NAME,SIZE,TYPE,MODEL

# Check if HDD device exists
if [ ! -b "$HDD_DEVICE" ]; then
    echo -e "${RED}✗${NC} HDD device $HDD_DEVICE not found"
    echo ""
    echo "Please check available devices above and update HDD_DEVICE in script"
    exit 1
fi

HDD_SIZE=$(lsblk -b -d -n -o SIZE "$HDD_DEVICE")
HDD_SIZE_GB=$((HDD_SIZE / 1024 / 1024 / 1024))

echo -e "${GREEN}✓${NC} HDD detected: $HDD_DEVICE (${HDD_SIZE_GB} GB)"

# ============================================================
# Partition HDD (if not already partitioned)
# ============================================================

echo -e "${BLUE}[2/7]${NC} Checking HDD partitioning..."

if [ ! -b "$HDD_PARTITION" ]; then
    echo -e "${YELLOW}⚠${NC} HDD not partitioned, creating partition..."

    # Create partition table
    parted -s "$HDD_DEVICE" mklabel gpt
    parted -s "$HDD_DEVICE" mkpart primary ext4 0% 100%

    # Wait for partition to appear
    sleep 2
    partprobe "$HDD_DEVICE"

    echo -e "${GREEN}✓${NC} Partition created: $HDD_PARTITION"
else
    echo -e "${GREEN}✓${NC} HDD already partitioned: $HDD_PARTITION"
fi

# ============================================================
# Format HDD (if not already formatted)
# ============================================================

echo -e "${BLUE}[3/7]${NC} Checking filesystem..."

if ! blkid "$HDD_PARTITION" | grep -q ext4; then
    echo -e "${YELLOW}⚠${NC} Formatting HDD as ext4..."
    echo -e "${RED}WARNING: This will ERASE all data on $HDD_PARTITION${NC}"
    echo ""

    # Format partition
    mkfs.ext4 -F -L "storage-hdd" "$HDD_PARTITION"

    echo -e "${GREEN}✓${NC} HDD formatted as ext4"
else
    echo -e "${GREEN}✓${NC} HDD already formatted as ext4"
fi

# ============================================================
# Create mount point
# ============================================================

echo -e "${BLUE}[4/7]${NC} Creating mount point..."

if [ ! -d "$HDD_MOUNT_POINT" ]; then
    mkdir -p "$HDD_MOUNT_POINT"
    echo -e "${GREEN}✓${NC} Mount point created: $HDD_MOUNT_POINT"
else
    echo -e "${GREEN}✓${NC} Mount point exists: $HDD_MOUNT_POINT"
fi

# ============================================================
# Mount HDD
# ============================================================

echo -e "${BLUE}[5/7]${NC} Mounting HDD..."

# Unmount if already mounted
if mount | grep -q "$HDD_MOUNT_POINT"; then
    umount "$HDD_MOUNT_POINT"
fi

# Mount HDD
mount "$HDD_PARTITION" "$HDD_MOUNT_POINT"

# Verify mount
if mount | grep -q "$HDD_MOUNT_POINT"; then
    echo -e "${GREEN}✓${NC} HDD mounted successfully"
    df -h "$HDD_MOUNT_POINT"
else
    echo -e "${RED}✗${NC} Failed to mount HDD"
    exit 1
fi

# ============================================================
# Add to /etc/fstab
# ============================================================

echo -e "${BLUE}[6/7]${NC} Configuring automatic mount..."

# Get UUID
HDD_UUID=$(blkid -s UUID -o value "$HDD_PARTITION")

# Check if already in fstab
if grep -q "$HDD_UUID" /etc/fstab; then
    echo -e "${GREEN}✓${NC} HDD already in /etc/fstab"
else
    # Backup fstab
    cp /etc/fstab /etc/fstab.bak

    # Add to fstab
    echo "UUID=$HDD_UUID $HDD_MOUNT_POINT ext4 defaults,noatime 0 2" >> /etc/fstab

    echo -e "${GREEN}✓${NC} HDD added to /etc/fstab"
fi

# ============================================================
# Create directory structure
# ============================================================

echo ""
echo -e "${BLUE}Creating storage directory structure...${NC}"

mkdir -p "$HDD_MOUNT_POINT"/{backup,iso,template,snippets,dump}
chmod 755 "$HDD_MOUNT_POINT"
chmod 755 "$HDD_MOUNT_POINT"/{backup,iso,template,snippets,dump}

echo -e "${GREEN}✓${NC} Directory structure created:"
tree -L 1 "$HDD_MOUNT_POINT" 2>/dev/null || ls -la "$HDD_MOUNT_POINT"

# ============================================================
# Configure Proxmox storage
# ============================================================

echo ""
echo -e "${BLUE}[7/7]${NC} Configuring Proxmox storage pool..."

# Check if storage already exists
if pvesm status | grep -q "$STORAGE_ID"; then
    echo -e "${GREEN}✓${NC} Proxmox storage '$STORAGE_ID' already configured"
else
    # Add storage to Proxmox
    pvesm add dir "$STORAGE_ID" \
        --path "$HDD_MOUNT_POINT" \
        --content backup,iso,vztmpl,snippets \
        --prune-backups "keep-last=3,keep-daily=7,keep-weekly=4,keep-monthly=6,keep-yearly=1" \
        --maxfiles 0

    echo -e "${GREEN}✓${NC} Proxmox storage '$STORAGE_ID' configured"
fi

# Display storage status
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Storage Status:${NC}"
pvesm status
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"

echo ""
echo -e "${GREEN}✓ Storage configuration complete!${NC}"
echo ""
echo "Storage details:"
echo "  Device: $HDD_DEVICE"
echo "  Partition: $HDD_PARTITION"
echo "  Mount point: $HDD_MOUNT_POINT"
echo "  Size: ${HDD_SIZE_GB} GB"
echo "  Proxmox storage ID: $STORAGE_ID"
echo ""
echo "Next: Run ./04-configure-network.sh"
