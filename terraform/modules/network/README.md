# Network Module

Creates and manages Proxmox network bridges for home lab infrastructure on Dell XPS L701X.

## Architecture

```
Dell XPS L701X Physical Interfaces:
├── USB-Ethernet (eth-usb)    → vmbr0 (WAN to ISP)
├── Built-in Ethernet (eth-builtin) → vmbr1 (LAN to OpenWRT)
└── WiFi (wlan0)               → Optional management

Proxmox Virtual Bridges:
├── vmbr0  - WAN Bridge (to ISP Router, DHCP)
├── vmbr1  - LAN Bridge (to OpenWRT, 192.168.10.0/24)
├── vmbr2  - INTERNAL Bridge (LXC, 10.0.30.0/24)
└── vmbr99 - MGMT Bridge (Management, 10.0.99.0/24)
```

## Network Topology

```
Internet
   ↓
ISP Router (192.168.1.1)
   ↓
vmbr0 (WAN) ← USB-Ethernet (eth-usb)
   ↓
OPNsense VM (vtnet0)
   ↓
vmbr1 (LAN, 192.168.10.0/24) ← Built-in Ethernet (eth-builtin)
   ├→ OPNsense (192.168.10.1)
   └→ OpenWRT (192.168.10.2)
      └→ Home Clients (192.168.20.0/24)

vmbr2 (INTERNAL, 10.0.30.0/24) ← Software bridge
   ├→ Proxmox host (10.0.30.1)
   ├→ LXC PostgreSQL (10.0.30.10)
   ├→ LXC Redis (10.0.30.20)
   └→ ... other LXC (10.0.30.30-90)
   Gateway: OPNsense (10.0.30.254)

vmbr99 (MGMT, 10.0.99.0/24) ← Software bridge
   ├→ Proxmox Web UI (10.0.99.1:8006)
   └→ OPNsense Web UI (10.0.99.10)
```

## Usage

```hcl
module "network" {
  source = "../../modules/network"

  # Node configuration
  node_name = var.proxmox_node_name

  # Physical interfaces (via udev rules)
  wan_interface = var.wan_interface       # "eth-usb"
  lan_interface = var.lan_interface       # "eth-builtin"
  wifi_interface = var.wifi_interface     # "wlan0"

  # Network CIDR blocks
  opnsense_lan_network_cidr     = "192.168.10.254/24"
  lxc_internal_proxmox_ip_cidr  = "10.0.30.1/24"
  mgmt_proxmox_ip_cidr          = "10.0.99.1/24"

  # Optional features
  enable_wifi_bridge = false
  enable_vlans       = false
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| node_name | Proxmox node name | `string` | n/a | yes |
| wan_interface | WAN interface name (USB-Ethernet) | `string` | `"eth-usb"` | no |
| lan_interface | LAN interface name (Built-in Ethernet) | `string` | `"eth-builtin"` | no |
| opnsense_lan_network_cidr | OPNsense LAN CIDR | `string` | `"192.168.10.254/24"` | no |
| lxc_internal_proxmox_ip_cidr | Proxmox IP on INTERNAL bridge | `string` | `"10.0.30.1/24"` | no |
| mgmt_proxmox_ip_cidr | Proxmox IP on MGMT bridge | `string` | `"10.0.99.1/24"` | no |
| enable_wifi_bridge | Enable WiFi bridge | `bool` | `false` | no |
| enable_vlans | Enable VLAN aware bridges | `bool` | `false` | no |

## Outputs

| Name | Description |
|------|-------------|
| wan_bridge | WAN bridge identifier ("vmbr0") |
| lan_bridge | LAN bridge identifier ("vmbr1") |
| internal_bridge | INTERNAL bridge identifier ("vmbr2") |
| mgmt_bridge | MGMT bridge identifier ("vmbr99") |
| network_summary | Complete network configuration summary |
| interface_mapping | Physical interface to bridge mapping |

## Bridge Details

### vmbr0 - WAN Bridge

- **Physical Port:** USB-Ethernet adapter (eth-usb via udev rule)
- **Purpose:** Connection to ISP Router
- **IP:** DHCP from ISP (no static IP on bridge)
- **Used by:** OPNsense WAN interface (vtnet0)

### vmbr1 - LAN Bridge

- **Physical Port:** Built-in Ethernet (eth-builtin via udev rule)
- **Purpose:** Connection to OpenWRT router
- **IP:** 192.168.10.254/24 (Proxmox)
- **Network:** 192.168.10.0/24
  - 192.168.10.1 - OPNsense LAN interface
  - 192.168.10.2 - OpenWRT WAN interface
  - 192.168.10.254 - Proxmox host
- **Used by:** OPNsense LAN interface (vtnet1)

### vmbr2 - INTERNAL Bridge

- **Physical Port:** None (software bridge)
- **Purpose:** LXC containers internal network
- **IP:** 10.0.30.1/24 (Proxmox)
- **Network:** 10.0.30.0/24
  - 10.0.30.1 - Proxmox host (direct LXC access)
  - 10.0.30.10-90 - LXC containers
  - 10.0.30.254 - OPNsense gateway (for internet)
- **Used by:** All LXC containers

### vmbr99 - MGMT Bridge

- **Physical Port:** None (software bridge)
- **Purpose:** Management and administration
- **IP:** 10.0.99.1/24 (Proxmox)
- **Network:** 10.0.99.0/24
  - 10.0.99.1 - Proxmox Web UI (https://10.0.99.1:8006)
  - 10.0.99.10 - OPNsense Web UI (https://10.0.99.10)
- **Used by:** OPNsense MGMT interface (vtnet3)

## Physical Interface Setup

### UDEV Rules for Interface Naming

Create `/etc/udev/rules.d/70-persistent-net.rules`:

```bash
# USB-Ethernet adapter (WAN)
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", \
  ATTR{address}=="XX:XX:XX:XX:XX:XX", NAME="eth-usb"

# Built-in Ethernet adapter (LAN)
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", \
  ATTR{address}=="YY:YY:YY:YY:YY:YY", NAME="eth-builtin"
```

Get MAC addresses:
```bash
ip link show
```

Apply udev rules:
```bash
udevadm control --reload-rules
udevadm trigger
```

## Networking Configuration

This module creates bridges, but actual routing configuration should be done via:

1. **Proxmox host** - `/etc/network/interfaces` (managed by Ansible)
2. **OPNsense** - Firewall rules and routing (managed by Ansible)
3. **OpenWRT** - Network configuration (managed by Ansible)

## Dependencies

- Proxmox Provider: `bpg/proxmox` >= 0.50.0
- Physical interfaces must exist and be named correctly (via udev rules)
- Proxmox node must be accessible via API

## Example: Full Configuration

```hcl
module "network" {
  source = "../../modules/network"

  node_name = "pve"

  # Dell XPS L701X interfaces
  wan_interface = "eth-usb"
  lan_interface = "eth-builtin"

  # Proxmox IPs on bridges
  opnsense_lan_network_cidr     = "192.168.10.254/24"
  lxc_internal_proxmox_ip_cidr  = "10.0.30.1/24"
  mgmt_proxmox_ip_cidr          = "10.0.99.1/24"
}

# Use module outputs in VM configuration
resource "proxmox_virtual_environment_vm" "opnsense" {
  # ...

  network_device {
    bridge = module.network.wan_bridge  # vmbr0
  }

  network_device {
    bridge = module.network.lan_bridge  # vmbr1
  }

  network_device {
    bridge = module.network.internal_bridge  # vmbr2
  }

  network_device {
    bridge = module.network.mgmt_bridge  # vmbr99
  }
}
```

## Notes

- USB-Ethernet adapter should be stable (use quality adapter)
- Ensure udev rules are applied before creating bridges
- Bridges will be created on Proxmox host, not inside VMs
- For VLAN support, set `enable_vlans = true`
- WiFi bridge is optional and disabled by default

## Troubleshooting

### Check bridge status

```bash
brctl show
ip link show type bridge
```

### Check interface status

```bash
ip link show eth-usb
ip link show eth-builtin
```

### Verify udev rules

```bash
udevadm info -a -p /sys/class/net/eth-usb
```

### Test connectivity

```bash
# From Proxmox host
ping 192.168.10.1  # OPNsense LAN
ping 10.0.30.254   # OPNsense INTERNAL

# From LXC container
ping 10.0.30.1     # Proxmox host
ping 10.0.30.254   # OPNsense gateway
ping 8.8.8.8       # Internet via OPNsense
```

## References

- [Proxmox Network Configuration](https://pve.proxmox.com/wiki/Network_Configuration)
- [Linux Bridge Configuration](https://wiki.archlinux.org/title/Network_bridge)
- [UDEV Persistent Network Device Names](https://wiki.archlinux.org/title/Network_configuration#Device_names)
