#!/bin/bash
# Deploy PostgreSQL Service from Template
# Architecture: Internal Network (10.0.30.0/24)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common-functions.sh"

# Configuration
TEMPLATE_ID=900
SERVICE_NAME="postgresql"
DEFAULT_CTID=200
DEFAULT_HOSTNAME="postgresql-db"
DEFAULT_IP="10.0.30.10"
ROOT_PASSWORD="Homelab2025!"
STORAGE="local-lvm"  # Production on SSD

main() {
    print_banner "PostgreSQL Service Deployment"

    check_proxmox
    check_root

    # Check if template exists
    if ! template_exists $TEMPLATE_ID; then
        echo -e "${RED}Error: Template ${TEMPLATE_ID} does not exist${NC}"
        echo ""
        echo "Create template first:"
        echo "  bash proxmox/scripts/templates/create-postgresql-template.sh"
        echo ""
        exit 1
    fi

    # Get configuration from user or use defaults
    read -p "Container ID [${DEFAULT_CTID}]: " CTID
    CTID=${CTID:-$DEFAULT_CTID}

    read -p "Hostname [${DEFAULT_HOSTNAME}]: " HOSTNAME
    HOSTNAME=${HOSTNAME:-$DEFAULT_HOSTNAME}

    read -p "IP Address [${DEFAULT_IP}]: " IP_ADDRESS
    IP_ADDRESS=${IP_ADDRESS:-$DEFAULT_IP}

    read -p "Storage [${STORAGE}]: " STORAGE_INPUT
    STORAGE=${STORAGE_INPUT:-$STORAGE}

    echo ""
    echo "Deployment Configuration:"
    echo "  Template ID: ${TEMPLATE_ID}"
    echo "  Container ID: ${CTID}"
    echo "  Hostname: ${HOSTNAME}"
    echo "  IP Address: ${IP_ADDRESS}"
    echo "  Storage: ${STORAGE}"
    echo "  Network: ${INTERNAL_NETWORK}"
    echo "  Gateway: ${INTERNAL_GATEWAY}"
    echo "  DNS: ${DNS_SERVER}"
    echo ""

    read -p "Deploy service? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled"
        exit 0
    fi

    # Clone template
    print_section "Cloning Template"
    if ! clone_template "$TEMPLATE_ID" "$CTID" "$HOSTNAME" "$IP_ADDRESS" "$STORAGE"; then
        exit 1
    fi

    # Start container
    print_section "Starting Container"
    if ! start_container "$CTID" 30; then
        exit 1
    fi

    # Wait for network
    wait_for_network "$CTID" 60

    # Change root password
    print_section "Configuring Container"
    change_root_password "$CTID" "$ROOT_PASSWORD"

    # PostgreSQL specific configuration
    echo "Configuring PostgreSQL..."

    # Allow remote connections (optional)
    exec_in_container $CTID "echo \"host all all 10.0.30.0/24 md5\" >> /etc/postgresql/*/main/pg_hba.conf"
    exec_in_container $CTID "echo \"listen_addresses = '*'\" >> /etc/postgresql/*/main/postgresql.conf"

    # Restart PostgreSQL
    exec_in_container $CTID "systemctl restart postgresql"

    # Display info
    print_section "Deployment Complete"
    show_container_info "$CTID"

    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  PostgreSQL Service Deployed Successfully!       ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Access Information:"
    echo "  SSH: ssh root@${IP_ADDRESS}"
    echo "  Password: ${ROOT_PASSWORD}"
    echo "  PostgreSQL: psql -h ${IP_ADDRESS} -U postgres"
    echo ""
    echo "Next steps:"
    echo "  1. Create database:"
    echo "     pct exec ${CTID} -- su - postgres -c 'createdb mydb'"
    echo ""
    echo "  2. Create user:"
    echo "     pct exec ${CTID} -- su - postgres -c \"psql -c \\\"CREATE USER myuser WITH PASSWORD 'mypass';\\\"\""
    echo ""
    echo "  3. Connect from app:"
    echo "     postgresql://${IP_ADDRESS}:5432/mydb"
    echo ""
}

main "$@"
