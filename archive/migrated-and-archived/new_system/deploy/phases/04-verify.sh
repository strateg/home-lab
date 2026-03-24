#!/bin/bash
# =============================================================================
# Phase 4: Deployment Verification
# =============================================================================
# This script verifies all deployed infrastructure is working correctly
# Checks: Network connectivity, services, databases, VPN
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0
WARNINGS=0

check_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
    ((WARNINGS++))
}

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                  PHASE 4: DEPLOYMENT VERIFICATION                    ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# =============================================================================
# Network Connectivity
# =============================================================================

echo -e "${CYAN}[1/5] Network Connectivity${NC}"
echo "───────────────────────────────────────────────────────────────────────"

# MikroTik
if ping -c 1 -W 2 192.168.88.1 &> /dev/null; then
    check_pass "MikroTik (192.168.88.1) - reachable"
else
    check_fail "MikroTik (192.168.88.1) - not reachable"
fi

# Proxmox
if ping -c 1 -W 2 192.168.88.2 &> /dev/null; then
    check_pass "Proxmox (192.168.88.2) - reachable"
else
    check_fail "Proxmox (192.168.88.2) - not reachable"
fi

# Orange Pi 5
if ping -c 1 -W 2 192.168.88.3 &> /dev/null; then
    check_pass "Orange Pi 5 (192.168.88.3) - reachable"
else
    check_warn "Orange Pi 5 (192.168.88.3) - not reachable (may not be deployed)"
fi

# PostgreSQL LXC
if ping -c 1 -W 2 10.0.30.10 &> /dev/null; then
    check_pass "PostgreSQL LXC (10.0.30.10) - reachable"
else
    check_fail "PostgreSQL LXC (10.0.30.10) - not reachable"
fi

# Redis LXC
if ping -c 1 -W 2 10.0.30.20 &> /dev/null; then
    check_pass "Redis LXC (10.0.30.20) - reachable"
else
    check_fail "Redis LXC (10.0.30.20) - not reachable"
fi

echo ""

# =============================================================================
# Web Services
# =============================================================================

echo -e "${CYAN}[2/5] Web Services${NC}"
echo "───────────────────────────────────────────────────────────────────────"

# MikroTik WebFig
if curl -sk --connect-timeout 5 https://192.168.88.1/ &> /dev/null; then
    check_pass "MikroTik WebFig (HTTPS) - accessible"
else
    check_warn "MikroTik WebFig (HTTPS) - not accessible (check certificate)"
fi

# Proxmox UI
if curl -sk --connect-timeout 5 https://192.168.88.2:8006/ &> /dev/null; then
    check_pass "Proxmox Web UI - accessible"
else
    check_fail "Proxmox Web UI - not accessible"
fi

# AdGuard Home
if curl -s --connect-timeout 5 http://192.168.88.1:3000/ &> /dev/null; then
    check_pass "AdGuard Home - accessible"
else
    check_warn "AdGuard Home - not accessible (container may need time)"
fi

# Jellyfin (if deployed)
if curl -s --connect-timeout 5 http://10.0.30.50:8096/ &> /dev/null; then
    check_pass "Jellyfin - accessible"
else
    check_warn "Jellyfin - not accessible (may not be deployed)"
fi

# Grafana (if deployed)
if curl -s --connect-timeout 5 http://10.0.30.50:3000/ &> /dev/null; then
    check_pass "Grafana - accessible"
else
    check_warn "Grafana - not accessible (may not be deployed)"
fi

echo ""

# =============================================================================
# Database Services
# =============================================================================

echo -e "${CYAN}[3/5] Database Services${NC}"
echo "───────────────────────────────────────────────────────────────────────"

# PostgreSQL port check
if nc -z -w 2 10.0.30.10 5432 2>/dev/null; then
    check_pass "PostgreSQL port 5432 - open"
else
    check_fail "PostgreSQL port 5432 - closed"
fi

# Redis port check
if nc -z -w 2 10.0.30.20 6379 2>/dev/null; then
    check_pass "Redis port 6379 - open"
else
    check_fail "Redis port 6379 - closed"
fi

# Redis ping (if redis-cli available)
if command -v redis-cli &> /dev/null; then
    if redis-cli -h 10.0.30.20 PING 2>/dev/null | grep -q "PONG"; then
        check_pass "Redis PING - responded"
    else
        check_warn "Redis PING - no response"
    fi
fi

echo ""

# =============================================================================
# DNS Resolution
# =============================================================================

echo -e "${CYAN}[4/5] DNS Resolution${NC}"
echo "───────────────────────────────────────────────────────────────────────"

# Test DNS resolution through MikroTik
if nslookup router.home.local 192.168.88.1 &> /dev/null; then
    check_pass "DNS resolution (router.home.local) - working"
else
    check_warn "DNS resolution - not working (AdGuard may need configuration)"
fi

# External DNS
if nslookup google.com 192.168.88.1 &> /dev/null; then
    check_pass "External DNS resolution - working"
else
    check_fail "External DNS resolution - not working"
fi

echo ""

# =============================================================================
# VPN Status
# =============================================================================

echo -e "${CYAN}[5/5] VPN Status${NC}"
echo "───────────────────────────────────────────────────────────────────────"

# WireGuard port
if nc -zu -w 2 192.168.88.1 51820 2>/dev/null; then
    check_pass "WireGuard port 51820 - open"
else
    check_warn "WireGuard port 51820 - closed (may need NAT traversal check)"
fi

# WireGuard interface (if wg command available)
if command -v wg &> /dev/null; then
    if wg show 2>/dev/null | grep -q "interface"; then
        check_pass "WireGuard interface - active"
    else
        check_warn "WireGuard interface - not active locally"
    fi
fi

echo ""

# =============================================================================
# Summary
# =============================================================================

echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Verification Summary:"
echo -e "  ${GREEN}Passed:   $PASSED${NC}"
echo -e "  ${RED}Failed:   $FAILED${NC}"
echo -e "  ${YELLOW}Warnings: $WARNINGS${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ✅ DEPLOYMENT VERIFICATION PASSED                       ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║              ❌ DEPLOYMENT VERIFICATION FAILED                        ║${NC}"
    echo -e "${RED}║              Review errors above and fix issues                       ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
