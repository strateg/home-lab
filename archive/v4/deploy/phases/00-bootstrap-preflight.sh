#!/bin/bash
# =============================================================================
# Phase 0: MikroTik Netinstall Preflight (ADR 0057)
# =============================================================================

set -euo pipefail

RESTORE_PATH="${1:-}"
BOOTSTRAP_SCRIPT="${2:-}"
NETINSTALL_IFACE="${3:-}"
NETINSTALL_CLIENT_IP="${4:-}"
ROUTEROS_PACKAGE="${5:-}"
ROUTEROS_PACKAGE_SHA256="${6:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

fail() {
    echo -e "${RED}ERROR: $*${NC}"
    exit 1
}

if [ -z "$RESTORE_PATH" ] || [ -z "$BOOTSTRAP_SCRIPT" ] || [ -z "$NETINSTALL_IFACE" ] || [ -z "$NETINSTALL_CLIENT_IP" ] || [ -z "$ROUTEROS_PACKAGE" ]; then
    fail "Usage: $0 <restore_path> <bootstrap_script> <netinstall_iface> <netinstall_client_ip> <routeros_package> [routeros_package_sha256]"
fi

case "$RESTORE_PATH" in
    minimal|backup|rsc)
        ;;
    *)
        fail "Unsupported RESTORE_PATH='$RESTORE_PATH' (expected: minimal, backup, or rsc)"
        ;;
esac

if ! command -v netinstall-cli >/dev/null 2>&1; then
    fail "netinstall-cli not found in PATH"
fi

if [ ! -f "$BOOTSTRAP_SCRIPT" ]; then
    fail "Bootstrap script not found: $BOOTSTRAP_SCRIPT"
fi

if [ ! -f "$ROUTEROS_PACKAGE" ]; then
    fail "RouterOS package not found: $ROUTEROS_PACKAGE"
fi

if ! echo "$NETINSTALL_CLIENT_IP" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    fail "Invalid IPv4 address format for netinstall client IP: $NETINSTALL_CLIENT_IP"
fi

if command -v ip >/dev/null 2>&1; then
    if ! ip link show "$NETINSTALL_IFACE" >/dev/null 2>&1; then
        fail "Network interface not found: $NETINSTALL_IFACE"
    fi
    if ! ip -4 addr show "$NETINSTALL_IFACE" | grep -Eq "(^| )${NETINSTALL_CLIENT_IP}/"; then
        fail "Netinstall client IP $NETINSTALL_CLIENT_IP is not configured on interface $NETINSTALL_IFACE"
    fi
else
    echo -e "${YELLOW}WARN: 'ip' command not found, skipping interface existence check${NC}"
fi

if [ -n "$ROUTEROS_PACKAGE_SHA256" ]; then
    if ! echo "$ROUTEROS_PACKAGE_SHA256" | grep -Eq '^[A-Fa-f0-9]{64}$'; then
        fail "Invalid SHA256 format for ROUTEROS_PACKAGE_SHA256 (expected 64 hex chars)"
    fi

    expected_sha="$(echo "$ROUTEROS_PACKAGE_SHA256" | tr '[:upper:]' '[:lower:]')"
    computed_sha=""

    if command -v sha256sum >/dev/null 2>&1; then
        computed_sha="$(sha256sum "$ROUTEROS_PACKAGE" | awk '{print $1}' | tr '[:upper:]' '[:lower:]')"
    elif command -v shasum >/dev/null 2>&1; then
        computed_sha="$(shasum -a 256 "$ROUTEROS_PACKAGE" | awk '{print $1}' | tr '[:upper:]' '[:lower:]')"
    else
        fail "ROUTEROS_PACKAGE_SHA256 is set but no sha256 tool found (sha256sum/shasum)"
    fi

    if [ "$computed_sha" != "$expected_sha" ]; then
        fail "RouterOS package checksum mismatch: expected $expected_sha, got $computed_sha"
    fi
fi

echo -e "${GREEN}Preflight OK:${NC}"
echo "  restore path    : $RESTORE_PATH"
echo "  bootstrap script: $BOOTSTRAP_SCRIPT"
echo "  install iface   : $NETINSTALL_IFACE"
echo "  client IP       : $NETINSTALL_CLIENT_IP"
echo "  RouterOS package: $ROUTEROS_PACKAGE"
if [ -n "$ROUTEROS_PACKAGE_SHA256" ]; then
    echo "  package sha256  : $ROUTEROS_PACKAGE_SHA256"
fi
