# =============================================================================
# MikroTik RouterOS - Minimal Terraform Init Script
# =============================================================================
# Run this after soft reset to enable Terraform management via REST API
#
# Usage:
#   1. Connect via WinBox to 192.168.88.1 (admin, no password)
#   2. Open Terminal
#   3. Paste this script or import file: /import init-terraform.rsc
#
# After running:
#   - REST API: https://192.168.88.1:8443
#   - User: terraform / CHANGE_THIS_PASSWORD
# =============================================================================

# --- System Identity ---
/system identity set name="MikroTik-Chateau"

# --- Create SSL Certificate ---
:put "Creating SSL certificate..."
/certificate add name=rest-api-cert common-name=router.lan days-valid=3650 key-size=2048
:delay 2s
/certificate sign rest-api-cert
:delay 2s

# --- Enable REST API ---
:put "Enabling REST API on port 8443..."
/ip service set www-ssl certificate=rest-api-cert disabled=no port=8443
/ip service set www disabled=no port=80

# Disable insecure services
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set api disabled=yes
/ip service set api-ssl disabled=yes

# --- Create Terraform User ---
:put "Creating terraform user..."

# Group with full API access
/user group add name=terraform policy=api,local,policy,read,reboot,sensitive,ssh,test,write

# User (CHANGE PASSWORD AFTER!)
/user add name=terraform group=terraform password=CHANGE_THIS_PASSWORD comment="Terraform automation"

# --- Firewall: Allow REST API from LAN ---
:put "Configuring firewall..."

# Remove conflicting rules if exist
:do {
    /ip firewall filter remove [find where comment~"REST API"]
} on-error={}

# Allow REST API from LAN (before default drop)
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8443 \
    src-address=192.168.88.0/24 comment="Allow REST API from LAN" place-before=0

# Allow WinBox from LAN
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8291 \
    src-address=192.168.88.0/24 comment="Allow WinBox from LAN" place-before=1

# --- DNS: Set local domain ---
/ip dns set servers=1.1.1.1,8.8.8.8 allow-remote-requests=yes

# --- Summary ---
:put ""
:put "=============================================="
:put "Terraform Init Complete!"
:put "=============================================="
:put ""
:put "REST API: https://192.168.88.1:8443"
:put "User:     terraform"
:put "Password: CHANGE_THIS_PASSWORD"
:put ""
:put "NEXT STEPS:"
:put "1. Change password:"
:put "   /user set terraform password=YourSecurePassword"
:put ""
:put "2. Test API:"
:put "   curl -k -u terraform:pass https://192.168.88.1:8443/rest/system/identity"
:put ""
:put "3. Configure terraform.tfvars and run:"
:put "   cd generated/terraform-mikrotik"
:put "   terraform init && terraform apply"
:put ""
:put "=============================================="
