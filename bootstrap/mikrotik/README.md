# MikroTik Bootstrap Guide

Prepare MikroTik Chateau LTE7 ax for Terraform automation via REST API.

## Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `init-terraform.rsc` | Minimal - enable REST API only | After soft reset |
| `bootstrap.rsc` | Full - REST API + containers + USB | Fresh setup with containers |

## Quick Start (After Soft Reset)

### 1. Connect to Router

After soft reset, MikroTik Chateau has default config:
- IP: `192.168.88.1`
- User: `admin` (no password)
- Bridge on ether2-5, wlan1-2

Connect via WinBox to `192.168.88.1`.

### 2. Run Init Script

Open Terminal and paste:

```routeros
# Minimal: Enable REST API for Terraform
/import init-terraform.rsc
```

Or run commands manually:

```routeros
# 1. Create SSL certificate
/certificate add name=rest-api-cert common-name=router.lan days-valid=3650
/certificate sign rest-api-cert

# 2. Enable REST API
/ip service set www-ssl certificate=rest-api-cert disabled=no port=8443

# 3. Create Terraform user
/user group add name=terraform policy=api,local,policy,read,reboot,sensitive,ssh,test,write
/user add name=terraform group=terraform password=YOUR_PASSWORD

# 4. Allow API in firewall
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8443 \
    src-address=192.168.88.0/24 comment="Allow REST API from LAN" place-before=0
```

### 3. Change Password!

```routeros
/user set terraform password=YourSecurePassword
```

### 4. Test Connection

From your workstation:

```bash
curl -k -u terraform:YourSecurePassword https://192.168.88.1:8443/rest/system/identity
```

Expected: `{"name":"MikroTik-Chateau"}`

### 5. Configure Terraform

```bash
cd generated/terraform-mikrotik
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
mikrotik_host     = "https://192.168.88.1:8443"
mikrotik_username = "terraform"
mikrotik_password = "YourSecurePassword"
mikrotik_insecure = true
```

### 6. Deploy

```bash
terraform init
terraform plan
terraform apply
```

## Full Bootstrap (With Containers)

For full setup including AdGuard and Tailscale containers:

```routeros
/import bootstrap.rsc
/system reboot  # Required for container mode
```

After reboot, connect USB SSD and run:
```routeros
/disk format-drive usb1 file-system=ext4 label=containers
```

## Troubleshooting

### Cannot Connect to 192.168.88.1

After soft reset without Quick Set:
1. Connect via MAC WinBox (WinBox → Neighbors)
2. Or connect cable to ether2-5 and get DHCP

### REST API Not Responding

```routeros
# Check service
/ip service print where name=www-ssl

# Check certificate
/certificate print

# Check firewall
/ip firewall filter print where dst-port=8443
```

### Terraform Auth Failed

```routeros
# Verify user
/user print where name=terraform

# Reset password
/user set terraform password=NewPassword

# Check group permissions
/user group print where name=terraform
```

## Network After Terraform Apply

| Service | URL |
|---------|-----|
| WebFig | https://192.168.88.1 |
| REST API | https://192.168.88.1:8443 |
| WinBox | 192.168.88.1:8291 |

## Security Notes

1. Change default password immediately
2. Use strong passwords (16+ chars)
3. Restrict API access to management network after initial setup
4. Keep RouterOS updated
