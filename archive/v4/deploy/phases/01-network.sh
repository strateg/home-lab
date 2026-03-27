#!/bin/bash
# =============================================================================
# Phase 1: Network Deployment (MikroTik)
# =============================================================================
# This script applies MikroTik Terraform configuration
# Deploys: VLANs, Firewall, DHCP, DNS, VPN, Containers
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_MODE="${DEPLOY_MODE:-native}"
DIST_ROOT="$PROJECT_DIR/v4-dist"
DIST_PACKAGE_ID="control/terraform/mikrotik"
DIST_CHECKER="$PROJECT_DIR/v4/topology-tools/check-dist-package.py"

case "$DEPLOY_MODE" in
    native)
        TERRAFORM_DIR="$PROJECT_DIR/.work/native/terraform/mikrotik"
        ;;
    dist)
        TERRAFORM_DIR="$DIST_ROOT/$DIST_PACKAGE_ID"
        ;;
    *)
        echo "ERROR Unsupported DEPLOY_MODE: $DEPLOY_MODE"
        echo "      Expected: native or dist"
        exit 1
        ;;
esac

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                PHASE 1: NETWORK DEPLOYMENT (MikroTik)                ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "Execution mode: $DEPLOY_MODE"
echo "Terraform root: $TERRAFORM_DIR"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if [ "$DEPLOY_MODE" = "dist" ]; then
    if ! python3 "$DIST_CHECKER" "$DIST_PACKAGE_ID"; then
        echo "   Assemble packages first: cd deploy && make assemble-dist"
        exit 1
    fi
else
    python3 "$PROJECT_DIR/v4/topology-tools/assemble-native.py" --target mikrotik --quiet
fi

if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
    echo -e "${RED}❌ terraform.tfvars not found!${NC}"
    if [ "$DEPLOY_MODE" = "dist" ]; then
        echo "   Create local/terraform/mikrotik/terraform.tfvars and run:"
        echo "   cd deploy && make materialize-dist-inputs"
    else
        echo "   Create local/terraform/mikrotik/terraform.tfvars and run:"
        echo "   cd deploy && make assemble-native"
    fi
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform not installed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites check passed${NC}"
echo ""

# Backup current MikroTik configuration
echo -e "${YELLOW}Creating MikroTik configuration backup...${NC}"

BACKUP_DIR="$PROJECT_DIR/backups/mikrotik"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S).rsc"

# Try to backup via SSH (optional, may fail if not configured)
if ssh -o ConnectTimeout=5 -o BatchMode=yes admin@192.168.88.1 "/export" > "$BACKUP_FILE" 2>/dev/null; then
    echo -e "${GREEN}✓ Backup saved to: $BACKUP_FILE${NC}"
else
    echo -e "${YELLOW}⚠️  Could not backup via SSH (continuing anyway)${NC}"
    echo "   Manual backup recommended: /export file=pre-terraform"
fi
echo ""

# Initialize Terraform
echo -e "${YELLOW}Initializing Terraform...${NC}"
cd "$TERRAFORM_DIR"
terraform init -upgrade

echo ""

# Show plan
echo -e "${YELLOW}Planning changes...${NC}"
terraform plan -out=tfplan

echo ""
echo -e "${CYAN}───────────────────────────────────────────────────────────────────────${NC}"
echo ""

# Confirm apply
echo -e "${RED}⚠️  WARNING: This will modify your MikroTik router configuration!${NC}"
echo ""
echo "Resources to be created/modified:"
echo "  - Bridge and VLAN interfaces"
echo "  - IP addresses"
echo "  - DHCP servers"
echo "  - DNS settings"
echo "  - Firewall rules"
echo "  - QoS queues"
echo "  - WireGuard VPN"
echo "  - Containers (AdGuard, Tailscale)"
echo ""
read -p "Apply these changes? [y/N] " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Deployment cancelled."
    exit 0
fi

# Apply configuration
echo ""
echo -e "${YELLOW}Applying MikroTik configuration...${NC}"
terraform apply tfplan

echo ""
echo -e "${GREEN}✅ Phase 1 (Network) completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  - Verify network connectivity"
echo "  - Check VLANs and routing"
echo "  - Run: DEPLOY_MODE=$DEPLOY_MODE ./phases/02-compute.sh"

# Cleanup plan file
rm -f tfplan
