#!/bin/bash
# =============================================================================
# Phase 0: MikroTik Bootstrap Postcheck (ADR 0057)
# =============================================================================

set -euo pipefail

MGMT_IP="${1:-}"
TERRAFORM_USER="${2:-}"
TERRAFORM_PASSWORD="${3:-}"
TERRAFORM_PASSWORD_FILE="${MIKROTIK_TERRAFORM_PASSWORD_FILE:-}"
API_PORT="${API_PORT:-8443}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

fail() {
    echo -e "${RED}ERROR: $*${NC}"
    exit 1
}

if [ -z "$MGMT_IP" ] || [ -z "$TERRAFORM_USER" ]; then
    fail "Usage: $0 <mgmt_ip> <terraform_user> [terraform_password]"
fi

if [ -z "$TERRAFORM_PASSWORD" ]; then
    if [ -n "$TERRAFORM_PASSWORD_FILE" ] && [ -f "$TERRAFORM_PASSWORD_FILE" ]; then
        TERRAFORM_PASSWORD="$(head -n1 "$TERRAFORM_PASSWORD_FILE" | tr -d '\r\n')"
    else
        fail "Terraform password not provided. Set MIKROTIK_TERRAFORM_PASSWORD or MIKROTIK_TERRAFORM_PASSWORD_FILE"
    fi
fi

if [ -z "$TERRAFORM_PASSWORD" ]; then
    fail "Terraform password is empty"
fi

if ! command -v curl >/dev/null 2>&1; then
    fail "curl is required for API postcheck"
fi

echo -e "${YELLOW}Postcheck:${NC} verifying reachability and API auth"

if command -v ping >/dev/null 2>&1; then
    if ping -c 1 "$MGMT_IP" >/dev/null 2>&1 || ping -n 1 "$MGMT_IP" >/dev/null 2>&1; then
        echo "  ping: OK ($MGMT_IP)"
    else
        echo -e "${YELLOW}WARN: ping check failed for $MGMT_IP, continuing with API probe${NC}"
    fi
fi

NETRC_FILE="$(mktemp)"
cleanup() {
    rm -f "$NETRC_FILE"
}
trap cleanup EXIT
chmod 600 "$NETRC_FILE"
cat >"$NETRC_FILE" <<EOF
machine $MGMT_IP
login $TERRAFORM_USER
password $TERRAFORM_PASSWORD
EOF

HTTP_CODE="$(curl -k -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 5 \
    --netrc-file "$NETRC_FILE" \
    "https://${MGMT_IP}:${API_PORT}/rest/system/identity" || true)"

if [ "$HTTP_CODE" != "200" ]; then
    fail "RouterOS API auth check failed (HTTP ${HTTP_CODE:-<empty>}) at https://${MGMT_IP}:${API_PORT}/rest/system/identity"
fi

echo -e "${GREEN}Postcheck OK:${NC} RouterOS API is reachable and Terraform credentials are valid"
