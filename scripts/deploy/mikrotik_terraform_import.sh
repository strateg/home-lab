#!/bin/bash
# MikroTik Terraform Import Script
# Automatically imports existing MikroTik resources into Terraform state
# This ensures idempotent deployments without deleting existing configs
#
# Usage: ./mikrotik_terraform_import.sh [ROUTER_IP] [USERNAME] [PASSWORD]
#
# Requirements:
# - ssh access to router
# - terraform initialized in generated/home-lab/terraform/mikrotik/

set -euo pipefail

ROUTER_IP="${1:-192.168.0.17}"
USERNAME="${2:-automator}"
PASSWORD="${3:-}"
TF_DIR="${TF_DIR:-generated/home-lab/terraform/mikrotik}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# SSH command wrapper
ssh_cmd() {
    if [[ -n "$PASSWORD" ]]; then
        sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$USERNAME@$ROUTER_IP" "$1" 2>/dev/null
    else
        ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$USERNAME@$ROUTER_IP" "$1" 2>/dev/null
    fi
}

# Get MikroTik internal ID for a resource
get_mikrotik_id() {
    local resource_type="$1"
    local name_field="$2"
    local name_value="$3"

    local result
    result=$(ssh_cmd "$resource_type print where $name_field=\"$name_value\" proplist=.id" | grep -oE '\*[0-9A-Fa-f]+' | head -1)
    echo "$result"
}

# Import a resource if it exists on MikroTik but not in Terraform state
import_if_exists() {
    local tf_resource="$1"
    local mikrotik_type="$2"
    local name_field="$3"
    local name_value="$4"

    # Check if already in Terraform state
    if terraform -chdir="$TF_DIR" state show "$tf_resource" &>/dev/null; then
        log_info "Already in state: $tf_resource"
        return 0
    fi

    # Get MikroTik internal ID
    local mk_id
    mk_id=$(get_mikrotik_id "$mikrotik_type" "$name_field" "$name_value")

    if [[ -n "$mk_id" ]]; then
        log_info "Importing $tf_resource (MikroTik ID: $mk_id)"
        terraform -chdir="$TF_DIR" import "$tf_resource" "$mk_id" || {
            log_warn "Failed to import $tf_resource - may not exist or different schema"
        }
    else
        log_info "Not found on router: $name_value"
    fi
}

# Main
log_info "Starting MikroTik Terraform import..."
log_info "Router: $ROUTER_IP, User: $USERNAME"
log_info "Terraform dir: $TF_DIR"

# Test connection
if ! ssh_cmd "/system identity print" | grep -q "name:"; then
    log_error "Cannot connect to router at $ROUTER_IP"
    exit 1
fi

cd "$(dirname "$0")/../.."

# Initialize terraform if needed
if [[ ! -d "$TF_DIR/.terraform" ]]; then
    log_info "Initializing Terraform..."
    terraform -chdir="$TF_DIR" init
fi

# Import IP pools
log_info "=== Importing IP Pools ==="
for pool in vpn_germany_pool guest_pool iot_pool; do
    import_if_exists "routeros_ip_pool.${pool}" "/ip pool" "name" "$pool"
done

# Import DHCP servers
log_info "=== Importing DHCP Servers ==="
for server in vpn_germany_dhcp guest_dhcp iot_dhcp; do
    import_if_exists "routeros_ip_dhcp_server.${server}" "/ip dhcp-server" "name" "$server"
done

# Import VLANs
log_info "=== Importing VLANs ==="
for vlan in vlan40 vlan30 vlan55; do
    # Extract name without 'vlan' prefix for terraform resource name
    tf_name="${vlan#vlan}"
    case "$tf_name" in
        40) tf_name="iot" ;;
        30) tf_name="guest" ;;
        55) tf_name="vpn_germany" ;;
    esac
    import_if_exists "routeros_interface_vlan.${tf_name}" "/interface vlan" "name" "$vlan"
done

# Import IP addresses
log_info "=== Importing IP Addresses ==="
# Get addresses with "managed by topology" comment
addresses=$(ssh_cmd "/ip address print where comment~\"managed by topology\" proplist=address,.id" 2>/dev/null || true)
if [[ -n "$addresses" ]]; then
    log_info "Found topology-managed addresses, manual import may be needed"
fi

log_info "=== Import Complete ==="
log_info "Run 'terraform -chdir=$TF_DIR plan' to verify state"
