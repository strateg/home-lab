#!/bin/bash
# Bootstrap network configuration for srv-orangepi5
# Run this on OrangePi5 console (HDMI) for initial network setup
#
# From topology:
#   - Management: 10.0.99.20/24 via VLAN 99 (native)
#   - Gateway: 10.0.99.1 (Chateau)
#
# Usage:
#   curl -sL https://raw.githubusercontent.com/.../orangepi5-network-init.sh | sudo bash
#   # OR copy-paste and run manually

set -e

INTERFACE="enx00e04c680347"
MGMT_IP="10.0.99.20"
MGMT_PREFIX="24"
MGMT_GATEWAY="10.0.99.1"
MGMT_DNS="10.0.99.1"

echo "=== OrangePi5 Network Bootstrap ==="
echo ""
echo "Configuration:"
echo "  Interface: $INTERFACE"
echo "  IP: $MGMT_IP/$MGMT_PREFIX"
echo "  Gateway: $MGMT_GATEWAY"
echo "  DNS: $MGMT_DNS"
echo ""

# Check interface exists
if ! ip link show "$INTERFACE" &>/dev/null; then
    echo "ERROR: Interface $INTERFACE not found!"
    echo ""
    echo "Available interfaces:"
    ip -br link show
    exit 1
fi

# Check if NetworkManager is available
if command -v nmcli &>/dev/null; then
    echo "Using NetworkManager..."

    # Remove any existing connection for this interface
    nmcli connection delete "management" 2>/dev/null || true
    nmcli connection delete "Wired connection 1" 2>/dev/null || true

    # Create new connection
    nmcli connection add \
        type ethernet \
        con-name "management" \
        ifname "$INTERFACE" \
        ipv4.method manual \
        ipv4.addresses "$MGMT_IP/$MGMT_PREFIX" \
        ipv4.gateway "$MGMT_GATEWAY" \
        ipv4.dns "$MGMT_DNS" \
        connection.autoconnect yes

    # Bring up connection
    nmcli connection up "management"

elif command -v netplan &>/dev/null; then
    echo "Using netplan..."

    cat > /etc/netplan/10-management.yaml << EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    $INTERFACE:
      addresses:
        - $MGMT_IP/$MGMT_PREFIX
      routes:
        - to: default
          via: $MGMT_GATEWAY
      nameservers:
        addresses:
          - $MGMT_DNS
          - 8.8.8.8
EOF

    chmod 600 /etc/netplan/10-management.yaml
    netplan apply

else
    echo "Using ip commands (temporary)..."

    # Flush existing config
    ip addr flush dev "$INTERFACE"

    # Add IP and route
    ip addr add "$MGMT_IP/$MGMT_PREFIX" dev "$INTERFACE"
    ip link set "$INTERFACE" up
    ip route add default via "$MGMT_GATEWAY"

    # Set DNS
    echo "nameserver $MGMT_DNS" > /etc/resolv.conf
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf

    echo ""
    echo "WARNING: This is temporary! Configuration will be lost on reboot."
    echo "Install NetworkManager or netplan for persistent config."
fi

echo ""
echo "=== Verifying configuration ==="
echo ""

echo "Interface:"
ip -br addr show "$INTERFACE"

echo ""
echo "Routes:"
ip route show | grep -E "default|10.0.99"

echo ""
echo "Testing connectivity..."
if ping -c 1 -W 2 "$MGMT_GATEWAY" &>/dev/null; then
    echo "✓ Gateway $MGMT_GATEWAY reachable"
else
    echo "✗ Gateway $MGMT_GATEWAY NOT reachable"
fi

if ping -c 1 -W 2 8.8.8.8 &>/dev/null; then
    echo "✓ Internet reachable"
else
    echo "✗ Internet NOT reachable"
fi

echo ""
echo "=== Done ==="
echo ""
echo "You can now connect via SSH:"
echo "  ssh automator@$MGMT_IP"
echo ""
echo "Run Ansible playbook for full configuration:"
echo "  ansible-playbook -i inventory/production playbooks/network-orangepi5.yml"
