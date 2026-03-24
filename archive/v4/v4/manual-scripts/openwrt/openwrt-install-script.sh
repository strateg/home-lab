#!/bin/sh
# OpenWRT Setup Script
# Installs and configures all necessary packages and scripts
# Run on OpenWRT: sh openwrt-install-script.sh

set -e

echo "=== OpenWRT Network Configuration Setup ==="
echo ""

# Update package lists
echo "[1/8] Updating package lists..."
opkg update

# Install required packages
echo "[2/8] Installing required packages..."
opkg install \
    luci-ssl \
    luci-app-wireguard \
    wireguard-tools \
    kmod-wireguard \
    luci-app-adblock \
    adguardhome \
    luci-theme-material \
    luci-app-statistics \
    luci-app-nlbwmon \
    ip-full \
    ipset \
    iptables-mod-ipopt \
    iptables-mod-conntrack-extra

# Create config directories
echo "[3/8] Creating configuration directories..."
mkdir -p /etc/openwrt-configs/home
mkdir -p /etc/openwrt-configs/travel
mkdir -p /usr/lib/openwrt-scripts

# Install mode switcher script
echo "[4/8] Installing mode switcher..."
cat > /usr/bin/openwrt-mode-switcher.sh <<'SWITCHER_EOF'
# Content from openwrt-mode-switcher.sh
# (Copy the content here or download from your config files)
SWITCHER_EOF
chmod +x /usr/bin/openwrt-mode-switcher.sh

# Install init script
echo "[5/8] Installing init script..."
cat > /etc/init.d/mode-detector <<'INIT_EOF'
# Content from openwrt-init-mode-detector
# (Copy the content here)
INIT_EOF
chmod +x /etc/init.d/mode-detector

# Install VPN failover script
echo "[6/8] Installing VPN failover script..."
cat > /usr/bin/openwrt-vpn-failover.sh <<'FAILOVER_EOF'
# Content from openwrt-vpn-failover.sh
FAILOVER_EOF
chmod +x /usr/bin/openwrt-vpn-failover.sh

# Add cron job for VPN failover
echo "[7/8] Setting up cron jobs..."
cat >> /etc/crontabs/root <<'CRON_EOF'
# VPN failover check every minute
* * * * * /usr/bin/openwrt-vpn-failover.sh

# Mode detection every 5 minutes
*/5 * * * * /usr/bin/openwrt-mode-switcher.sh
CRON_EOF
/etc/init.d/cron restart

# Enable services
echo "[8/8] Enabling services..."
/etc/init.d/mode-detector enable
/etc/init.d/AdGuardHome enable

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Copy your home mode configs to /etc/openwrt-configs/home/"
echo "2. Copy your travel mode configs to /etc/openwrt-configs/travel/"
echo "3. Generate WireGuard keys: wg genkey | tee privatekey | wg pubkey > publickey"
echo "4. Configure AdGuard Home at http://192.168.20.1:3000"
echo "5. Reboot: reboot"
echo ""
