#!/bin/bash
# Post-Install Script 04: Configure Network
# Proxmox VE 9 - Dell XPS L701X
# Configure network bridges and interfaces

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Configuring Network${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo ""

# ============================================================
# Detect network interfaces
# ============================================================

echo -e "${BLUE}[1/6]${NC} Detecting network interfaces..."
echo ""
echo "Available network interfaces:"
ip link show | grep -E "^[0-9]+:" | awk '{print $2}' | tr -d ':'
echo ""

# Get MAC addresses for identification
USB_ETH_MAC=$(ip link show | grep -A1 "usb" | grep "link/ether" | awk '{print $2}' | head -n1)
BUILTIN_ETH_MAC=$(ip link show | grep -A1 "en" | grep "link/ether" | awk '{print $2}' | head -n1 | grep -v "$USB_ETH_MAC")

echo "USB Ethernet MAC: ${USB_ETH_MAC:-not detected}"
echo "Built-in Ethernet MAC: ${BUILTIN_ETH_MAC:-not detected}"

# ============================================================
# Create UDEV rules for persistent interface naming
# ============================================================

echo ""
echo -e "${BLUE}[2/6]${NC} Creating UDEV rules for persistent interface names..."

# Backup existing rules
if [ -f /etc/udev/rules.d/70-persistent-net.rules ]; then
    cp /etc/udev/rules.d/70-persistent-net.rules /etc/udev/rules.d/70-persistent-net.rules.bak
fi

# Create UDEV rules
cat > /etc/udev/rules.d/70-persistent-net.rules <<EOF
# Dell XPS L701X Network Interface Rules
# Persistent names for USB Ethernet and Built-in Ethernet

# USB Ethernet Adapter (WAN) - Rename to eth-usb
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="$USB_ETH_MAC", NAME="eth-usb"

# Built-in Ethernet (LAN) - Rename to eth-builtin
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="$BUILTIN_ETH_MAC", NAME="eth-builtin"
EOF

echo -e "${GREEN}✓${NC} UDEV rules created: /etc/udev/rules.d/70-persistent-net.rules"

# Apply UDEV rules (requires reboot to take full effect)
udevadm control --reload-rules
udevadm trigger

echo -e "${YELLOW}⚠${NC} UDEV rules will take effect after reboot"

# ============================================================
# Disable USB autosuspend for USB-Ethernet stability
# ============================================================

echo ""
echo -e "${BLUE}[3/6]${NC} Disabling USB autosuspend for stability..."

# Create systemd service to disable USB autosuspend on boot
cat > /etc/systemd/system/disable-usb-autosuspend.service <<'EOF'
[Unit]
Description=Disable USB Autosuspend
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'for i in /sys/bus/usb/devices/*/power/autosuspend; do echo -1 > $i; done'
ExecStart=/bin/bash -c 'for i in /sys/bus/usb/devices/*/power/control; do echo on > $i; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable disable-usb-autosuspend.service
systemctl start disable-usb-autosuspend.service

echo -e "${GREEN}✓${NC} USB autosuspend disabled"

# ============================================================
# Configure network bridges in /etc/network/interfaces
# ============================================================

echo ""
echo -e "${BLUE}[4/6]${NC} Configuring network bridges..."

# Backup current network configuration
cp /etc/network/interfaces /etc/network/interfaces.bak.$(date +%Y%m%d_%H%M%S)

# Create new network configuration
cat > /etc/network/interfaces <<'EOF'
# Dell XPS L701X Network Configuration
# Proxmox VE 9 - Multi-bridge setup

# Loopback interface
auto lo
iface lo inet loopback

# ============================================================
# Physical Interfaces (do not configure directly)
# ============================================================

# USB Ethernet (WAN) - connected to ISP router
iface eth-usb inet manual

# Built-in Ethernet (LAN) - connected to GL.iNet Slate AX
iface eth-builtin inet manual

# ============================================================
# Bridge vmbr0: WAN (to ISP Router)
# ============================================================

auto vmbr0
iface vmbr0 inet dhcp
    bridge-ports eth-usb
    bridge-stp off
    bridge-fd 0
    # This bridge connects to ISP router
    # Gets IP via DHCP from ISP

# ============================================================
# Bridge vmbr1: LAN (to GL.iNet Slate AX)
# ============================================================

auto vmbr1
iface vmbr1 inet static
    address 192.168.10.254/24
    bridge-ports eth-builtin
    bridge-stp off
    bridge-fd 0
    # This bridge connects to GL.iNet Slate AX (192.168.10.1)
    # OPNsense LAN interface connects here

# ============================================================
# Bridge vmbr2: INTERNAL (LXC Containers)
# ============================================================

auto vmbr2
iface vmbr2 inet static
    address 10.0.30.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    # Internal network for LXC containers
    # PostgreSQL, Redis, Nextcloud, etc.

# ============================================================
# Bridge vmbr99: MGMT (Management)
# ============================================================

auto vmbr99
iface vmbr99 inet static
    address 10.0.99.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    # Management network
    # Proxmox web UI accessible here

EOF

echo -e "${GREEN}✓${NC} Network bridges configured in /etc/network/interfaces"

# ============================================================
# Configure DNS servers
# ============================================================

echo ""
echo -e "${BLUE}[5/6]${NC} Configuring DNS servers..."

# Backup resolv.conf
cp /etc/resolv.conf /etc/resolv.conf.bak

# Configure DNS
cat > /etc/resolv.conf <<EOF
# DNS Configuration
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 1.0.0.1
EOF

echo -e "${GREEN}✓${NC} DNS configured (Cloudflare + Google)"

# ============================================================
# Display network configuration
# ============================================================

echo ""
echo -e "${BLUE}[6/6]${NC} Network configuration summary..."
echo ""
echo -e "${GREEN}Network Bridges:${NC}"
echo "  vmbr0: WAN (DHCP) - USB Ethernet to ISP"
echo "  vmbr1: LAN (192.168.10.254/24) - Built-in Ethernet to GL.iNet"
echo "  vmbr2: INTERNAL (10.0.30.1/24) - LXC Containers"
echo "  vmbr99: MGMT (10.0.99.1/24) - Management"
echo ""
echo -e "${YELLOW}⚠ IMPORTANT:${NC}"
echo "  Network changes require system reboot to apply fully"
echo "  After reboot:"
echo "    - UDEV rules will rename interfaces"
echo "    - Network bridges will be created"
echo "    - You can access Proxmox at: https://10.0.99.1:8006"
echo ""

# ============================================================
# Apply network configuration (optional)
# ============================================================

echo -e "${YELLOW}Apply network configuration now? (requires network restart)${NC}"
echo "Type 'yes' to apply, anything else to skip:"
read -r response

if [ "$response" == "yes" ]; then
    echo ""
    echo -e "${BLUE}Applying network configuration...${NC}"

    # Restart networking
    systemctl restart networking

    echo -e "${GREEN}✓${NC} Network configuration applied"
    echo ""
    echo "Current bridges:"
    ip -br link show type bridge
else
    echo ""
    echo -e "${YELLOW}⚠${NC} Network configuration saved but not applied"
    echo "   Run 'systemctl restart networking' or reboot to apply"
fi

echo ""
echo -e "${GREEN}✓ Network configuration complete!${NC}"
echo ""
echo "Next: Run ./05-init-git-repo.sh"
