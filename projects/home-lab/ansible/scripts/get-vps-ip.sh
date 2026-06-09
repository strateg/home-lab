#!/bin/bash
# Get VPS Oracle Frankfurt public IP dynamically
#
# Usage:
#   export VPS_ORACLE_FRANKFURT_IP=$(./scripts/get-vps-ip.sh)
#
# Methods (in order of preference):
#   1. OCI CLI - queries instance VNIC for public IP
#   2. DNS lookup - if DDNS is configured
#   3. Manual - prompts user to enter IP
#
# RULE: Never store public IP statically - it can change on VPS restart

set -e

INSTANCE_ID="ocid1.instance.oc1.eu-frankfurt-1.antheljtktcemiacour3ugube5pczalr6qmrumzhp43n47bkgsix3ahtr7da"
COMPARTMENT_ID="ocid1.tenancy.oc1..aaaaaaaaxkhwya4e3e3haawi5mbhlyj7q3mds624qmvhvd4aqzze3gxwtj3q"

# Method 1: Try OCI CLI
if command -v oci &> /dev/null; then
    # Get VNIC attachments for the instance
    VNIC_ID=$(oci compute vnic-attachment list \
        --instance-id "$INSTANCE_ID" \
        --compartment-id "$COMPARTMENT_ID" \
        --query 'data[0]."vnic-id"' \
        --raw-output 2>/dev/null) || true

    if [ -n "$VNIC_ID" ] && [ "$VNIC_ID" != "null" ]; then
        PUBLIC_IP=$(oci network vnic get \
            --vnic-id "$VNIC_ID" \
            --query 'data."public-ip"' \
            --raw-output 2>/dev/null) || true

        if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "null" ]; then
            echo "$PUBLIC_IP"
            exit 0
        fi
    fi
fi

# Method 2: Try SSH through WireGuard tunnel (if connected)
# The VPS is accessible at 10.100.0.2 through WireGuard
if ping -c 1 -W 2 10.100.0.2 &>/dev/null; then
    # Query the VPS for its own public IP
    PUBLIC_IP=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        ubuntu@10.100.0.2 "curl -s ifconfig.me" 2>/dev/null) || true

    if [ -n "$PUBLIC_IP" ]; then
        echo "$PUBLIC_IP"
        exit 0
    fi
fi

# Method 3: Check environment variable (may be set by caller)
if [ -n "$VPS_ORACLE_FRANKFURT_IP" ]; then
    echo "$VPS_ORACLE_FRANKFURT_IP"
    exit 0
fi

# Method 4: Prompt user
>&2 echo "Could not auto-discover VPS IP."
>&2 echo "Enter VPS Oracle Frankfurt public IP: "
read -r PUBLIC_IP
echo "$PUBLIC_IP"
