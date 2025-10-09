#!/bin/bash
# Common functions for LXC template and service management
# Source this file: source proxmox/scripts/lib/common-functions.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Network configuration
INTERNAL_NETWORK="10.0.30.0/24"
INTERNAL_GATEWAY="10.0.30.254"  # OPNsense INTERNAL interface (Internet gateway)
PROXMOX_INTERNAL_IP="10.0.30.1"  # Proxmox host IP (direct access)
DNS_SERVER="192.168.10.2"  # AdGuard DNS on OpenWRT
BRIDGE="vmbr2"  # Internal bridge for LXC containers

# Storage configuration
TEMPLATE_STORAGE="local-hdd"  # Templates on HDD
PRODUCTION_STORAGE="local-lvm"  # Production containers on SSD
TEST_STORAGE="local-hdd"  # Test containers on HDD

# Base URL for Community Scripts
COMMUNITY_SCRIPTS_URL="https://github.com/community-scripts/ProxmoxVE/raw/main/ct"

# Check if running on Proxmox
check_proxmox() {
    if ! command -v pveversion &> /dev/null; then
        echo -e "${RED}Error: This script must be run on Proxmox VE${NC}"
        exit 1
    fi
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Error: This script must be run as root${NC}"
        exit 1
    fi
}

# Check if template exists
template_exists() {
    local template_id=$1
    pct list | grep -q "^${template_id} .*template"
}

# Check if container exists
container_exists() {
    local ctid=$1
    pct list | grep -q "^${ctid} "
}

# Check if VM exists
vm_exists() {
    local vmid=$1
    qm list | grep -q "^${vmid} "
}

# Check if VM template exists
vm_template_exists() {
    local vmid=$1
    qm list | grep "^${vmid} " | grep -q "template"
}

# Get next available CT ID
get_next_ctid() {
    local start_id=${1:-200}
    local ctid=$start_id

    while container_exists $ctid; do
        ((ctid++))
    done

    echo $ctid
}

# Create template using Community Scripts
create_template_from_community() {
    local template_id=$1
    local script_name=$2
    local template_name=$3
    local description=$4

    echo -e "${BLUE}Creating template: ${template_name} (ID: ${template_id})${NC}"

    if template_exists $template_id; then
        echo -e "${YELLOW}Template ID ${template_id} already exists${NC}"
        return 0
    fi

    if container_exists $template_id; then
        echo -e "${YELLOW}Container ID ${template_id} exists (not template)${NC}"
        read -p "Convert to template? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            pct stop $template_id 2>/dev/null || true
            pct template $template_id
            echo -e "${GREEN}✓ Converted to template${NC}"
            return 0
        else
            return 1
        fi
    fi

    # Download and run Community Script
    local script_url="${COMMUNITY_SCRIPTS_URL}/${script_name}.sh"

    echo "Downloading: $script_url"

    # Set environment variables for non-interactive installation
    export CTID="$template_id"
    export CT_TYPE="1"  # Unprivileged
    export PW="ChangeMe123!"  # Will be changed on first clone
    export CT_NAME="$template_name"
    export DISK_SIZE="8"
    export CORE_COUNT="2"
    export RAM_SIZE="2048"
    export BRG="$BRIDGE"
    export NET="dhcp"  # DHCP for template, static on clone
    export GATE="$INTERNAL_GATEWAY"
    export APT_CACHER="0"
    export DISABLEIPV6="no"
    export NS="$DNS_SERVER"
    export VERB="no"
    export SD="$TEMPLATE_STORAGE"  # Store template on HDD

    # Run Community Script
    if bash -c "$(wget -qLO - $script_url)" ; then
        echo -e "${GREEN}✓ Container created${NC}"

        # Wait for container to be ready
        sleep 5

        # Stop container
        echo "Stopping container..."
        pct stop $template_id
        sleep 2

        # Convert to template
        echo "Converting to template..."
        pct template $template_id

        # Set description
        if [ -n "$description" ]; then
            pct set $template_id --description "$description"
        fi

        echo -e "${GREEN}✓ Template created: ${template_name} (ID: ${template_id})${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to create template${NC}"
        return 1
    fi
}

# Clone template to create service
clone_template() {
    local template_id=$1
    local new_ctid=$2
    local new_hostname=$3
    local ip_address=$4
    local storage=${5:-$PRODUCTION_STORAGE}

    echo -e "${BLUE}Cloning template ${template_id} → ${new_hostname} (ID: ${new_ctid})${NC}"

    if ! template_exists $template_id; then
        echo -e "${RED}Error: Template ${template_id} does not exist${NC}"
        return 1
    fi

    if container_exists $new_ctid; then
        echo -e "${YELLOW}Container ID ${new_ctid} already exists${NC}"
        return 1
    fi

    # Clone template
    echo "Cloning..."
    pct clone $template_id $new_ctid \
        --hostname "$new_hostname" \
        --storage "$storage" \
        --full

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Clone failed${NC}"
        return 1
    fi

    echo -e "${GREEN}✓ Cloned successfully${NC}"

    # Configure network with static IP
    if [ -n "$ip_address" ]; then
        echo "Configuring network: $ip_address"
        pct set $new_ctid \
            --net0 name=eth0,bridge=$BRIDGE,ip=${ip_address}/24,gw=$INTERNAL_GATEWAY

        pct set $new_ctid --nameserver $DNS_SERVER
    fi

    # Set to start on boot
    pct set $new_ctid --onboot 1

    echo -e "${GREEN}✓ Container configured${NC}"
    return 0
}

# Start container and wait for it to be ready
start_container() {
    local ctid=$1
    local wait_seconds=${2:-30}

    echo "Starting container ${ctid}..."
    pct start $ctid

    echo "Waiting for container to be ready (${wait_seconds}s)..."
    sleep $wait_seconds

    if pct status $ctid | grep -q "running"; then
        echo -e "${GREEN}✓ Container is running${NC}"
        return 0
    else
        echo -e "${RED}✗ Container failed to start${NC}"
        return 1
    fi
}

# Execute command in container
exec_in_container() {
    local ctid=$1
    shift
    local cmd="$@"

    pct exec $ctid -- bash -c "$cmd"
}

# Change container root password
change_root_password() {
    local ctid=$1
    local new_password=$2

    echo "Changing root password..."
    echo -e "${new_password}\n${new_password}" | pct exec $ctid -- passwd root
}

# Display container info
show_container_info() {
    local ctid=$1

    echo ""
    echo -e "${CYAN}Container Information:${NC}"
    echo "  ID: $ctid"
    echo "  Hostname: $(pct config $ctid | grep hostname | cut -d: -f2 | xargs)"
    echo "  IP: $(pct config $ctid | grep 'net0:' | grep -oP 'ip=\K[^,]+')"
    echo "  Status: $(pct status $ctid | awk '{print $2}')"
    echo "  Storage: $(pct config $ctid | grep rootfs | cut -d: -f2 | cut -d, -f1)"
    echo ""
}

# List all templates
list_templates() {
    echo -e "${CYAN}Available Templates:${NC}"
    pct list | grep "template" | awk '{printf "  ID %-4s - %s\n", $1, $3}'
}

# List all containers from templates
list_containers() {
    echo -e "${CYAN}Deployed Containers:${NC}"
    pct list | grep -v "template" | awk '{printf "  ID %-4s - %-20s - %s\n", $1, $3, $2}'
}

# Backup container
backup_container() {
    local ctid=$1
    local storage=${2:-$TEMPLATE_STORAGE}

    echo "Creating backup of container ${ctid}..."
    vzdump $ctid --storage $storage --mode snapshot --compress zstd
}

# Remove container
remove_container() {
    local ctid=$1
    local confirm=${2:-prompt}

    if [ "$confirm" = "prompt" ]; then
        read -p "Remove container ${ctid}? (yes/no): " answer
        if [ "$answer" != "yes" ]; then
            echo "Cancelled"
            return 1
        fi
    fi

    echo "Stopping container..."
    pct stop $ctid 2>/dev/null || true
    sleep 2

    echo "Removing container..."
    pct destroy $ctid

    echo -e "${GREEN}✓ Container ${ctid} removed${NC}"
}

# Print banner
print_banner() {
    local title=$1
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ${title}${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Print section
print_section() {
    local title=$1
    echo ""
    echo -e "${BLUE}━━━ ${title} ━━━${NC}"
    echo ""
}

# Validate IP address
validate_ip() {
    local ip=$1
    local ip_regex='^([0-9]{1,3}\.){3}[0-9]{1,3}$'

    if [[ $ip =~ $ip_regex ]]; then
        return 0
    else
        return 1
    fi
}

# Get container IP
get_container_ip() {
    local ctid=$1
    pct config $ctid | grep 'net0:' | grep -oP 'ip=\K[^/,]+'
}

# Wait for network in container
wait_for_network() {
    local ctid=$1
    local max_wait=${2:-60}
    local count=0

    echo "Waiting for network in container ${ctid}..."

    while [ $count -lt $max_wait ]; do
        if pct exec $ctid -- ping -c 1 8.8.8.8 &>/dev/null; then
            echo -e "${GREEN}✓ Network is ready${NC}"
            return 0
        fi
        sleep 2
        ((count+=2))
    done

    echo -e "${YELLOW}⚠ Network not ready after ${max_wait}s${NC}"
    return 1
}

# Export functions for subshells
export -f check_proxmox
export -f check_root
export -f template_exists
export -f container_exists
export -f get_next_ctid
export -f create_template_from_community
export -f clone_template
export -f start_container
export -f exec_in_container
export -f change_root_password
export -f show_container_info
export -f list_templates
export -f list_containers
export -f backup_container
export -f remove_container
export -f print_banner
export -f print_section
export -f validate_ip
export -f get_container_ip
export -f wait_for_network
