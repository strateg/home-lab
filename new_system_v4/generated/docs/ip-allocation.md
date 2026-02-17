# IP Address Allocation

**Generated from**: topology.yaml v4.0.0
**Date**: 2026-02-17 19:13:20

---

## Network Summary

Total networks: **9**

| Network ID | CIDR | Gateway | VLAN | Trust Zone |
|------------|------|---------|------|------------|
| net-wan | dhcp | dhcp | None | untrusted |
| net-lte-failover | dhcp | dhcp | None | untrusted |
| net-lan | 192.168.88.0/24 | 192.168.88.1 | None | user |
| net-servers | 10.0.30.0/24 | 10.0.30.1 | 30 | servers |
| net-guest | 192.168.30.0/24 | 192.168.30.1 | 50 | guest |
| net-iot | 192.168.40.0/24 | 192.168.40.1 | 40 | iot |
| net-management | 10.0.99.0/24 | 10.0.99.1 | 99 | management |
| net-vpn-home | 10.0.200.0/24 | 10.0.200.1 | None | user |
| net-tailscale | 100.64.0.0/10 | None | None | user |

---

## IP Allocations

Total allocated IPs: **12**

| IP Address | Device | Network | Interface | Description |
|------------|--------|---------|-----------|-------------|
| 10.0.200.1 | mikrotik-chateau | net-vpn-home | wireguard1 | WireGuard server |
| 10.0.30.1 | mikrotik-chateau | net-servers | vlan30 | MikroTik servers gateway |
| 10.0.30.2 | gamayun | net-servers | vmbr0.30 | Proxmox bridge IP |
| 10.0.30.50 | orangepi5 | net-servers | eth0.30 | Orange Pi 5 server interface |
| 10.0.99.1 | mikrotik-chateau | net-management | vlan99-mgmt | MikroTik management gateway |
| 10.0.99.2 | gamayun | net-management | vmbr0.99 | Proxmox Web UI |
| 10.0.99.3 | orangepi5 | net-management | eth0.99 | Orange Pi 5 management |
| 192.168.30.1 | mikrotik-chateau | net-guest | vlan50-guest | MikroTik guest gateway |
| 192.168.40.1 | mikrotik-chateau | net-iot | vlan40-iot | MikroTik IoT gateway |
| 192.168.88.1 | mikrotik-chateau | net-lan | bridge-lan | MikroTik LAN gateway |
| 192.168.88.2 | gamayun | net-lan | eth0 | Proxmox host |
| 192.168.88.3 | orangepi5 | net-lan | eth0 | Orange Pi 5 application server |

---

## Allocations by Network

### net-wan (dhcp)

**Trust Zone**: untrusted
**Gateway**: dhcp

*No allocations defined*

---

### net-lte-failover (dhcp)

**Trust Zone**: untrusted
**Gateway**: dhcp

*No allocations defined*

---

### net-lan (192.168.88.0/24)

**Trust Zone**: user
**Gateway**: 192.168.88.1

| IP Address | Device | Interface | Description |
|------------|--------|-----------|-------------|
| 192.168.88.1 | mikrotik-chateau | bridge-lan | MikroTik LAN gateway |
| 192.168.88.2 | gamayun | eth0 | Proxmox host |
| 192.168.88.3 | orangepi5 | eth0 | Orange Pi 5 application server |

---

### net-servers (10.0.30.0/24)

**Trust Zone**: servers
**Gateway**: 10.0.30.1
**VLAN**: 30

| IP Address | Device | Interface | Description |
|------------|--------|-----------|-------------|
| 10.0.30.1 | mikrotik-chateau | vlan30 | MikroTik servers gateway |
| 10.0.30.2 | gamayun | vmbr0.30 | Proxmox bridge IP |
| 10.0.30.50 | orangepi5 | eth0.30 | Orange Pi 5 server interface |

---

### net-guest (192.168.30.0/24)

**Trust Zone**: guest
**Gateway**: 192.168.30.1
**VLAN**: 50

| IP Address | Device | Interface | Description |
|------------|--------|-----------|-------------|
| 192.168.30.1 | mikrotik-chateau | vlan50-guest | MikroTik guest gateway |

---

### net-iot (192.168.40.0/24)

**Trust Zone**: iot
**Gateway**: 192.168.40.1
**VLAN**: 40

| IP Address | Device | Interface | Description |
|------------|--------|-----------|-------------|
| 192.168.40.1 | mikrotik-chateau | vlan40-iot | MikroTik IoT gateway |

---

### net-management (10.0.99.0/24)

**Trust Zone**: management
**Gateway**: 10.0.99.1
**VLAN**: 99

| IP Address | Device | Interface | Description |
|------------|--------|-----------|-------------|
| 10.0.99.1 | mikrotik-chateau | vlan99-mgmt | MikroTik management gateway |
| 10.0.99.2 | gamayun | vmbr0.99 | Proxmox Web UI |
| 10.0.99.3 | orangepi5 | eth0.99 | Orange Pi 5 management |

---

### net-vpn-home (10.0.200.0/24)

**Trust Zone**: user
**Gateway**: 10.0.200.1

| IP Address | Device | Interface | Description |
|------------|--------|-----------|-------------|
| 10.0.200.1 | mikrotik-chateau | wireguard1 | WireGuard server |

---

### net-tailscale (100.64.0.0/10)

**Trust Zone**: user

*No allocations defined*

---


## Reserved Addresses


---

**DO NOT EDIT MANUALLY** - Regenerate with `python3 scripts/generate-docs.py`