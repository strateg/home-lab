#!/bin/sh
# OpenWRT VPN Failover Script
# Automatically switches between Home and Oracle VPN
# Place in: /usr/bin/openwrt-vpn-failover.sh
# Run via cron every 1 minute

HOME_VPN="wg-home"
ORACLE_VPN="wg-oracle"
TEST_IP="10.0.99.10"
ROUTE_TABLE="100"
LOG_TAG="vpn-failover"

# Test connectivity through specific interface
test_vpn() {
    local interface=$1
    ping -c 2 -W 2 -I "$interface" "$TEST_IP" > /dev/null 2>&1
    return $?
}

# Set default route through specified VPN
set_default_vpn() {
    local vpn=$1

    logger -t "$LOG_TAG" "Setting default VPN to: $vpn"

    # Remove existing policy routing
    ip rule del from 192.168.100.0/24 table "$ROUTE_TABLE" 2>/dev/null
    ip route flush table "$ROUTE_TABLE" 2>/dev/null

    # Add new policy routing
    case "$vpn" in
        "home")
            ip route add default dev "$HOME_VPN" table "$ROUTE_TABLE"
            ip rule add from 192.168.100.0/24 table "$ROUTE_TABLE" priority 100
            echo "home" > /tmp/active-vpn
            ;;
        "oracle")
            ip route add default dev "$ORACLE_VPN" table "$ROUTE_TABLE"
            ip rule add from 192.168.100.0/24 table "$ROUTE_TABLE" priority 100
            echo "oracle" > /tmp/active-vpn
            ;;
        "direct")
            # Fall back to direct internet (no VPN)
            echo "direct" > /tmp/active-vpn
            logger -t "$LOG_TAG" "WARNING: No VPN available, using direct connection!"
            ;;
    esac

    ip route flush cache
}

# Main failover logic
main() {
    CURRENT_VPN=$(cat /tmp/active-vpn 2>/dev/null || echo "unknown")

    # Test home VPN first (preferred)
    if test_vpn "$HOME_VPN"; then
        if [ "$CURRENT_VPN" != "home" ]; then
            logger -t "$LOG_TAG" "Home VPN is UP, switching from $CURRENT_VPN"
            set_default_vpn "home"
        fi
        return 0
    fi

    # Test Oracle VPN (failover)
    if test_vpn "$ORACLE_VPN"; then
        if [ "$CURRENT_VPN" != "oracle" ]; then
            logger -t "$LOG_TAG" "Home VPN DOWN, failing over to Oracle"
            set_default_vpn "oracle"
        fi
        return 0
    fi

    # Both VPNs are down
    logger -t "$LOG_TAG" "ERROR: Both VPNs are DOWN!"
    if [ "$CURRENT_VPN" != "direct" ]; then
        set_default_vpn "direct"
    fi

    return 1
}

main "$@"
