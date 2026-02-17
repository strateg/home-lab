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

## Bootstrap (One-Time Setup)

Before Terraform can manage MikroTik, you must enable the REST API manually.

### Option 1: Import Script

1. Download `bootstrap/mikrotik/bootstrap.rsc` to your computer
2. Connect to MikroTik via WinBox
3. Go to **Files** → Upload `bootstrap.rsc`
4. Open **Terminal** and run:
   ```routeros
   /import bootstrap.rsc
   ```
5. **Change the terraform password immediately!**
   ```routeros
   /user set terraform password=YOUR_SECURE_PASSWORD
   ```
6. Reboot to enable container mode:
   ```routeros
   /system reboot
   ```

### Option 2: Manual Commands

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

### Verify REST API Access

```bash
curl -k -u terraform:YOUR_PASSWORD https://192.168.88.1:8443/rest/system/identity
# Expected: {"name":"MikroTik-Chateau"}
```

---

## Configuration

### 1. Configure terraform.tfvars

```bash
cd generated/terraform-mikrotik
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

# WireGuard Peers
wireguard_peers = [
  {
    name        = "phone"
    public_key  = "peer_public_key_here"
    allowed_ips = ["10.0.200.10/32"]
    comment     = "My Phone"
  },
  {
    name        = "laptop"
    public_key  = "peer_public_key_here"
    allowed_ips = ["10.0.200.11/32"]
    comment     = "My Laptop"
  }
]

# Containers
adguard_password  = ""  # bcrypt hash
tailscale_authkey = ""  # From Tailscale admin console
```

### 2. Generate WireGuard Keys

```bash
# Generate server private key
wg genkey > server_private.key

# Generate server public key (for clients)
cat server_private.key | wg pubkey > server_public.key

# Generate client keys
wg genkey | tee phone_private.key | wg pubkey > phone_public.key
```

---

## Deployment

### Initialize and Plan

```bash
cd generated/terraform-mikrotik
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

```hcl
# WireGuard interface
resource "routeros_interface_wireguard" "wg_home" {
  name        = "wireguard1"
  listen_port = 51820
  private_key = var.wireguard_private_key
}

# Dynamic peers from variable
resource "routeros_interface_wireguard_peer" "peers" {
  for_each = { for peer in var.wireguard_peers : peer.name => peer }

  interface       = routeros_interface_wireguard.wg_home.name
  public_key      = each.value.public_key
  allowed_address = each.value.allowed_ips
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
3. Re-run bootstrap script
4. Apply Terraform configuration

---

## Security Considerations

1. **Change default passwords** immediately after bootstrap
2. **Restrict API access** to management network only
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

**Last Updated**: 2026-02-17
