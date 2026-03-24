#!/bin/bash
# Configure routing for LXC containers to use OPNsense as gateway
# LXC containers in vmbr2 (10.0.30.0/24) need to route through OPNsense (10.0.30.254)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common-functions.sh"

show_banner "LXC Routing Configuration"

print_info "Network Architecture:"
echo "  Proxmox Host:    10.0.30.1/24   (vmbr2)"
echo "  OPNsense VM:     10.0.30.254/24 (INTERNAL interface)"
echo "  LXC Containers:  10.0.30.10-90  (use 10.0.30.254 as gateway)"
echo ""

# Check if OPNsense is running
if ! vm_exists 100 || [ "$(qm status 100 2>/dev/null | grep -o 'running')" != "running" ]; then
    print_warning "OPNsense VM (100) is not running"
    echo "The routing will be configured, but won't work until OPNsense is started"
    echo ""
fi

# Step 1: Enable IP forwarding on Proxmox
print_step "1" "Enabling IP forwarding on Proxmox host"

if ! grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    sysctl -p
    print_success "IP forwarding enabled"
else
    print_success "IP forwarding already enabled"
fi

# Step 2: Configure iptables for vmbr2
print_step "2" "Configuring iptables rules"

# Allow forwarding on vmbr2
if ! iptables -C FORWARD -i vmbr2 -j ACCEPT 2>/dev/null; then
    iptables -I FORWARD -i vmbr2 -j ACCEPT
    print_success "Added FORWARD rule for vmbr2"
else
    print_success "FORWARD rule already exists"
fi

# Allow established/related connections back
if ! iptables -C FORWARD -o vmbr2 -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null; then
    iptables -I FORWARD -o vmbr2 -m state --state ESTABLISHED,RELATED -j ACCEPT
    print_success "Added ESTABLISHED/RELATED rule"
else
    print_success "ESTABLISHED/RELATED rule already exists"
fi

# Step 3: Make iptables rules persistent
print_step "3" "Making iptables rules persistent"

if ! command -v iptables-save &> /dev/null; then
    print_warning "iptables-persistent not installed"
    read -p "Install iptables-persistent? (y/n): " install_persistent
    if [[ "$install_persistent" =~ ^[Yy]$ ]]; then
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
    fi
fi

if command -v iptables-save &> /dev/null; then
    iptables-save > /etc/iptables/rules.v4
    print_success "Iptables rules saved"
fi

# Step 4: Create systemd service for routing
print_step "4" "Creating systemd service for LXC routing"

cat > /etc/systemd/system/lxc-routing.service <<'EOF'
[Unit]
Description=LXC Container Routing via OPNsense
After=network-online.target pve-cluster.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'sysctl -w net.ipv4.ip_forward=1'
ExecStart=/bin/bash -c 'iptables -C FORWARD -i vmbr2 -j ACCEPT 2>/dev/null || iptables -I FORWARD -i vmbr2 -j ACCEPT'
ExecStart=/bin/bash -c 'iptables -C FORWARD -o vmbr2 -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || iptables -I FORWARD -o vmbr2 -m state --state ESTABLISHED,RELATED -j ACCEPT'

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable lxc-routing.service
systemctl start lxc-routing.service

print_success "Systemd service created and enabled"

# Step 5: Test connectivity
print_step "5" "Testing configuration"

echo "Checking routing table:"
ip route show | grep "10.0.30.0/24" || echo "  No specific route (will use default)"

echo ""
echo "Checking iptables:"
iptables -L FORWARD -n -v | grep vmbr2

echo ""
print_success "Routing configuration complete!"

echo ""
print_info "Network Flow:"
echo "  LXC Container (10.0.30.10)"
echo "    ↓ gateway: 10.0.30.254"
echo "  OPNsense INTERNAL (10.0.30.254)"
echo "    ↓ NAT via WAN"
echo "  Internet"
echo ""

echo "Verification:"
echo "  1. Deploy OPNsense: bash vms/deploy-opnsense.sh"
echo "  2. Configure OPNsense INTERNAL interface: 10.0.30.254/24"
echo "  3. Deploy LXC container: bash services/deploy-postgresql.sh"
echo "  4. Test from container: pct exec 200 -- ping -c 3 8.8.8.8"
echo ""

print_info "OPNsense Configuration Required:"
echo "  Interface: INTERNAL (vtnet2)"
echo "    IP: 10.0.30.254/24"
echo "    Description: LXC Containers Gateway"
echo ""
echo "  Firewall Rules: INTERNAL → WAN"
echo "    Action: Pass"
echo "    Protocol: TCP/UDP"
echo "    Source: 10.0.30.0/24"
echo "    Destination: any"
echo "    Ports: 80, 443, 53 (for updates and DNS)"
echo ""
echo "  NAT: Outbound"
echo "    Mode: Automatic or Hybrid"
echo "    Network: 10.0.30.0/24"
echo "    Translation: WAN address"
echo ""
