#!/bin/bash
# =============================================================================
# Phase 3: Services Configuration (Ansible)
# =============================================================================
# This script runs Ansible playbooks to configure services
# Configures: PostgreSQL, Redis, Docker services on Orange Pi 5
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ANSIBLE_DIR="$PROJECT_DIR/ansible"
ANSIBLE_ENV="production"
GENERATED_ANSIBLE_DIR="$PROJECT_DIR/generated/ansible"
GENERATED_INVENTORY_DIR="$GENERATED_ANSIBLE_DIR/inventory/$ANSIBLE_ENV"
RUNTIME_INVENTORY_DIR="$PROJECT_DIR/generated/ansible/runtime/production"
ASSEMBLER_SCRIPT="$PROJECT_DIR/topology-tools/assemble-ansible-runtime.py"

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            echo "Usage: $0"
            echo ""
            echo "Uses assembled runtime inventory:"
            echo "  generated/ansible/runtime/production"
            echo ""
            echo "If runtime inventory is missing, the script assembles it from:"
            echo "  - generated/ansible/inventory/$ANSIBLE_ENV"
            echo "  - ansible/inventory-overrides/production"
            exit 0
            ;;
    esac
done

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║              PHASE 3: SERVICES CONFIGURATION (Ansible)               ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v ansible-playbook &> /dev/null; then
    echo -e "${RED}❌ Ansible not installed!${NC}"
    exit 1
fi

if [ ! -d "$ANSIBLE_DIR" ]; then
    echo -e "${RED}❌ Ansible directory not found: $ANSIBLE_DIR${NC}"
    exit 1
fi

# Check runtime inventory exists or assemble it
INVENTORY="$RUNTIME_INVENTORY_DIR"
if [ ! -f "$INVENTORY/hosts.yml" ]; then
    echo -e "${YELLOW}Runtime inventory not found, assembling it now...${NC}"

    if [ ! -f "$GENERATED_INVENTORY_DIR/hosts.yml" ]; then
        echo -e "${RED}❌ Generated inventory not found: $GENERATED_INVENTORY_DIR/hosts.yml${NC}"
        echo "   Generate inventory first:"
        echo "   python3 topology-tools/regenerate-all.py"
        exit 1
    fi

    if ! python3 "$ASSEMBLER_SCRIPT"; then
        echo -e "${RED}❌ Failed to assemble runtime inventory${NC}"
        exit 1
    fi
fi

if [ ! -f "$INVENTORY/hosts.yml" ]; then
    echo -e "${RED}❌ No runtime inventory found!${NC}"
    echo "   Run: python3 topology-tools/regenerate-all.py"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites check passed${NC}"
echo ""

cd "$ANSIBLE_DIR"

# Test connectivity
echo -e "${YELLOW}Testing Ansible connectivity...${NC}"
if ansible all -i "$INVENTORY" -m ping --one-line 2>/dev/null; then
    echo -e "${GREEN}✓ All hosts reachable${NC}"
else
    echo -e "${YELLOW}⚠️  Some hosts may not be reachable (continuing anyway)${NC}"
fi
echo ""

# Show what will be configured
echo -e "${YELLOW}Services to be configured:${NC}"
echo "  - Common configuration (all hosts)"
echo "  - PostgreSQL (Proxmox LXC)"
echo "  - Redis (Proxmox LXC)"
echo "  - Docker services (Orange Pi 5)"
echo "    - Nextcloud"
echo "    - Jellyfin"
echo "    - Prometheus/Grafana/Loki"
echo ""

read -p "Run Ansible playbooks? [y/N] " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Configuration cancelled."
    exit 0
fi

echo ""

# Run playbooks in order
echo -e "${YELLOW}Running Ansible playbooks...${NC}"
echo ""

# Common configuration
echo -e "${CYAN}[1/4] Common configuration...${NC}"
ansible-playbook -i "$INVENTORY" playbooks/common.yml || {
    echo -e "${RED}❌ Common playbook failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Common configuration complete${NC}"
echo ""

# PostgreSQL
echo -e "${CYAN}[2/4] PostgreSQL configuration...${NC}"
ansible-playbook -i "$INVENTORY" playbooks/postgresql.yml || {
    echo -e "${RED}❌ PostgreSQL playbook failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ PostgreSQL configuration complete${NC}"
echo ""

# Redis
echo -e "${CYAN}[3/4] Redis configuration...${NC}"
ansible-playbook -i "$INVENTORY" playbooks/redis.yml || {
    echo -e "${RED}❌ Redis playbook failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Redis configuration complete${NC}"
echo ""

# Orange Pi 5 Docker services (if playbook exists)
if [ -f "playbooks/orangepi5.yml" ]; then
    echo -e "${CYAN}[4/4] Orange Pi 5 Docker services...${NC}"
    ansible-playbook -i "$INVENTORY" playbooks/orangepi5.yml || {
        echo -e "${YELLOW}⚠️  Orange Pi 5 playbook had issues (continuing)${NC}"
    }
    echo -e "${GREEN}✓ Orange Pi 5 configuration complete${NC}"
else
    echo -e "${YELLOW}[4/4] Skipping Orange Pi 5 (playbook not found)${NC}"
fi

echo ""
echo -e "${GREEN}✅ Phase 3 (Services) completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  - Run: ./phases/04-verify.sh"
echo "  - Or manually verify services"
