#!/bin/bash
# Deploy AmneziaWG Sweden container to MikroTik Chateau
# Usage: ./deploy-amneziawg-sweden.sh
#
# Prerequisites:
# - MikroTik Chateau accessible via SSH
# - Container package installed on RouterOS
# - USB storage mounted at /usb1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
ROUTER_HOST="${MIKROTIK_HOST:-192.168.88.1}"
ROUTER_USER="${MIKROTIK_USER:-admin}"
AWG_IMAGE="catesin/awg-mikrotik:3.0"
AWG_CONFIG="$PROJECT_ROOT/configs/mikrotik/containers/amneziawg-sweden/awg0.conf"

echo "=== AmneziaWG Sweden Container Deployment ==="
echo "Router: $ROUTER_HOST"
echo "Image: $AWG_IMAGE"

# Check if config exists
if [[ ! -f "$AWG_CONFIG" ]]; then
    echo "ERROR: AWG config not found: $AWG_CONFIG"
    exit 1
fi

echo ""
echo "Step 1: Create veth interface for AWG Sweden container"
ssh "$ROUTER_USER@$ROUTER_HOST" <<'MIKROTIK_VETH'
# Create veth interface for AmneziaWG Sweden container
/interface veth remove [find name=veth-awg-se]
/interface veth add name=veth-awg-se address=172.18.21.2/30 gateway=172.18.21.1

# Add IP to router side
/ip address remove [find address="172.18.21.1/30"]
/ip address add address=172.18.21.1/30 interface=veth-awg-se comment="AWG Sweden container gateway"

:put "veth-awg-se interface created"
MIKROTIK_VETH

echo ""
echo "Step 2: Create container directories"
ssh "$ROUTER_USER@$ROUTER_HOST" <<'MIKROTIK_DIRS'
# Create directories for AWG Sweden container
:do {
    /file remove [find name~"usb1/containers/amneziawg-sweden"]
} on-error={}
/tool fetch url="http://127.0.0.1/" dst-path="usb1/containers/amneziawg-sweden/config/.gitkeep"
:delay 1
:put "Container directories ready"
MIKROTIK_DIRS

echo ""
echo "Step 3: Upload AWG configuration"
scp "$AWG_CONFIG" "$ROUTER_USER@$ROUTER_HOST:/usb1/containers/amneziawg-sweden/config/awg0.conf"
echo "Configuration uploaded"

echo ""
echo "Step 4: Pull container image and configure"
ssh "$ROUTER_USER@$ROUTER_HOST" <<MIKROTIK_CONTAINER
# Configure container mount
/container mounts remove [find name=awg_se_conf]
/container mounts add name=awg_se_conf src=/usb1/containers/amneziawg-sweden/config dst=/etc/amnezia/amneziawg

# Remove existing container
/container remove [find comment~"AmneziaWG Sweden"]

# Pull and configure container
/container add \\
    remote-image=$AWG_IMAGE \\
    interface=veth-awg-se \\
    root-dir=/usb1/containers/amneziawg-sweden/rootfs \\
    mounts=awg_se_conf \\
    logging=yes \\
    start-on-boot=yes \\
    comment="AmneziaWG VPN client for Sweden exit"

:put "Container configured, pulling image..."
MIKROTIK_CONTAINER

echo ""
echo "Step 5: Add VPN endpoint route (prevent routing loop)"
ssh "$ROUTER_USER@$ROUTER_HOST" <<'MIKROTIK_ROUTE'
# Remove existing endpoint route if any
/ip route remove [find comment~"AmneziaWG Sweden endpoint"]

# Add static route for VPN endpoint via WAN
# This prevents routing loop: container traffic to VPN server must not go through tunnel
/ip route add dst-address=146.70.206.133/32 gateway=ether1 distance=1 \
    comment="AmneziaWG Sweden endpoint - bypass tunnel"

:put "VPN endpoint route added"
MIKROTIK_ROUTE

echo ""
echo "Step 6: Configure forward rule for container egress"
ssh "$ROUTER_USER@$ROUTER_HOST" <<'MIKROTIK_FW'
# Allow container to reach internet (for VPN tunnel)
/ip firewall filter remove [find comment~"AWG Sweden container"]
/ip firewall filter add chain=forward action=accept \
    in-interface=veth-awg-se out-interface=ether1 \
    comment="AWG Sweden container WAN egress" \
    place-before=[/ip firewall filter find action=drop chain=forward]

:put "Firewall rule added"
MIKROTIK_FW

echo ""
echo "Step 7: Wait for image pull and start container"
ssh "$ROUTER_USER@$ROUTER_HOST" <<'MIKROTIK_START'
# Wait for image to be pulled (check status)
:local maxwait 120
:local waited 0
:while ([/container get [find comment~"AmneziaWG Sweden"] status] != "stopped" && $waited < $maxwait) do={
    :delay 5
    :set waited ($waited + 5)
    :put "Waiting for image pull... ($waited s)"
}

# Start container
/container start [find comment~"AmneziaWG Sweden"]
:delay 3

:local status [/container get [find comment~"AmneziaWG Sweden"] status]
:put "Container status: $status"
MIKROTIK_START

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Verify container: ssh $ROUTER_USER@$ROUTER_HOST '/container print'"
echo "2. Check logs: ssh $ROUTER_USER@$ROUTER_HOST '/log print where topics~\"container\"'"
echo "3. Configure WiFi AP for VLAN 58:"
echo "   /interface wifi add name=wifi-vpn-sweden master-interface=wifi1 ..."
echo "4. Test: Connect device to VPN-Sweden WiFi and check IP"
echo ""
echo "To apply Terraform for VLAN/routing:"
echo "  cd $PROJECT_ROOT/generated/home-lab/terraform/mikrotik"
echo "  terraform plan && terraform apply"
echo ""
