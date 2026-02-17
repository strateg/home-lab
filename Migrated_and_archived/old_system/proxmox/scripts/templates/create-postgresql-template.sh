#!/bin/bash
# Create PostgreSQL LXC Template
# Uses Proxmox VE Community Scripts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common-functions.sh"

# Configuration
TEMPLATE_ID=900
TEMPLATE_NAME="postgresql-template"
COMMUNITY_SCRIPT="postgresql"
DESCRIPTION="PostgreSQL Database Server Template
Created: $(date +%Y-%m-%d)
Base: Debian 12
Version: PostgreSQL 16
Network: DHCP (configure on clone)
Storage: ${TEMPLATE_STORAGE}"

main() {
    print_banner "PostgreSQL Template Creator"

    check_proxmox
    check_root

    echo "Configuration:"
    echo "  Template ID: ${TEMPLATE_ID}"
    echo "  Template Name: ${TEMPLATE_NAME}"
    echo "  Storage: ${TEMPLATE_STORAGE}"
    echo "  Community Script: ${COMMUNITY_SCRIPT}"
    echo ""

    read -p "Create template? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled"
        exit 0
    fi

    # Create template using Community Scripts
    if create_template_from_community \
        "$TEMPLATE_ID" \
        "$COMMUNITY_SCRIPT" \
        "$TEMPLATE_NAME" \
        "$DESCRIPTION"; then

        echo ""
        echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  PostgreSQL Template Created Successfully!       ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
        echo ""
        echo "Template Information:"
        echo "  ID: ${TEMPLATE_ID}"
        echo "  Name: ${TEMPLATE_NAME}"
        echo "  Storage: ${TEMPLATE_STORAGE}"
        echo ""
        echo "Next steps:"
        echo "  1. Deploy service:"
        echo "     bash proxmox/scripts/services/deploy-postgresql.sh"
        echo ""
        echo "  2. Or clone manually:"
        echo "     pct clone ${TEMPLATE_ID} 200 --hostname postgresql-01 --full --storage local-lvm"
        echo ""
    else
        echo -e "${RED}Failed to create template${NC}"
        exit 1
    fi
}

main "$@"
