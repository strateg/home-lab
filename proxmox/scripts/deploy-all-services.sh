#!/bin/bash
# Deploy All Home Lab Services
# Master orchestration script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common-functions.sh"

# Service definitions: CTID:HOSTNAME:IP:TEMPLATE_ID:SERVICE_NAME
SERVICES=(
    "200:postgresql-db:10.0.30.10:900:PostgreSQL Database"
    "201:redis-cache:10.0.30.20:901:Redis Cache"
    "202:nextcloud:10.0.30.30:902:Nextcloud Storage"
    "203:gitea:10.0.30.40:903:Gitea Git Server"
    "204:homeassistant:10.0.30.50:904:Home Assistant"
    "205:grafana:10.0.30.60:905:Grafana Monitoring"
    "206:prometheus:10.0.30.70:906:Prometheus Metrics"
    "207:nginx-proxy:10.0.30.80:907:Nginx Proxy Manager"
    "208:docker-host:10.0.30.90:908:Docker Host"
)

ROOT_PASSWORD="Homelab2025!"
STORAGE="local-lvm"

deploy_service() {
    local ctid=$1
    local hostname=$2
    local ip=$3
    local template_id=$4
    local description=$5

    print_section "Deploying: $description"

    echo "Configuration:"
    echo "  CTID: $ctid"
    echo "  Hostname: $hostname"
    echo "  IP: $ip"
    echo "  Template: $template_id"
    echo ""

    # Check template
    if ! template_exists $template_id; then
        echo -e "${YELLOW}⚠ Template $template_id not found, skipping${NC}"
        return 1
    fi

    # Skip if exists
    if container_exists $ctid; then
        echo -e "${YELLOW}⚠ Container $ctid already exists, skipping${NC}"
        return 0
    fi

    # Deploy
    if clone_template "$template_id" "$ctid" "$hostname" "$ip" "$STORAGE"; then
        # Special configurations per service
        case $hostname in
            docker-host)
                pct set $ctid --features nesting=1,keyctl=1
                ;;
        esac

        start_container "$ctid" 30
        wait_for_network "$ctid" 60
        change_root_password "$ctid" "$ROOT_PASSWORD"

        echo -e "${GREEN}✓ Deployed: $description${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed: $description${NC}"
        return 1
    fi
}

main() {
    print_banner "Home Lab - Deploy All Services"

    check_proxmox
    check_root

    echo "Services to deploy:"
    echo ""
    for service in "${SERVICES[@]}"; do
        IFS=: read -r ctid hostname ip template_id desc <<< "$service"
        echo "  [$ctid] $desc - $ip"
    done
    echo ""

    read -p "Deploy all services? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled"
        exit 0
    fi

    DEPLOYED=0
    FAILED=0
    SKIPPED=0

    for service in "${SERVICES[@]}"; do
        IFS=: read -r ctid hostname ip template_id desc <<< "$service"

        if deploy_service "$ctid" "$hostname" "$ip" "$template_id" "$desc"; then
            ((DEPLOYED++))
        else
            if container_exists $ctid; then
                ((SKIPPED++))
            else
                ((FAILED++))
            fi
        fi

        sleep 2
    done

    print_banner "Deployment Complete"

    echo "Summary:"
    echo "  ✓ Deployed: $DEPLOYED"
    echo "  ⊘ Skipped: $SKIPPED"
    echo "  ✗ Failed: $FAILED"
    echo ""

    if [ $DEPLOYED -gt 0 ] || [ $SKIPPED -gt 0 ]; then
        list_containers
        echo ""
        echo -e "${CYAN}Access Information:${NC}"
        echo "  Root Password: $ROOT_PASSWORD"
        echo "  Network: $INTERNAL_NETWORK"
        echo "  Gateway: $INTERNAL_GATEWAY"
        echo ""
        echo "Services:"
        for service in "${SERVICES[@]}"; do
            IFS=: read -r ctid hostname ip template_id desc <<< "$service"
            if container_exists $ctid; then
                echo "  $desc: http://$ip"
            fi
        done
        echo ""
    fi
}

main "$@"
