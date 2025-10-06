#!/bin/bash
# Deploy OPNsense VM from template
# Clones template from HDD to production on SSD

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common-functions.sh"

# Configuration
TEMPLATE_ID="${TEMPLATE_ID:-910}"
VM_ID="${1:-100}"
VM_NAME="${2:-opnsense-firewall}"
VM_STORAGE="${VM_STORAGE:-local-lvm}"

show_banner "OPNsense VM Deployment"

print_info "Configuration:"
echo "  Template ID: $TEMPLATE_ID"
echo "  VM ID: $VM_ID"
echo "  VM Name: $VM_NAME"
echo "  Storage: $VM_STORAGE"
echo ""

# Check if template exists
if ! template_exists "$TEMPLATE_ID"; then
    print_error "Template $TEMPLATE_ID does not exist"
    echo "Create template first: bash vms/create-opnsense-template.sh"
    exit 1
fi

# Check if VM already exists
if vm_exists "$VM_ID"; then
    print_warning "VM $VM_ID already exists"
    read -p "Remove existing VM and redeploy? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        print_info "Stopping and removing existing VM..."
        qm stop "$VM_ID" || true
        sleep 2
        qm destroy "$VM_ID"
    else
        print_error "Deployment cancelled"
        exit 1
    fi
fi

# Step 1: Clone template
print_step "1" "Cloning template $TEMPLATE_ID → VM $VM_ID"

qm clone "$TEMPLATE_ID" "$VM_ID" \
    --name "$VM_NAME" \
    --full \
    --storage "$VM_STORAGE"

print_success "VM cloned successfully"

# Step 2: Configure VM settings
print_step "2" "Configuring VM settings"

qm set "$VM_ID" \
    --onboot 1 \
    --startup order=1,up=60,down=60 \
    --protection 1 \
    --description "OPNsense Firewall

Network Configuration:
- WAN (vtnet0):      vmbr0 - DHCP from ISP
- LAN (vtnet1):      vmbr1 - 192.168.10.1/24 → OpenWRT
- INTERNAL (vtnet2): vmbr2 - 10.0.30.254/24 → LXC
- MGMT (vtnet3):     vmbr99 - 10.0.99.10/24 → Admin

Access:
- Web UI: https://192.168.10.1 or https://10.0.99.10
- SSH: ssh root@192.168.10.1
- Default credentials: root/opnsense

Deployed: $(date '+%Y-%m-%d %H:%M:%S')
From template: $TEMPLATE_ID
Storage: $VM_STORAGE"

print_success "VM configured"

# Step 3: Start VM
print_step "3" "Starting VM"

qm start "$VM_ID"

print_success "VM started"

# Wait for boot
print_info "Waiting for OPNsense to boot (60 seconds)..."
sleep 60

# Step 4: Show status
print_step "4" "VM Status"

qm status "$VM_ID"
echo ""

# Network configuration
print_info "Network Configuration:"
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║             OPNsense Network Interfaces                      ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  vtnet0 (WAN)      → vmbr0 → ISP Router                     ║"
echo "║    DHCP from ISP (~192.168.1.x)                             ║"
echo "║                                                              ║"
echo "║  vtnet1 (LAN)      → vmbr1 → OpenWRT WAN                    ║"
echo "║    192.168.10.1/24                                          ║"
echo "║                                                              ║"
echo "║  vtnet2 (INTERNAL) → vmbr2 → LXC Containers                 ║"
echo "║    10.0.30.254/24 (Gateway for containers)                  ║"
echo "║                                                              ║"
echo "║  vtnet3 (MGMT)     → vmbr99 → Management                    ║"
echo "║    10.0.99.10/24                                            ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

print_success "OPNsense VM deployed successfully!"
echo ""
echo "Next steps:"
echo "  1. Access Web UI: https://192.168.10.1"
echo "     or via management: https://10.0.99.10"
echo ""
echo "  2. Login with: root / opnsense"
echo ""
echo "  3. Complete configuration wizard if needed"
echo ""
echo "  4. Configure firewall rules:"
echo "     See: opnsense/configs/opnsense-interfaces-config.txt"
echo ""
echo "  5. Update LXC containers to use OPNsense as gateway:"
echo "     Gateway: 10.0.30.254 (OPNsense INTERNAL)"
echo ""
echo "Useful commands:"
echo "  - Check status: qm status $VM_ID"
echo "  - View console: qm terminal $VM_ID"
echo "  - Restart: qm reboot $VM_ID"
echo "  - Stop: qm stop $VM_ID"
echo "  - Backup: vzdump $VM_ID --storage local-hdd"
echo ""
