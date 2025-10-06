#!/bin/bash
# Complete Home Lab Deployment
# Deploys OPNsense VM and LXC services from templates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common-functions.sh"

show_banner "Complete Home Lab Deployment"

print_info "This script will deploy:"
echo "  1. OPNsense Firewall VM (ID: 100)"
echo "  2. LXC Routing Configuration"
echo "  3. All LXC Services (IDs: 200-208)"
echo ""

# Parse arguments
DEPLOY_OPNSENSE=true
DEPLOY_LXC=true
SKIP_OPNSENSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-opnsense)
            SKIP_OPNSENSE=true
            shift
            ;;
        --opnsense-only)
            DEPLOY_LXC=false
            shift
            ;;
        --lxc-only)
            DEPLOY_OPNSENSE=false
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-opnsense   Skip OPNsense deployment"
            echo "  --opnsense-only   Deploy only OPNsense"
            echo "  --lxc-only        Deploy only LXC services"
            echo "  --help, -h        Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Prerequisites check
print_info "Checking prerequisites..."

# Check templates exist
MISSING_TEMPLATES=()

if [ "$DEPLOY_OPNSENSE" = true ] && ! $SKIP_OPNSENSE; then
    if ! vm_template_exists 910; then
        MISSING_TEMPLATES+=("910 (OPNsense)")
    fi
fi

if [ "$DEPLOY_LXC" = true ]; then
    for template_id in 900 901 902 903 904 905 906 907 908; do
        if ! template_exists $template_id; then
            MISSING_TEMPLATES+=("$template_id (LXC)")
        fi
    done
fi

if [ ${#MISSING_TEMPLATES[@]} -gt 0 ]; then
    print_error "Missing templates:"
    for tmpl in "${MISSING_TEMPLATES[@]}"; do
        echo "  - $tmpl"
    done
    echo ""
    echo "Create templates first:"
    if [[ " ${MISSING_TEMPLATES[@]} " =~ " 910 " ]]; then
        echo "  bash vms/create-opnsense-template.sh"
    fi
    if [ ${#MISSING_TEMPLATES[@]} -gt 1 ]; then
        echo "  bash templates/create-all-templates.sh"
    fi
    exit 1
fi

print_success "All required templates exist"
echo ""

# Deployment timeline
print_info "Estimated deployment time:"
if [ "$DEPLOY_OPNSENSE" = true ] && ! $SKIP_OPNSENSE; then
    echo "  OPNsense VM: ~2 minutes"
fi
if [ "$DEPLOY_LXC" = true ]; then
    echo "  LXC Services (9): ~10 minutes"
fi
echo "  Total: ~12-15 minutes"
echo ""

read -p "Continue with deployment? (y/n): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    print_warning "Deployment cancelled"
    exit 0
fi

# ==============================================================================
# Phase 1: Deploy OPNsense
# ==============================================================================

if [ "$DEPLOY_OPNSENSE" = true ] && ! $SKIP_OPNSENSE; then
    print_section "PHASE 1: OPNsense Firewall Deployment"

    if vm_exists 100; then
        print_warning "OPNsense VM already exists (ID: 100)"
        read -p "Skip OPNsense deployment? (y/n): " skip_opn
        if [[ "$skip_opn" =~ ^[Yy]$ ]]; then
            print_info "Skipping OPNsense deployment"
        else
            bash "${SCRIPT_DIR}/vms/deploy-opnsense.sh"
        fi
    else
        bash "${SCRIPT_DIR}/vms/deploy-opnsense.sh"
    fi

    # Wait for OPNsense to fully boot
    print_info "Waiting for OPNsense to fully initialize (90 seconds)..."
    sleep 90

    print_success "OPNsense deployment complete"
    echo ""
fi

# ==============================================================================
# Phase 2: Configure LXC Routing
# ==============================================================================

print_section "PHASE 2: LXC Routing Configuration"

if ! vm_exists 100; then
    print_warning "OPNsense VM not found - routing will be configured but may not work"
elif [ "$(qm status 100 2>/dev/null | grep -o 'running')" != "running" ]; then
    print_warning "OPNsense VM is not running - starting it now"
    qm start 100
    sleep 60
fi

bash "${SCRIPT_DIR}/configure-lxc-routing.sh"

print_success "Routing configuration complete"
echo ""

# ==============================================================================
# Phase 3: Deploy LXC Services
# ==============================================================================

if [ "$DEPLOY_LXC" = true ]; then
    print_section "PHASE 3: LXC Services Deployment"

    print_info "Deploying 9 LXC services..."
    echo ""

    # Check which services already exist
    EXISTING_SERVICES=()
    for ctid in {200..208}; do
        if container_exists $ctid; then
            EXISTING_SERVICES+=($ctid)
        fi
    done

    if [ ${#EXISTING_SERVICES[@]} -gt 0 ]; then
        print_warning "Found existing containers:"
        pct list | grep -E "^(200|201|202|203|204|205|206|207|208) "
        echo ""
        read -p "Remove and redeploy all? (yes/no): " redeploy
        if [ "$redeploy" != "yes" ]; then
            print_warning "Keeping existing containers, deploying only missing ones"
        else
            print_info "Removing existing containers..."
            for ctid in "${EXISTING_SERVICES[@]}"; do
                pct stop $ctid 2>/dev/null || true
                pct destroy $ctid
            done
        fi
    fi

    # Deploy all services
    bash "${SCRIPT_DIR}/deploy-all-services.sh"

    print_success "LXC services deployment complete"
    echo ""
fi

# ==============================================================================
# Final Status
# ==============================================================================

print_section "DEPLOYMENT COMPLETE!"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                   System Status                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# OPNsense status
if vm_exists 100; then
    OPNSENSE_STATUS=$(qm status 100 | grep -o 'running' || echo "stopped")
    if [ "$OPNSENSE_STATUS" = "running" ]; then
        print_success "OPNsense VM (100): Running"
        echo "  Access: https://192.168.10.1 or https://10.0.99.10"
    else
        print_warning "OPNsense VM (100): $OPNSENSE_STATUS"
    fi
else
    print_info "OPNsense VM: Not deployed"
fi

echo ""

# LXC services status
if [ "$DEPLOY_LXC" = true ]; then
    print_info "LXC Services:"
    pct list | grep -E "^20[0-8] " || echo "  No LXC services deployed"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                   Next Steps                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [ "$DEPLOY_OPNSENSE" = true ] || vm_exists 100; then
    echo "1. Configure OPNsense:"
    echo "   - Access: https://192.168.10.1"
    echo "   - Login: root / opnsense"
    echo "   - Configure INTERNAL interface: 10.0.30.254/24"
    echo "   - Configure MGMT interface: 10.0.99.10/24"
    echo "   - Setup firewall rules (see opnsense/configs/)"
    echo ""
fi

if [ "$DEPLOY_LXC" = true ]; then
    echo "2. Test LXC connectivity:"
    echo "   pct exec 200 -- ping -c 3 8.8.8.8"
    echo ""
    echo "3. Access LXC services:"
    echo "   - PostgreSQL: pct exec 200 -- su - postgres -c 'psql'"
    echo "   - Redis: pct exec 201 -- redis-cli ping"
    echo "   - Docker: pct exec 208 -- docker ps"
    echo ""
fi

echo "4. Deploy OpenWRT router (manual):"
echo "   - Connect to OPNsense LAN: 192.168.10.2/24"
echo "   - Configure as described in openwrt/ configs"
echo ""

echo "5. Backup configuration:"
echo "   - OPNsense: System → Configuration → Backups"
echo "   - LXC: vzdump 200-208 --storage local-hdd"
echo ""

print_info "Documentation:"
echo "  - Network setup: proxmox/scripts/NETWORK-SETUP.md"
echo "  - LXC automation: proxmox/scripts/README.md"
echo "  - Architecture: proxmox/scripts/ARCHITECTURE.md"
echo "  - Quick start: proxmox/scripts/QUICK-START.md"
echo ""

print_success "Deployment complete! Your home lab is ready 🚀"
