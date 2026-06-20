# MikroTik Terraform Configuration

## Router API Access

The MikroTik router exposes REST API on standard HTTPS port 443:

```hcl
mikrotik_host     = "https://192.168.0.17:443"
mikrotik_username = "automator"
mikrotik_insecure = true  # Self-signed certificate
```

### Service Configuration

| Service | Port | Purpose |
|---------|------|---------|
| www-ssl | 443 | REST API for Terraform |
| reverse-proxy | 9443 | Disabled (reserved for future nginx proxy) |

To verify API access:
```bash
curl -sk -u user:pass "https://192.168.0.17:443/rest/system/resource"
```

## WiFi Configuration

**Note:** The `routeros` Terraform provider does not support WiFi resources
(`routeros_interface_wifi_*`). WiFi configuration must be managed via SSH/RSC.

The files in this directory (`vpn_germany_wifi.tf`, `variables_wifi.tf`) are
kept for reference but cannot be applied via Terraform.

### Manual WiFi Setup (VPN Germany)

```routeros
# WiFi datapath with VLAN tagging
/interface/wifi/datapath/add name=dp-vpn-germany bridge=bridge vlan-id=55

# WiFi security profile
/interface/wifi/security/add name=sec-vpn-germany authentication-types=wpa2-psk wps=disable

# WiFi configuration
/interface/wifi/configuration/add name=cfg-vpn-germany ssid="VPN-Germany" mode=ap \
    security=sec-vpn-germany datapath=dp-vpn-germany

# Apply to interface
/interface/wifi/set wifi1 configuration=cfg-vpn-germany
```

## Terraform Usage

```bash
cd generated/home-lab/terraform/mikrotik/

# Create terraform.tfvars from secrets
# (see projects/home-lab/secrets/tunnels/wg-home-to-oci.yaml)

terraform init
terraform plan
terraform apply
```

## Idempotency

For existing routers, import resources before first apply:

```bash
# Get resource ID from router
ssh automator@192.168.0.17 ":put [/ip/pool/get [find name=vpn_germany_pool] .id]"

# Import into Terraform state
terraform import routeros_ip_pool.vpn_germany_pool '*7'
```
