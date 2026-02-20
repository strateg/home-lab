#!/bin/sh
# OpenWRT Mode Switcher
# Automatically switches between HOME and TRAVEL modes
# Place in: /usr/bin/openwrt-mode-switcher.sh
# Make executable: chmod +x /usr/bin/openwrt-mode-switcher.sh

MODE_FILE="/etc/openwrt-mode"
HOME_GATEWAY="192.168.10.1"
OPNSENSE_CHECK="10.0.99.10"
LOG_TAG="mode-switcher"

# Backup directories
HOME_CONFIGS="/etc/openwrt-configs/home"
TRAVEL_CONFIGS="/etc/openwrt-configs/travel"

# Function to detect current location
detect_mode() {
    logger -t "$LOG_TAG" "Detecting network environment..."

    # Try to ping OPNsense on LAN interface
    if ping -c 2 -W 2 -I eth0 "$HOME_GATEWAY" > /dev/null 2>&1; then
        echo "home"
        return 0
    else
        echo "travel"
        return 1
    fi
}

# Function to switch to HOME mode
switch_to_home() {
    logger -t "$LOG_TAG" "Switching to HOME mode..."

    # Stop WireGuard
    /etc/init.d/wireguard stop 2>/dev/null

    # Copy HOME configurations
    cp "$HOME_CONFIGS/network" /etc/config/network
    cp "$HOME_CONFIGS/wireless" /etc/config/wireless
    cp "$HOME_CONFIGS/dhcp" /etc/config/dhcp
    cp "$HOME_CONFIGS/firewall" /etc/config/firewall

    # Restart services
    /etc/init.d/network restart
    sleep 5
    /etc/init.d/firewall restart
    /etc/init.d/dnsmasq restart
    wifi reload

    # Start AdGuard if not running
    /etc/init.d/AdGuardHome start 2>/dev/null

    echo "home" > "$MODE_FILE"
    logger -t "$LOG_TAG" "Switched to HOME mode successfully"
}

# Function to switch to TRAVEL mode
switch_to_travel() {
    logger -t "$LOG_TAG" "Switching to TRAVEL mode..."

    # Copy TRAVEL configurations
    cp "$TRAVEL_CONFIGS/network" /etc/config/network
    cp "$TRAVEL_CONFIGS/wireless" /etc/config/wireless
    cp "$TRAVEL_CONFIGS/dhcp" /etc/config/dhcp
    cp "$TRAVEL_CONFIGS/firewall" /etc/config/firewall

    # Restart services
    /etc/init.d/network restart
    sleep 5
    /etc/init.d/firewall restart
    /etc/init.d/dnsmasq restart
    wifi reload

    # Wait for network to stabilize
    sleep 10

    # Start WireGuard
    /etc/init.d/wireguard start

    echo "travel" > "$MODE_FILE"
    logger -t "$LOG_TAG" "Switched to TRAVEL mode successfully"
}

# Function to check WireGuard connectivity
check_vpn() {
    # Check if home is reachable through VPN
    if ping -c 2 -W 3 -I wg-home "$OPNSENSE_CHECK" > /dev/null 2>&1; then
        logger -t "$LOG_TAG" "VPN to home is UP"
        return 0
    elif ping -c 2 -W 3 -I wg-oracle "$OPNSENSE_CHECK" > /dev/null 2>&1; then
        logger -t "$LOG_TAG" "VPN to Oracle is UP (failover)"
        return 0
    else
        logger -t "$LOG_TAG" "WARNING: VPN is DOWN!"
        return 1
    fi
}

# Main logic
main() {
    CURRENT_MODE=$(cat "$MODE_FILE" 2>/dev/null || echo "unknown")
    DETECTED_MODE=$(detect_mode)

    logger -t "$LOG_TAG" "Current mode: $CURRENT_MODE, Detected: $DETECTED_MODE"

    # If mode changed, switch
    if [ "$CURRENT_MODE" != "$DETECTED_MODE" ]; then
        logger -t "$LOG_TAG" "Mode change detected!"

        case "$DETECTED_MODE" in
            "home")
                switch_to_home
                ;;
            "travel")
                switch_to_travel
                # Wait and check VPN
                sleep 15
                if ! check_vpn; then
                    logger -t "$LOG_TAG" "ERROR: Failed to establish VPN connection"
                fi
                ;;
        esac
    else
        logger -t "$LOG_TAG" "Mode unchanged: $CURRENT_MODE"

        # If in travel mode, check VPN health
        if [ "$CURRENT_MODE" = "travel" ]; then
            check_vpn
        fi
    fi
}

# Run main function
main "$@"
