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
(`routeros_interface_wifi_*`). WiFi configuration is generated as an RSC script
and must be applied via SSH.

WiFi configuration is defined in topology at:
`projects/home-lab/topology/instances/devices/rtr-mikrotik-chateau.yaml`

### Applying WiFi Configuration

After compiling topology, the RSC script is generated at:
`generated/home-lab/terraform/mikrotik/wifi-config.rsc`

**Apply:**
```bash
scp generated/home-lab/terraform/mikrotik/wifi-config.rsc admin@192.168.88.1:
ssh admin@192.168.88.1 "/import wifi-config.rsc"

# Set WiFi passphrases
ssh admin@192.168.88.1 '/interface/wifi/security/set sec-wifi1 passphrase="YOUR_PASSWORD"'
ssh admin@192.168.88.1 '/interface/wifi/security/set sec-wifi2 passphrase="YOUR_PASSWORD"'

# Apply configurations to interfaces
ssh admin@192.168.88.1 '/interface/wifi/set wifi1 configuration=cfg-wifi1'
ssh admin@192.168.88.1 '/interface/wifi/set wifi2 configuration=cfg-wifi2'
```

The generated script creates:
- `dp-main-lan` datapath (bridges WiFi to main bridge, no VLAN)
- `dp-vpn-germany` datapath (bridges WiFi to bridge with VLAN 55)
- Security profiles for each SSID
- WiFi configurations for Chateau*, Chateau, VPN-Germany

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
