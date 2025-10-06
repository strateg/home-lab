#!/bin/bash
# Create OPNsense VM Template on Proxmox
# Stores template on HDD for later cloning to production

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common-functions.sh"

# Configuration
TEMPLATE_ID="${1:-910}"
TEMPLATE_NAME="opnsense-template"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local-hdd}"
TEMPLATE_DISK_SIZE="${TEMPLATE_DISK_SIZE:-32}"
ISO_STORAGE="${ISO_STORAGE:-local-hdd}"
ISO_NAME="OPNsense-24.7-dvd-amd64.iso"
ISO_URL="https://mirror.ams1.nl.leaseweb.net/opnsense/releases/24.7/OPNsense-24.7-dvd-amd64.iso.bz2"

show_banner "OPNsense Template Creation"

print_info "Configuration:"
echo "  Template ID: $TEMPLATE_ID"
echo "  Template Name: $TEMPLATE_NAME"
echo "  Storage: $TEMPLATE_STORAGE"
echo "  Disk Size: ${TEMPLATE_DISK_SIZE}G"
echo "  ISO Storage: $ISO_STORAGE"
echo ""

# Check if template already exists
if template_exists "$TEMPLATE_ID"; then
    print_warning "Template $TEMPLATE_ID already exists"
    read -p "Remove existing template and recreate? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        print_info "Removing existing template..."
        qm destroy "$TEMPLATE_ID"
    else
        print_error "Template creation cancelled"
        exit 1
    fi
fi

# Step 1: Download OPNsense ISO if not exists
print_step "1" "Downloading OPNsense ISO"

ISO_DIR="/var/lib/vz/template/iso"
ISO_PATH="${ISO_DIR}/${ISO_NAME}"

if [ ! -f "$ISO_PATH" ]; then
    print_info "Downloading OPNsense ISO..."
    cd "$ISO_DIR"

    wget -c "$ISO_URL" -O "${ISO_NAME}.bz2"

    print_info "Extracting ISO..."
    bunzip2 "${ISO_NAME}.bz2"

    print_success "ISO downloaded and extracted"
else
    print_success "ISO already exists: $ISO_PATH"
fi

# Step 2: Create VM
print_step "2" "Creating OPNsense VM"

qm create "$TEMPLATE_ID" \
    --name "$TEMPLATE_NAME" \
    --memory 4096 \
    --cores 2 \
    --cpu host \
    --machine q35 \
    --bios ovmf \
    --ostype other \
    --scsihw virtio-scsi-pci \
    --ide2 "${ISO_STORAGE}:iso/${ISO_NAME},media=cdrom"

print_success "VM created with ID $TEMPLATE_ID"

# Step 3: Add EFI Disk
print_step "3" "Adding EFI disk"

qm set "$TEMPLATE_ID" --efidisk0 "${TEMPLATE_STORAGE}:1,format=raw,efitype=4m,pre-enrolled-keys=1"

# Step 4: Add system disk
print_step "4" "Adding system disk"

qm set "$TEMPLATE_ID" --scsi0 "${TEMPLATE_STORAGE}:${TEMPLATE_DISK_SIZE},format=raw"

# Step 5: Configure network adapters
print_step "5" "Configuring network adapters"

# net0 - WAN (vmbr0)
qm set "$TEMPLATE_ID" --net0 virtio,bridge=vmbr0,firewall=0

# net1 - LAN (vmbr1)
qm set "$TEMPLATE_ID" --net1 virtio,bridge=vmbr1,firewall=0

# net2 - INTERNAL (vmbr2)
qm set "$TEMPLATE_ID" --net2 virtio,bridge=vmbr2,firewall=0

# net3 - MGMT (vmbr99)
qm set "$TEMPLATE_ID" --net3 virtio,bridge=vmbr99,firewall=0

print_success "Network adapters configured"

# Step 6: Additional settings
print_step "6" "Applying additional settings"

qm set "$TEMPLATE_ID" \
    --boot order=scsi0 \
    --bootdisk scsi0 \
    --onboot 1 \
    --startup order=1,up=60,down=60 \
    --protection 0 \
    --agent enabled=0

print_success "Additional settings applied"

# Step 7: Show configuration
print_step "7" "VM Configuration"

qm config "$TEMPLATE_ID"

echo ""
print_warning "MANUAL INSTALLATION REQUIRED"
echo ""
echo "Next steps:"
echo "  1. Start VM: qm start $TEMPLATE_ID"
echo "  2. Access console: qm terminal $TEMPLATE_ID"
echo "     or use Proxmox Web UI"
echo ""
echo "  3. Install OPNsense:"
echo "     - Login: installer / opnsense"
echo "     - Select 'Install (UFS)'"
echo "     - Choose disk: da0"
echo "     - Complete installation"
echo ""
echo "  4. Configure network interfaces:"
echo "     - WAN: vtnet0 (DHCP from ISP)"
echo "     - LAN: vtnet1 (192.168.10.1/24)"
echo ""
echo "  5. After installation completes:"
echo "     - Remove ISO: qm set $TEMPLATE_ID --delete ide2"
echo "     - Shutdown VM: qm shutdown $TEMPLATE_ID"
echo "     - Convert to template: qm template $TEMPLATE_ID"
echo ""
echo "  6. Access OPNsense Web UI:"
echo "     https://192.168.10.1"
echo "     Login: root / opnsense"
echo ""
echo "  7. Complete wizard and configure:"
echo "     - INTERNAL interface: vtnet2 (10.0.30.254/24)"
echo "     - MGMT interface: vtnet3 (10.0.99.10/24)"
echo "     - Firewall rules (see opnsense/configs/)"
echo ""

print_success "OPNsense VM template prepared"
print_info "Template will be stored on: $TEMPLATE_STORAGE"

echo ""
read -p "Start VM now for installation? (y/n): " start_vm
if [[ "$start_vm" =~ ^[Yy]$ ]]; then
    qm start "$TEMPLATE_ID"
    print_success "VM started"
    echo ""
    echo "Access console: qm terminal $TEMPLATE_ID"
    echo "Or use Proxmox Web UI: https://$(hostname -I | awk '{print $1}'):8006"
fi
