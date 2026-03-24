# =============================================================================
# MikroTik RouterOS Bootstrap Script
# =============================================================================
# This script prepares MikroTik Chateau LTE7 ax for Terraform management
#
# Usage:
#   1. Connect to MikroTik via WinBox or WebFig (192.168.88.1)
#   2. Open Terminal or Files section
#   3. Import this script: /import bootstrap.rsc
#   4. Or copy-paste commands manually
#
# After running this script:
#   - REST API is available at https://192.168.88.1:8443
#   - Terraform user 'terraform' is created
#   - Container support is enabled (requires RouterOS 7.4+)
#
# =============================================================================

# -----------------------------------------------------------------------------
# System Identity
# -----------------------------------------------------------------------------
/system identity set name="MikroTik-Chateau"

# -----------------------------------------------------------------------------
# Create SSL Certificate for REST API
# -----------------------------------------------------------------------------
:log info "Creating SSL certificate for REST API..."

/certificate add name=local-cert common-name=mikrotik.home.local \
    days-valid=3650 key-size=2048 key-usage=key-encipherment,tls-server

:delay 2s

/certificate sign local-cert
:delay 2s

# -----------------------------------------------------------------------------
# Enable REST API (www-ssl service)
# -----------------------------------------------------------------------------
:log info "Enabling REST API..."

/ip service set www-ssl certificate=local-cert disabled=no port=8443
/ip service set www disabled=no  # Keep WebFig available

# Disable unnecessary services
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set api disabled=yes  # Use REST API instead

# -----------------------------------------------------------------------------
# Create Terraform User
# -----------------------------------------------------------------------------
:log info "Creating Terraform user..."

# Create group with necessary permissions
/user group add name=terraform \
    policy=api,read,write,policy,sensitive,test,local,ssh,reboot

# Create terraform user (CHANGE PASSWORD!)
/user add name=terraform group=terraform password=CHANGE_ME_IMMEDIATELY \
    comment="Terraform automation user"

# -----------------------------------------------------------------------------
# Firewall Rules for API Access
# -----------------------------------------------------------------------------
:log info "Adding firewall rules..."

# Allow REST API from management network
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8443 \
    src-address=10.0.99.0/24 comment="Allow REST API from management network" \
    place-before=0

# Allow REST API from LAN (for initial setup)
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8443 \
    src-address=192.168.88.0/24 comment="Allow REST API from LAN (temp)" \
    place-before=1

# -----------------------------------------------------------------------------
# Container Support (RouterOS 7.4+)
# -----------------------------------------------------------------------------
:log info "Configuring container support..."

# Enable container mode (requires reboot)
:if ([/system/resource get version] >= "7.4") do={
    /system/device-mode/update container=yes
    :log info "Container mode enabled (reboot required)"
} else={
    :log warning "RouterOS version < 7.4, containers not supported"
}

# Configure container registry
/container/config set registry-url=https://registry-1.docker.io \
    tmpdir=/usb1/containers/tmp ram-high=512M

# -----------------------------------------------------------------------------
# USB Storage Preparation
# -----------------------------------------------------------------------------
:log info "Preparing USB storage for containers..."

# Note: USB storage must be physically connected and formatted
# Commands below will fail if USB is not present

:do {
    /disk format-drive usb1 file-system=ext4 label=containers
} on-error={
    :log warning "USB storage not found or already formatted"
}

# Create directories for containers
:do {
    /file mkdir /usb1/containers
    /file mkdir /usb1/containers/adguard
    /file mkdir /usb1/containers/adguard/config
    /file mkdir /usb1/containers/adguard/data
    /file mkdir /usb1/containers/adguard/root
    /file mkdir /usb1/containers/tailscale
    /file mkdir /usb1/containers/tailscale/state
    /file mkdir /usb1/containers/tailscale/root
    /file mkdir /usb1/containers/tmp
} on-error={
    :log warning "Could not create container directories"
}

# -----------------------------------------------------------------------------
# Backup Current Configuration
# -----------------------------------------------------------------------------
:log info "Creating configuration backup..."
/export file=pre-terraform-backup

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
:log info "========================================"
:log info "Bootstrap completed!"
:log info "========================================"
:log info "REST API: https://192.168.88.1:8443"
:log info "User: terraform"
:log info "Password: CHANGE_ME_IMMEDIATELY"
:log info ""
:log info "IMPORTANT:"
:log info "1. Change terraform user password!"
:log info "2. Reboot for container mode"
:log info "3. Connect USB SSD for containers"
:log info "========================================"

:put ""
:put "========================================"
:put "Bootstrap completed!"
:put "========================================"
:put ""
:put "REST API available at: https://192.168.88.1:8443"
:put ""
:put "IMPORTANT NEXT STEPS:"
:put "1. Change the terraform user password:"
:put "   /user set terraform password=YOUR_SECURE_PASSWORD"
:put ""
:put "2. Reboot to enable container mode:"
:put "   /system reboot"
:put ""
:put "3. After reboot, configure terraform.tfvars:"
:put "   mikrotik_host = \"https://192.168.88.1:8443\""
:put "   mikrotik_username = \"terraform\""
:put "   mikrotik_password = \"YOUR_SECURE_PASSWORD\""
:put ""
:put "4. Run Terraform:"
:put "   cd generated/terraform-mikrotik"
:put "   terraform init && terraform plan"
:put ""
:put "========================================"
