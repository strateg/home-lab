# MikroTik Terraform Guide

This guide explains how to manage MikroTik RouterOS configuration using Terraform with the `terraform-routeros` provider.

---

## Overview

The home lab uses **MikroTik Chateau LTE7 ax** as the central router, configured entirely via Terraform from `topology.yaml`.

### What Gets Configured

| Category | Resources |
|----------|-----------|
| **Network** | Bridge, VLANs, ports, IP addresses |
| **DHCP** | Servers, pools, static leases |
| **DNS** | Settings, static records (via AdGuard) |
| **Firewall** | Filter rules, NAT, address lists |
| **QoS** | Queue trees, traffic prioritization |
| **VPN** | WireGuard interface and peers |
| **Containers** | AdGuard Home, Tailscale |

---

## Prerequisites

### Hardware Requirements

- MikroTik device with **RouterOS 7.4+** (for container support)
- **ARM64 or x86** architecture
- **USB storage** for containers (USB SSD recommended)

### Software Requirements

- Terraform 1.5+
- Python 3.8+ (for generators)

---

## Bootstrap (Day-0, One-Time Setup)

Terraform is the day-1 and day-2 owner. The target day-0 workflow is a control-node
Netinstall run that applies the generated bootstrap script and then hands over into
the normal Terraform flow.

### Preferred Path: Netinstall-First Bootstrap

1. Assemble the native execution workspace:
   ```bash
   cd deploy
   make assemble-native
   ```
2. Run preflight checks from the control node:
   ```bash
   make bootstrap-preflight RESTORE_PATH=minimal \
     MIKROTIK_NETINSTALL_INTERFACE=<install-interface> \
     MIKROTIK_NETINSTALL_CLIENT_IP=<client-ip> \
     MIKROTIK_ROUTEROS_PACKAGE=/path/to/routeros-arm64.npk \
     MIKROTIK_ROUTEROS_PACKAGE_SHA256=<sha256-optional>
   ```
3. Put the router into Etherboot or Netinstall mode, then run:
   ```bash
   make bootstrap-netinstall RESTORE_PATH=minimal \
     MIKROTIK_BOOTSTRAP_MAC=<router-mac> \
     MIKROTIK_NETINSTALL_INTERFACE=<install-interface> \
     MIKROTIK_NETINSTALL_CLIENT_IP=<client-ip> \
     MIKROTIK_ROUTEROS_PACKAGE=/path/to/routeros-arm64.npk
   ```
4. Validate handover and Terraform connectivity:
   ```bash
   make bootstrap-postcheck MIKROTIK_MGMT_IP=192.168.88.1 \
     MIKROTIK_TERRAFORM_PASSWORD_FILE=local/terraform/mikrotik/password.txt
   make bootstrap-terraform-check
   ```
5. Compatibility-only restore paths:
   - `RESTORE_PATH=backup` or `RESTORE_PATH=rsc`
   - require `ALLOW_NON_MINIMAL_RESTORE=true`

### Fallback Option 1: Manual Script Import

Use this when Netinstall is not available or you are recovering a router that is
already reachable over IP.

1. Run `cd deploy && make assemble-native`
2. Connect to MikroTik via WinBox
3. Go to **Files** and upload `.work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc`
4. Open **Terminal** and run:
   ```routeros
   /import init-terraform.rsc
   ```
5. If you imported a placeholder password, change it immediately:
   ```routeros
   /user set terraform password=YOUR_SECURE_PASSWORD
   ```

### Fallback Option 2: Manual Commands

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

# 5. Optional: enable container mode if the first Terraform apply needs it
/system/device-mode/update container=yes

# 6. Reboot if device mode changed
/system reboot
```

### Compatibility Helper: Legacy SSH Deployer

`topology-tools/scripts/deployers/mikrotik_bootstrap.py` remains available for
manual recovery or compatibility scenarios where the router is already reachable
over SSH. It is not the canonical ADR 0057 day-0 path.

### Verify REST API Access

```bash
curl -k --netrc-file local/terraform/mikrotik/api.netrc https://192.168.88.1:8443/rest/system/identity
# Expected: {"name":"MikroTik-Chateau"}
```

---

## Configuration

### 1. Configure terraform.tfvars

```bash
cd generated/home-lab/terraform/mikrotik
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
# MikroTik Connection
mikrotik_host     = "https://192.168.88.1:8443"
mikrotik_username = "terraform"
mikrotik_password = "your_secure_password"
mikrotik_insecure = true  # For self-signed certificate

# WireGuard VPN
wireguard_private_key = "generated_with_wg_genkey"

# WireGuard Peers (supports site-to-site and road-warrior)
wireguard_peers = [
  {
    name                 = "vps-oracle-frankfurt"
    public_key           = "peer_public_key_here"
    preshared_key        = "optional_psk_for_extra_security"
    endpoint_address     = "92.5.172.16"      # Server public IP
    endpoint_port        = 51820
    allowed_ips          = ["10.100.0.2/32", "0.0.0.0/0"]
    persistent_keepalive = "25s"              # Required for NAT traversal
    comment              = "Remote: vps-oracle-frankfurt"
  },
  {
    name        = "phone"
    public_key  = "peer_public_key_here"
    allowed_ips = ["10.0.200.10/32"]
    comment     = "My Phone"
  }
]

# Containers
adguard_password  = ""  # bcrypt hash
tailscale_authkey = ""  # From Tailscale admin console
```

### 2. Load Secrets from SOPS (Recommended)

Instead of manually editing `terraform.tfvars`, use SOPS-encrypted secrets:

```bash
cd generated/home-lab/terraform/mikrotik

# Extract MikroTik credentials
sops -d ../../../../projects/home-lab/secrets/terraform/mikrotik.yaml > terraform.tfvars

# Append WireGuard tunnel secrets
cat >> terraform.tfvars << 'EOF'

# WireGuard Configuration
EOF

# Extract WireGuard keys
sops -d ../../../../projects/home-lab/secrets/tunnels/wg-home-to-oci.yaml | \
  python3 -c "
import sys, yaml
data = yaml.safe_load(sys.stdin)
print(f'wireguard_private_key = \"{data[\"mikrotik\"][\"private_key\"]}\"')
print()
print('wireguard_peers = [')
print('  {')
print(f'    name                 = \"vps-oracle-frankfurt\"')
print(f'    public_key           = \"{data[\"vps\"][\"public_key\"]}\"')
print(f'    preshared_key        = \"{data[\"preshared_key\"]}\"')
print(f'    endpoint_address     = \"{data[\"vps\"][\"public_ip\"]}\"')
print(f'    endpoint_port        = 51820')
print(f'    allowed_ips          = [\"10.100.0.2/32\", \"0.0.0.0/0\"]')
print(f'    persistent_keepalive = \"25s\"')
print(f'    comment              = \"Remote: vps-oracle-frankfurt\"')
print('  }')
print(']')
" >> terraform.tfvars
```

### 3. Generate WireGuard Keys

```bash
# Generate server private key
wg genkey > server_private.key

# Generate server public key (for clients)
cat server_private.key | wg pubkey > server_public.key

# Generate client keys
wg genkey | tee phone_private.key | wg pubkey > phone_public.key

# Generate preshared key (optional, for extra security)
wg genpsk > preshared.key
```

---

## Deployment

### Initialize and Plan

```bash
cd .work/native/terraform/mikrotik
terraform init
terraform plan
```

### Apply Configuration

```bash
terraform apply
```

**WARNING**: This modifies your router configuration. Ensure you have:
- Console access (in case of lockout)
- Backup of current configuration

### Using Makefile

```bash
cd deploy
make plan-mikrotik    # Preview changes
make apply-mikrotik   # Apply with confirmation
```

---

## Generated Resources

### interfaces.tf

```hcl
# Bridge with VLAN filtering
resource "routeros_interface_bridge" "lan" {
  name           = "bridge-lan"
  vlan_filtering = true
  pvid           = 1
}

# Bridge ports (LAN1-4)
resource "routeros_interface_bridge_port" "lan1" {
  bridge    = routeros_interface_bridge.lan.name
  interface = "ether2"
  pvid      = 1
}

# VLANs
resource "routeros_interface_vlan" "vlan30" {
  name      = "vlan30"
  vlan_id   = 30
  interface = routeros_interface_bridge.lan.name
}
```

### firewall.tf

```hcl
# Address lists for easier management
resource "routeros_ip_firewall_addr_list" "lan_networks" {
  list    = "LAN"
  address = "192.168.88.0/24"
}

# Input chain rules
resource "routeros_ip_firewall_filter" "input_established" {
  chain            = "input"
  action           = "accept"
  connection_state = "established,related"
}

# NAT masquerade
resource "routeros_ip_firewall_nat" "masquerade" {
  chain         = "srcnat"
  action        = "masquerade"
  out_interface = "ether1"
}
```

### vpn.tf

Generated from topology WireGuard tunnel instances:

```hcl
locals {
  wireguard_interface_name = "wg0"
}

# WireGuard interface
resource "routeros_interface_wireguard" "wg0" {
  name        = local.wireguard_interface_name
  listen_port = 51820
  private_key = var.wireguard_private_key
  mtu         = 1420
  comment     = "WireGuard tunnel - managed by topology"
}

# WireGuard peer (site-to-site example)
resource "routeros_interface_wireguard_peer" "vps_oracle_frankfurt" {
  interface            = routeros_interface_wireguard.wg0.name
  public_key           = var.wireguard_peers[0].public_key
  preshared_key        = var.wireguard_peers[0].preshared_key
  endpoint_address     = var.wireguard_peers[0].endpoint_address
  endpoint_port        = var.wireguard_peers[0].endpoint_port
  allowed_address      = var.wireguard_peers[0].allowed_ips
  persistent_keepalive = var.wireguard_peers[0].persistent_keepalive
  comment              = "Remote: vps-oracle-frankfurt"
}

# WireGuard interface IP address
resource "routeros_ip_address" "wg0" {
  address   = "10.100.0.1/30"
  interface = routeros_interface_wireguard.wg0.name
  comment   = "WireGuard tunnel IP - managed by topology"
}

# Add WireGuard to LAN interface list (firewall trust)
resource "routeros_interface_list_member" "wg0_lan" {
  interface = routeros_interface_wireguard.wg0.name
  list      = "LAN"
  comment   = "Trust WireGuard tunnel - managed by topology"
}
```

### containers.tf

```hcl
# Container configuration
resource "routeros_container_config" "config" {
  registry_url = "https://registry-1.docker.io"
  ram_high     = "512M"
  tmpdir       = "/usb1/containers/tmp"
}

# AdGuard Home container
resource "routeros_container" "adguard" {
  remote_image  = "adguard/adguardhome:latest"
  interface     = routeros_interface_veth.adguard_veth.name
  root_dir      = "/usb1/containers/adguard/root"
  start_on_boot = true
}
```

---

## Network Topology

### VLANs

| VLAN ID | Name | CIDR | Purpose |
|---------|------|------|---------|
| 1 | LAN | 192.168.88.0/24 | Main LAN (untagged) |
| 30 | Servers | 10.0.30.0/24 | Server network |
| 40 | IoT | 192.168.40.0/24 | IoT devices (isolated) |
| 50 | Guest | 192.168.30.0/24 | Guest WiFi (isolated) |
| 99 | Management | 10.0.99.0/24 | Management access |

### Port Assignments

| Port | Connected Device | VLAN |
|------|-----------------|------|
| ether1 | WAN (Internet) | - |
| ether2 (LAN1) | Proxmox | Trunk (all VLANs) |
| ether3 (LAN2) | Orange Pi 5 | Trunk (all VLANs) |
| ether4 (LAN3) | Reserved | Access (VLAN 1) |
| ether5 (LAN4) | Reserved | Access (VLAN 1) |

---

## QoS Configuration

Traffic is prioritized using queue trees:

| Priority | Class | Guarantee | Max | Use Case |
|----------|-------|-----------|-----|----------|
| 1 | VoIP | 10% | 30% | Voice calls |
| 2 | Gaming | 15% | 40% | Low-latency games |
| 3 | Interactive | 20% | 50% | SSH, web browsing |
| 4 | Streaming | 25% | 60% | Video streaming |
| 5 | Web | 15% | 80% | General web |
| 6 | Bulk | 10% | 100% | Downloads, updates |
| 7 | Downloads | 5% | 100% | P2P, large transfers |

---

## Importing Existing Resources

If WireGuard is already configured on the router (e.g., via RSC script), import resources into Terraform state:

### 1. Find Resource IDs

```bash
# Get WireGuard interface ID
curl -sk -u terraform:PASSWORD https://192.168.88.1:8443/rest/interface/wireguard
# Example: [{".id":"*19", "name":"wg0", ...}]

# Get peer ID
curl -sk -u terraform:PASSWORD https://192.168.88.1:8443/rest/interface/wireguard/peers
# Example: [{".id":"*1", "interface":"wg0", ...}]

# Get IP address ID (filter by interface)
curl -sk -u terraform:PASSWORD https://192.168.88.1:8443/rest/ip/address | grep wg0
# Example: {".id":"*C", "address":"10.100.0.1/30", "interface":"wg0", ...}

# Get interface list member ID
curl -sk -u terraform:PASSWORD https://192.168.88.1:8443/rest/interface/list/member | grep wg0
# Example: {".id":"*4", "interface":"wg0", "list":"LAN", ...}
```

### 2. Import Resources

```bash
cd generated/home-lab/terraform/mikrotik

# Import WireGuard interface
terraform import routeros_interface_wireguard.wg0 "*19"

# Import peer
terraform import routeros_interface_wireguard_peer.vps_oracle_frankfurt "*1"

# Import IP address
terraform import routeros_ip_address.wg0 "*C"

# Import interface list member
terraform import routeros_interface_list_member.wg0_lan "*4"
```

### 3. Verify State

```bash
terraform plan -target=routeros_interface_wireguard.wg0 \
  -target=routeros_interface_wireguard_peer.vps_oracle_frankfurt \
  -target=routeros_ip_address.wg0 \
  -target=routeros_interface_list_member.wg0_lan

# Should show only minor changes (comments)
```

---

## Known Issues & Workarounds

### VRF Parameter Not Supported via REST API

**Problem**: При импорте существующих IP addresses в Terraform state, провайдер сохраняет атрибут `vrf: "main"`. При последующих PATCH запросах RouterOS 7.x возвращает ошибку:

```
Error: PATCH returned response code: 400, details: 'unknown parameter vrf'
```

**Причина**: VRF (Virtual Routing and Forwarding) — технология виртуализации таблиц маршрутизации. RouterOS поддерживает VRF, но REST API не позволяет изменять этот параметр через PATCH.

**Что такое VRF**:
| Аспект | Описание |
|--------|----------|
| Изоляция | Независимые таблицы маршрутизации на одном роутере |
| Multi-tenancy | Обслуживание клиентов с пересекающимися IP-адресами |
| Default | `vrf: "main"` — глобальная таблица (используется по умолчанию) |

**Решение**: В шаблонах добавлен lifecycle block:

```hcl
resource "routeros_ip_address" "example" {
  address   = "192.168.88.1/24"
  interface = "bridge"

  lifecycle {
    # vrf not supported via REST API in RouterOS 7.x
    ignore_changes = [vrf]
  }
}
```

**Для home lab**: VRF не нужен, достаточно игнорировать параметр.

---

### DHCP Server Requires dynamic_lease_identifiers

**Problem**: RouterOS 7.x требует параметр `dynamic_lease_identifiers` для DHCP серверов:

```
Error: PATCH returned response code: 400, details: 'failure: at least one dynamic lease identifier should be specified'
```

**Решение**: В шаблонах добавлен обязательный параметр:

```hcl
resource "routeros_ip_dhcp_server" "example" {
  name                       = "dhcp_server"
  interface                  = "bridge"
  address_pool               = "default-dhcp"
  dynamic_lease_identifiers  = "client-mac,client-id"  # Required!
}
```

---

## Troubleshooting

### REST API Not Responding

```routeros
# Check service status
/ip service print where name=www-ssl

# Check certificate
/certificate print

# Check firewall rules
/ip firewall filter print where dst-port=8443
```

### Container Mode Not Available

```routeros
# Check RouterOS version (requires 7.4+)
/system resource print

# Enable container mode
/system/device-mode/update container=yes
# Reboot required!
```

### Terraform Authentication Failed

```routeros
# Verify user exists
/user print where name=terraform

# Check permissions
/user group print where name=terraform

# Reset password
/user set terraform password=new_password
```

### USB Storage Issues

```routeros
# Check USB detection
/disk print

# Format if needed
/disk format-drive usb1 file-system=ext4 label=containers

# Create directories
/file mkdir /usb1/containers
```

---

## Backup and Recovery

### Before Applying Changes

```bash
# Create backup on MikroTik
ssh admin@192.168.88.1 "/export file=pre-terraform-backup"

# Download backup
scp admin@192.168.88.1:/pre-terraform-backup.rsc ./backups/
```

### Terraform State Backup

```bash
# Backup state file
cp terraform.tfstate terraform.tfstate.backup

# Or use remote backend (recommended for production)
```

### Recovery from Bad Configuration

If locked out:

1. Connect via serial console or Netinstall
2. Reset to defaults: `/system reset-configuration`
3. Re-run the preferred Netinstall path or a documented fallback bootstrap path
4. Apply Terraform configuration

---

## Security Considerations

1. **Change default passwords** immediately after bootstrap
2. **Restrict API access** to the intended Terraform/control-node subnet only
3. **Use strong passwords** (16+ characters, mixed case, numbers, symbols)
4. **Rotate credentials** regularly
5. **Keep RouterOS updated** for security patches
6. **Don't commit** `terraform.tfvars` to version control

---

## References

- [terraform-routeros Provider](https://registry.terraform.io/providers/terraform-routeros/routeros/latest/docs)
- [RouterOS REST API](https://help.mikrotik.com/docs/display/ROS/REST+API)
- [RouterOS Container](https://help.mikrotik.com/docs/display/ROS/Container)
- [WireGuard on RouterOS](https://help.mikrotik.com/docs/display/ROS/WireGuard)

---

**Last Updated**: 2026-06-19
