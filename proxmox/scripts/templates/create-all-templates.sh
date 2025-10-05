#!/bin/bash
# Create All Service Templates
# Master script to create all templates at once

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common-functions.sh"

# Template definitions: ID:SCRIPT_NAME:TEMPLATE_NAME
TEMPLATES=(
    "900:postgresql:postgresql-template"
    "901:redis:redis-template"
    "902:nextcloud:nextcloud-template"
    "903:gitea:gitea-template"
    "904:homeassistant:homeassistant-template"
    "905:grafana:grafana-template"
    "906:prometheus:prometheus-template"
    "907:nginxproxymanager:npm-template"
    "908:docker:docker-template"
)

main() {
    print_banner "Create All Service Templates"

    check_proxmox
    check_root

    echo "Templates to create:"
    echo ""
    for template in "${TEMPLATES[@]}"; do
        IFS=: read -r id script name <<< "$template"
        echo "  ID $id: $name (from $script)"
    done
    echo ""

    read -p "Create all templates? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled"
        exit 0
    fi

    CREATED=0
    FAILED=0

    for template in "${TEMPLATES[@]}"; do
        IFS=: read -r id script name <<< "$template"

        print_section "Creating: $name"

        if template_exists "$id"; then
            echo -e "${YELLOW}Template $id already exists, skipping${NC}"
            ((CREATED++))
            continue
        fi

        DESC="Template: $name
Created: $(date +%Y-%m-%d)
Script: $script
Storage: ${TEMPLATE_STORAGE}"

        if create_template_from_community "$id" "$script" "$name" "$DESC"; then
            ((CREATED++))
        else
            ((FAILED++))
        fi

        sleep 5
    done

    echo ""
    print_banner "Template Creation Complete"
    echo "Summary:"
    echo "  ✓ Created/Exists: $CREATED"
    echo "  ✗ Failed: $FAILED"
    echo ""

    if [ $CREATED -gt 0 ]; then
        list_templates
    fi
}

main "$@"
