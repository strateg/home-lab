#!/bin/bash
# =============================================================================
# Phase 2: Compute Deployment (Proxmox)
# =============================================================================
# This script applies Proxmox Terraform configuration
# Deploys: Network bridges, LXC containers (PostgreSQL, Redis)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_MODE="${DEPLOY_MODE:-native}"
DIST_ROOT="$PROJECT_DIR/v4-dist"
DIST_PACKAGE_ID="control/terraform/proxmox"
DIST_CHECKER="$PROJECT_DIR/v4/topology-tools/check-dist-package.py"

case "$DEPLOY_MODE" in
    native)
        TERRAFORM_DIR="$PROJECT_DIR/.work/native/terraform/proxmox"
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
echo "║                PHASE 2: COMPUTE DEPLOYMENT (Proxmox)                 ║"
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
    python3 "$PROJECT_DIR/v4/topology-tools/assemble-native.py" --target proxmox --quiet
fi

if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
    echo -e "${RED}❌ terraform.tfvars not found!${NC}"
    if [ "$DEPLOY_MODE" = "dist" ]; then
        echo "   Create local/terraform/proxmox/terraform.tfvars and run:"
        echo "   cd deploy && make materialize-dist-inputs"
    else
        echo "   Create local/terraform/proxmox/terraform.tfvars and run:"
        echo "   cd deploy && make assemble-native"
    fi
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform not installed!${NC}"
    exit 1
fi

# Check Proxmox connectivity
PROXMOX_IP="192.168.88.2"
if ! ping -c 1 -W 2 "$PROXMOX_IP" &> /dev/null; then
    echo -e "${RED}❌ Cannot reach Proxmox at $PROXMOX_IP${NC}"
    echo "   Ensure Phase 1 (Network) was completed successfully"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites check passed${NC}"
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
echo -e "${YELLOW}Resources to be created/modified:${NC}"
echo "  - Network bridges (vmbr0, vmbr2, vmbr99)"
echo "  - LXC containers (PostgreSQL, Redis)"
echo ""
read -p "Apply these changes? [y/N] " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Deployment cancelled."
    exit 0
fi

# Apply configuration
echo ""
echo -e "${YELLOW}Applying Proxmox configuration...${NC}"
terraform apply tfplan

echo ""
echo -e "${GREEN}✅ Phase 2 (Compute) completed successfully!${NC}"
echo ""
echo "LXC containers created. Waiting for boot..."
sleep 10

# Verify LXC containers are running
echo -e "${YELLOW}Verifying LXC containers...${NC}"
if ssh -o ConnectTimeout=5 root@"$PROXMOX_IP" "pct list" 2>/dev/null; then
    echo -e "${GREEN}✓ LXC containers are running${NC}"
else
    echo -e "${YELLOW}⚠️  Could not verify LXC status (SSH may need configuration)${NC}"
fi

echo ""
echo "Next steps:"
echo "  - Wait for LXC containers to fully boot (~30 seconds)"
echo "  - Run: DEPLOY_MODE=$DEPLOY_MODE ./phases/03-services.sh"

# Cleanup plan file
rm -f tfplan
