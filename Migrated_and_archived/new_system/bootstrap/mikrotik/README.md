# MikroTik Bootstrap Guide

This guide prepares MikroTik Chateau LTE7 ax for Terraform automation.

## Prerequisites

- MikroTik Chateau LTE7 ax with RouterOS 7.4+
- Access to router via WinBox, WebFig, or SSH
- USB SSD connected (for containers)

## Quick Start

### Option 1: Import Script

1. Download `bootstrap.rsc` to your computer
2. Connect to MikroTik via WinBox
3. Go to **Files** section
4. Upload `bootstrap.rsc`
5. Open **Terminal** and run:
   ```
   /import bootstrap.rsc
   ```
6. **Change the terraform password immediately!**

### Option 2: Manual Commands

Connect via Terminal (WinBox, WebFig, or SSH) and run:

```routeros
# 1. Create SSL certificate
/certificate add name=local-cert common-name=mikrotik.home.local days-valid=3650
/certificate sign local-cert

# 2. Enable REST API
/ip service set www-ssl certificate=local-cert disabled=no port=8443

# 3. Create Terraform user
/user group add name=terraform policy=api,read,write,policy,sensitive,test
/user add name=terraform group=terraform password=YOUR_SECURE_PASSWORD

# 4. Allow API access from management network
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=8443 \
    src-address=10.0.99.0/24 comment="Allow REST API"

# 5. Enable container mode (requires reboot)
/system/device-mode/update container=yes

# 6. Reboot
/system reboot
```

## Post-Bootstrap Steps

### 1. Configure USB Storage

After connecting USB SSD:

```routeros
# Format USB drive
/disk format-drive usb1 file-system=ext4 label=containers

# Create container directories
/file mkdir /usb1/containers
/file mkdir /usb1/containers/adguard
/file mkdir /usb1/containers/tailscale
```

### 2. Configure Terraform Variables

Copy and edit `terraform.tfvars`:

```bash
cd generated/terraform-mikrotik
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
mikrotik_host     = "https://192.168.88.1:8443"
mikrotik_username = "terraform"
mikrotik_password = "your_secure_password"  # Change this!
mikrotik_insecure = true  # For self-signed certificate
```

### 3. Test Connection

```bash
curl -k -u terraform:password https://192.168.88.1:8443/rest/system/identity
```

Expected response:
```json
{"name":"MikroTik-Chateau"}
```

### 4. Run Terraform

```bash
cd generated/terraform-mikrotik
terraform init
terraform plan
terraform apply
```

## Troubleshooting

### REST API Not Responding

1. Check service is enabled:
   ```routeros
   /ip service print where name=www-ssl
   ```

2. Check certificate is valid:
   ```routeros
   /certificate print
   ```

3. Check firewall rules:
   ```routeros
   /ip firewall filter print where dst-port=8443
   ```

### Container Mode Not Available

- Requires RouterOS 7.4 or later
- Check version: `/system resource print`
- Enable: `/system/device-mode/update container=yes`
- **Reboot required** after enabling

### USB Storage Issues

1. Check USB is detected:
   ```routeros
   /disk print
   ```

2. Format if needed:
   ```routeros
   /disk format-drive usb1 file-system=ext4
   ```

### Terraform Authentication Failed

1. Verify user exists:
   ```routeros
   /user print where name=terraform
   ```

2. Check user permissions:
   ```routeros
   /user group print where name=terraform
   ```

3. Reset password if needed:
   ```routeros
   /user set terraform password=new_password
   ```

## Security Notes

1. **Change default password immediately** after bootstrap
2. Consider restricting API access to management network only
3. Use strong passwords (min 16 characters, mixed case, numbers, symbols)
4. Regularly rotate credentials
5. Keep RouterOS updated

## Network Access After Bootstrap

After Terraform applies the full configuration:

| Service | URL |
|---------|-----|
| WebFig | https://192.168.88.1/ |
| REST API | https://192.168.88.1:8443/ |
| WinBox | 192.168.88.1:8291 |
| AdGuard | http://192.168.88.1:3000/ |
| WireGuard | 192.168.88.1:51820 (UDP) |

## Related Files

- `bootstrap.rsc` - RouterOS bootstrap script
- `generated/terraform-mikrotik/` - Generated Terraform configs
- `deploy/phases/01-network.sh` - Network deployment script
