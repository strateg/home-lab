#!/bin/bash
# Proxmox Network Configuration Script
# Automates network bridge setup with persistent interface naming

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/network-functions.sh"
source "${SCRIPT_DIR}/lib/common-functions.sh"

# Configuration
UDEV_RULES_FILE="/etc/udev/rules.d/70-persistent-net.rules"
NETWORK_INTERFACES_FILE="/etc/network/interfaces"
NETWORK_BACKUP_DIR="/root/network-backups"

show_banner() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║         PROXMOX NETWORK CONFIGURATION AUTOMATION              ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
}

backup_network_config() {
    print_info "Creating backup of current network configuration..."

    mkdir -p "$NETWORK_BACKUP_DIR"
    local backup_timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_dir="${NETWORK_BACKUP_DIR}/backup-${backup_timestamp}"
    mkdir -p "$backup_dir"

    if [ -f "$NETWORK_INTERFACES_FILE" ]; then
        cp "$NETWORK_INTERFACES_FILE" "${backup_dir}/interfaces"
        print_success "Backed up: $NETWORK_INTERFACES_FILE"
    fi

    if [ -f "$UDEV_RULES_FILE" ]; then
        cp "$UDEV_RULES_FILE" "${backup_dir}/70-persistent-net.rules"
        print_success "Backed up: $UDEV_RULES_FILE"
    fi

    print_success "Backup created: $backup_dir"
}

interactive_mode() {
    show_banner

    print_info "Detecting network interfaces..."
    detect_network_interfaces

    echo ""
    print_info "Network Architecture:"
    echo "  vmbr0 (WAN)      → USB Ethernet → ISP Router"
    echo "  vmbr1 (LAN)      → Built-in Ethernet → OpenWRT WAN"
    echo "  vmbr2 (Internal) → 10.0.30.0/24 → LXC Containers"
    echo "  vmbr99 (Mgmt)    → 10.0.99.0/24 → Emergency Access"
    echo ""

    # Show detected interfaces
    show_network_status

    echo ""
    read -p "Do you want to automatically configure network? (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_warning "Configuration cancelled by user"
        exit 0
    fi

    # Backup current config
    backup_network_config

    # Select interfaces
    print_info "Selecting network interfaces..."
    select_network_interfaces

    # Generate udev rules
    print_info "Generating udev rules for persistent naming..."
    generate_udev_rules

    if [ -f "/tmp/70-persistent-net.rules" ]; then
        print_info "Installing udev rules..."
        cp /tmp/70-persistent-net.rules "$UDEV_RULES_FILE"
        print_success "Installed: $UDEV_RULES_FILE"
    fi

    # Generate network interfaces
    print_info "Generating network interfaces configuration..."
    generate_network_interfaces

    if [ -f "/tmp/interfaces" ]; then
        print_info "Preview of new configuration:"
        echo "----------------------------------------"
        cat /tmp/interfaces
        echo "----------------------------------------"
        echo ""

        read -p "Apply this configuration? (y/n): " apply_confirm
        if [[ "$apply_confirm" =~ ^[Yy]$ ]]; then
            cp /tmp/interfaces "$NETWORK_INTERFACES_FILE"
            print_success "Installed: $NETWORK_INTERFACES_FILE"

            echo ""
            print_warning "Network configuration updated!"
            print_warning "You MUST reboot for changes to take effect:"
            echo ""
            echo "  systemctl reboot"
            echo ""

            read -p "Reboot now? (y/n): " reboot_confirm
            if [[ "$reboot_confirm" =~ ^[Yy]$ ]]; then
                print_info "Rebooting in 5 seconds... (Ctrl+C to cancel)"
                sleep 5
                systemctl reboot
            else
                print_warning "Remember to reboot manually!"
            fi
        else
            print_warning "Configuration not applied"
            print_info "Preview saved to: /tmp/interfaces"
        fi
    fi
}

automated_mode() {
    show_banner
    print_info "Running in automated mode..."

    # Detect interfaces
    detect_network_interfaces

    # Select interfaces automatically
    select_network_interfaces

    # Generate udev rules
    generate_udev_rules
    if [ -f "/tmp/70-persistent-net.rules" ]; then
        cp /tmp/70-persistent-net.rules "$UDEV_RULES_FILE"
        print_success "Generated: $UDEV_RULES_FILE"
    fi

    # Generate network interfaces
    generate_network_interfaces
    if [ -f "/tmp/interfaces" ]; then
        backup_network_config
        cp /tmp/interfaces "$NETWORK_INTERFACES_FILE"
        print_success "Generated: $NETWORK_INTERFACES_FILE"
    fi

    print_success "Network configuration completed!"
    print_warning "Reboot required for changes to take effect"
}

show_current_config() {
    show_banner
    print_info "Current Network Configuration:"
    echo ""

    if [ -f "$NETWORK_INTERFACES_FILE" ]; then
        echo "=== /etc/network/interfaces ==="
        cat "$NETWORK_INTERFACES_FILE"
        echo ""
    fi

    if [ -f "$UDEV_RULES_FILE" ]; then
        echo "=== $UDEV_RULES_FILE ==="
        cat "$UDEV_RULES_FILE"
        echo ""
    fi

    echo "=== Current Network Status ==="
    ip -br addr show
    echo ""

    echo "=== Bridge Status ==="
    ip -br link show type bridge 2>/dev/null || echo "No bridges configured"
}

restore_backup() {
    show_banner

    if [ ! -d "$NETWORK_BACKUP_DIR" ]; then
        print_error "No backups found in $NETWORK_BACKUP_DIR"
        exit 1
    fi

    print_info "Available backups:"
    local backups=($(ls -1 "$NETWORK_BACKUP_DIR" | grep "backup-" | sort -r))

    if [ ${#backups[@]} -eq 0 ]; then
        print_error "No backups found"
        exit 1
    fi

    local idx=1
    for backup in "${backups[@]}"; do
        echo "  $idx) $backup"
        ((idx++))
    done

    echo ""
    read -p "Select backup to restore (1-${#backups[@]}): " selection

    if [[ ! "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt ${#backups[@]} ]; then
        print_error "Invalid selection"
        exit 1
    fi

    local backup_dir="${NETWORK_BACKUP_DIR}/${backups[$((selection-1))]}"

    print_info "Restoring from: $backup_dir"

    if [ -f "${backup_dir}/interfaces" ]; then
        cp "${backup_dir}/interfaces" "$NETWORK_INTERFACES_FILE"
        print_success "Restored: $NETWORK_INTERFACES_FILE"
    fi

    if [ -f "${backup_dir}/70-persistent-net.rules" ]; then
        cp "${backup_dir}/70-persistent-net.rules" "$UDEV_RULES_FILE"
        print_success "Restored: $UDEV_RULES_FILE"
    fi

    print_success "Backup restored successfully"
    print_warning "Reboot required for changes to take effect"
}

show_help() {
    cat << EOF
Proxmox Network Configuration Script

USAGE:
    $(basename $0) [OPTIONS]

OPTIONS:
    -h, --help          Show this help message
    -i, --interactive   Interactive configuration (default)
    -a, --auto          Automated configuration (no prompts)
    -s, --show          Show current configuration
    -r, --restore       Restore from backup
    -d, --diagram       Generate network diagram
    -t, --test          Test network connectivity

EXAMPLES:
    # Interactive setup
    bash configure-network.sh

    # Automated setup
    bash configure-network.sh --auto

    # Show current config
    bash configure-network.sh --show

    # Restore backup
    bash configure-network.sh --restore

NETWORK ARCHITECTURE:
    vmbr0  - WAN Bridge (USB-Ethernet → ISP Router)
    vmbr1  - LAN Bridge (Built-in Ethernet → OpenWRT)
    vmbr2  - Internal Bridge (10.0.30.0/24 → LXC Containers)
    vmbr99 - Management Bridge (10.0.99.0/24 → Emergency Access)

EOF
}

# Main
main() {
    check_root

    case "${1:-}" in
        -h|--help)
            show_help
            ;;
        -a|--auto)
            automated_mode
            ;;
        -s|--show)
            show_current_config
            ;;
        -r|--restore)
            restore_backup
            ;;
        -d|--diagram)
            show_banner
            generate_network_diagram
            ;;
        -t|--test)
            show_banner
            test_network_connectivity
            ;;
        -i|--interactive|"")
            interactive_mode
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
