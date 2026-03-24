#!/bin/bash
# Deploy Redis Service from Template

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common-functions.sh"

TEMPLATE_ID=901
DEFAULT_CTID=201
DEFAULT_HOSTNAME="redis-cache"
DEFAULT_IP="10.0.30.20"
ROOT_PASSWORD="Homelab2025!"
STORAGE="local-lvm"

main() {
    print_banner "Redis Service Deployment"
    check_proxmox
    check_root

    if ! template_exists $TEMPLATE_ID; then
        echo -e "${RED}Error: Template ${TEMPLATE_ID} does not exist${NC}"
        echo "Create template: bash proxmox/scripts/templates/create-all-templates.sh"
        exit 1
    fi

    read -p "Container ID [${DEFAULT_CTID}]: " CTID
    CTID=${CTID:-$DEFAULT_CTID}

    read -p "Hostname [${DEFAULT_HOSTNAME}]: " HOSTNAME
    HOSTNAME=${HOSTNAME:-$DEFAULT_HOSTNAME}

    read -p "IP Address [${DEFAULT_IP}]: " IP_ADDRESS
    IP_ADDRESS=${IP_ADDRESS:-$DEFAULT_IP}

    echo ""
    echo "Deployment Configuration:"
    echo "  Container ID: ${CTID}"
    echo "  Hostname: ${HOSTNAME}"
    echo "  IP Address: ${IP_ADDRESS}"
    echo ""

    read -p "Deploy? (yes/no): " confirm
    [ "$confirm" != "yes" ] && exit 0

    clone_template "$TEMPLATE_ID" "$CTID" "$HOSTNAME" "$IP_ADDRESS" "$STORAGE"
    start_container "$CTID" 30
    wait_for_network "$CTID" 60
    change_root_password "$CTID" "$ROOT_PASSWORD"

    # Configure Redis for remote access
    exec_in_container $CTID "sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf"
    exec_in_container $CTID "systemctl restart redis"

    print_section "Deployment Complete"
    show_container_info "$CTID"

    echo -e "${GREEN}Redis Service Deployed!${NC}"
    echo ""
    echo "Access:"
    echo "  SSH: ssh root@${IP_ADDRESS}"
    echo "  Redis: redis-cli -h ${IP_ADDRESS}"
    echo ""
}

main "$@"
