#!/bin/bash
# Deploy Docker Host from Template

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common-functions.sh"

TEMPLATE_ID=908
DEFAULT_CTID=208
DEFAULT_HOSTNAME="docker-host"
DEFAULT_IP="10.0.30.90"
ROOT_PASSWORD="Homelab2025!"
STORAGE="local-lvm"

main() {
    print_banner "Docker Host Deployment"
    check_proxmox
    check_root

    if ! template_exists $TEMPLATE_ID; then
        echo -e "${RED}Error: Template ${TEMPLATE_ID} does not exist${NC}"
        exit 1
    fi

    read -p "Container ID [${DEFAULT_CTID}]: " CTID
    CTID=${CTID:-$DEFAULT_CTID}

    read -p "Hostname [${DEFAULT_HOSTNAME}]: " HOSTNAME
    HOSTNAME=${HOSTNAME:-$DEFAULT_HOSTNAME}

    read -p "IP Address [${DEFAULT_IP}]: " IP_ADDRESS
    IP_ADDRESS=${IP_ADDRESS:-$DEFAULT_IP}

    echo ""
    read -p "Deploy? (yes/no): " confirm
    [ "$confirm" != "yes" ] && exit 0

    clone_template "$TEMPLATE_ID" "$CTID" "$HOSTNAME" "$IP_ADDRESS" "$STORAGE"

    # Docker needs privileged container or proper nesting
    echo "Enabling container features for Docker..."
    pct set $CTID --features nesting=1,keyctl=1

    start_container "$CTID" 30
    wait_for_network "$CTID" 60
    change_root_password "$CTID" "$ROOT_PASSWORD"

    # Verify Docker
    exec_in_container $CTID "docker --version"

    print_section "Deployment Complete"
    show_container_info "$CTID"

    echo -e "${GREEN}Docker Host Deployed!${NC}"
    echo ""
    echo "Access:"
    echo "  SSH: ssh root@${IP_ADDRESS}"
    echo "  Docker: docker -H ssh://root@${IP_ADDRESS} ps"
    echo ""
    echo "Test Docker:"
    echo "  pct exec ${CTID} -- docker run hello-world"
    echo ""
}

main "$@"
