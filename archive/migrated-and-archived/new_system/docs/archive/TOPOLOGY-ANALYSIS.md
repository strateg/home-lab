# Topology.yaml Analysis & Improvement Plan

## Current Structure Analysis

### ✅ What's Good

1. **Metadata Section** - Has version, environment, hardware info
2. **Single Source of Truth** - All infrastructure in one file
3. **Machine-Readable IDs** - Uses snake_case keys (wan, opnsense_lan)
4. **Comprehensive** - Covers physical, network, VMs, storage, services
5. **Well-Commented** - Clear descriptions throughout

### ⚠️ Issues vs Best Practices

| Issue | Current State | Best Practice | Impact |
|-------|---------------|---------------|---------|
| **No Physical/Logical Separation** | Mixed bridges, interfaces, networks | Separate `physical_topology` and `logical_topology` | Medium |
| **Missing Trust Zones** | No security boundaries defined | Add `trust_zones` section | High |
| **Inconsistent References** | Some use names, some IDs | Always use IDs for references | Medium |
| **No Device Hierarchy** | No racks/locations structure | Add `devices` with location hierarchy | Low |
| **Services Not Linked** | Services don't reference devices/networks | Use ID references | Medium |
| **No Validation** | No schema enforcement | Add validation schema | High |
| **Missing Author/Date in Metadata** | Only `last_updated` | Add `author`, `date` | Low |

## Proposed Improved Structure

```yaml
version: "2.0.0"

metadata:
  org: "home-lab"
  environment: "production"
  author: "dprohhorov"
  created: "2025-10-09"
  last_updated: "2025-10-09"
  description: "Home lab infrastructure topology - Dell XPS L701X"

physical_topology:
  # Physical hardware and location
  locations:
    - id: home
      type: home-lab

  devices:
    - id: gamayun
      type: hypervisor
      model: "Dell XPS L701X"
      location: home
      specs:
        cpu: "Intel Core i3-M370"
        cpu_cores: 2
        ram_gb: 8
        disks:
          - id: ssd-system
            device: sda
            size_gb: 180
            type: ssd
          - id: hdd-data
            device: sdb
            size_gb: 500
            type: hdd
      interfaces:
        - id: eth-usb
          type: usb-ethernet
          speed: 1000
          role: wan
        - id: eth-builtin
          type: pci-ethernet
          speed: 1000
          role: lan

    - id: slate-ax1800
      type: router
      model: "GL.iNet Slate AX (GL-AXT1800)"
      location: home
      role: gateway
      interfaces:
        - id: wan
          type: ethernet
        - id: lan
          type: ethernet
        - id: wlan0
          type: wifi-5ghz
        - id: wlan1
          type: wifi-2.4ghz

    - id: opnsense-fw
      type: vm-firewall
      runs_on: gamayun
      vmid: 100

logical_topology:
  # Network definitions with trust zones
  trust_zones:
    - id: untrusted
      name: "Untrusted Zone"
      description: "External networks (ISP)"
      security_level: 0

    - id: dmz
      name: "DMZ Zone"
      description: "OPNsense LAN facing GL.iNet"
      security_level: 1

    - id: internal
      name: "Internal Zone"
      description: "LXC containers and services"
      security_level: 2

    - id: management
      name: "Management Zone"
      description: "Infrastructure management"
      security_level: 3

    - id: user
      name: "User Zone"
      description: "End-user devices"
      security_level: 1

  networks:
    - id: net-wan
      name: "WAN"
      cidr: "192.168.1.0/24"
      gateway: "192.168.1.1"
      dns: ["1.1.1.1", "8.8.8.8"]
      trust_zone: untrusted
      bridge: vmbr0
      vlan: null
      dhcp: true
      description: "ISP provided network"

    - id: net-opnsense-lan
      name: "OPNsense LAN"
      cidr: "192.168.10.0/24"
      gateway: "192.168.10.1"
      dns: ["192.168.10.2"]
      trust_zone: dmz
      bridge: vmbr1
      vlan: null
      dhcp: false
      description: "Network between OPNsense and GL.iNet"

    - id: net-user-lan
      name: "User LAN"
      cidr: "192.168.20.0/24"
      gateway: "192.168.20.1"
      dns: ["192.168.20.1"]
      trust_zone: user
      managed_by: slate-ax1800
      vlan: null
      dhcp: true
      dhcp_range: "192.168.20.100-192.168.20.200"

    - id: net-lxc-internal
      name: "LXC Internal"
      cidr: "10.0.30.0/24"
      gateway: "10.0.30.254"
      dns: ["192.168.10.2"]
      trust_zone: internal
      bridge: vmbr2
      vlan: null
      dhcp: false

    - id: net-management
      name: "Management"
      cidr: "10.0.99.0/24"
      gateway: "10.0.99.1"
      dns: ["1.1.1.1", "8.8.8.8"]
      trust_zone: management
      bridge: vmbr99
      vlan: null
      dhcp: false

  bridges:
    - id: vmbr0
      device: gamayun
      comment: "WAN Bridge"
      ports: ["eth-usb"]
      address: "dhcp"
      network_ref: net-wan

    - id: vmbr1
      device: gamayun
      comment: "LAN Bridge"
      ports: ["eth-builtin"]
      address: "192.168.10.254/24"
      network_ref: net-opnsense-lan

    - id: vmbr2
      device: gamayun
      comment: "INTERNAL Bridge"
      ports: []
      address: "10.0.30.1/24"
      network_ref: net-lxc-internal

    - id: vmbr99
      device: gamayun
      comment: "MGMT Bridge"
      ports: []
      address: "10.0.99.1/24"
      network_ref: net-management

  routing:
    - id: route-lxc-internet
      name: "LXC to Internet"
      source_network: net-lxc-internal
      destination: "0.0.0.0/0"
      next_hop: "10.0.30.254"
      device: opnsense-fw

    - id: route-user-lxc
      name: "User to LXC Services"
      source_network: net-user-lan
      destination_network: net-lxc-internal
      via: opnsense-fw

  firewall_policies:
    - id: fw-default-deny
      name: "Default Deny"
      action: drop
      priority: 1000

    - id: fw-lxc-internet
      name: "LXC to Internet"
      source_zone: internal
      destination_zone: untrusted
      action: allow
      priority: 100

    - id: fw-user-lxc-services
      name: "User to LXC Services"
      source_zone: user
      destination_zone: internal
      ports: [80, 443, 5432, 6379]
      action: allow
      priority: 200

    - id: fw-guest-isolated
      name: "Guest Isolation"
      source_zone: user
      source_network: net-guest-wifi
      destination_zones: [internal, management]
      action: drop
      priority: 300

compute:
  # VMs and LXC containers
  vms:
    - id: opnsense-fw
      vmid: 100
      name: "opnsense-fw"
      device: gamayun
      type: firewall
      template_ref: tpl-opnsense
      trust_zone: dmz

      resources:
        cores: 2
        memory_mb: 2048
        balloon_mb: 1024

      storage:
        - disk: scsi0
          storage_ref: storage-lvm
          size_gb: 32

      networks:
        - interface: net0
          bridge: vmbr0
          network_ref: net-wan
          role: wan
        - interface: net1
          bridge: vmbr1
          network_ref: net-opnsense-lan
          ip: "192.168.10.1/24"
          role: lan
        - interface: net2
          bridge: vmbr2
          network_ref: net-lxc-internal
          ip: "10.0.30.254/24"
          role: internal
        - interface: net3
          bridge: vmbr99
          network_ref: net-management
          ip: "10.0.99.10/24"
          role: management

  lxc:
    - id: postgresql-db
      vmid: 200
      name: "postgresql-db"
      device: gamayun
      type: database
      template_ref: tpl-postgresql
      trust_zone: internal

      resources:
        cores: 2
        memory_mb: 2048
        swap_mb: 512

      storage:
        rootfs:
          storage_ref: storage-lvm
          size_gb: 8

      networks:
        - interface: eth0
          bridge: vmbr2
          network_ref: net-lxc-internal
          ip: "10.0.30.10/24"
          gateway: "10.0.30.254"

      services:
        - service_ref: svc-postgresql

storage:
  - id: storage-local
    type: dir
    path: "/var/lib/vz"
    content: ["vztmpl", "iso", "backup"]
    device: gamayun

  - id: storage-lvm
    type: lvmthin
    vgname: "pve"
    thinpool: "data"
    content: ["images", "rootdir"]
    device: gamayun
    disk_ref: ssd-system

  - id: storage-hdd
    type: dir
    path: "/mnt/hdd"
    content: ["backup", "iso", "vztmpl", "snippets"]
    device: gamayun
    disk_ref: hdd-data

services:
  # Service definitions with device and network references
  - id: svc-proxmox-ui
    name: "Proxmox Web UI"
    type: web-ui
    device_ref: gamayun
    network_ref: net-management
    ip: "10.0.99.1"
    port: 8006
    protocol: https
    trust_zone: management

  - id: svc-opnsense-ui
    name: "OPNsense Web UI"
    type: web-ui
    vm_ref: opnsense-fw
    network_ref: net-management
    ip: "10.0.99.10"
    port: 443
    protocol: https
    trust_zone: management

  - id: svc-postgresql
    name: "PostgreSQL Database"
    type: database
    lxc_ref: postgresql-db
    network_ref: net-lxc-internal
    ip: "10.0.30.10"
    port: 5432
    protocol: tcp
    trust_zone: internal

  - id: svc-adguard
    name: "AdGuard Home"
    type: dns
    device_ref: slate-ax1800
    network_ref: net-user-lan
    ip: "192.168.20.1"
    port: 3000
    protocol: http
    trust_zone: user

  - id: svc-vpn-home
    name: "WireGuard Home VPN"
    type: vpn
    device_ref: slate-ax1800
    network_ref: net-user-lan
    port: 51820
    protocol: udp
    trust_zone: user
    vpn_network: "10.0.200.0/24"
```

## Migration Strategy

### Phase 1: Analysis (Current)
- ✅ Document current structure
- ✅ Identify gaps vs best practices
- ✅ Design improved structure

### Phase 2: Schema Validation
- Create YAML schema for validation
- Add pre-commit hook for validation
- Test with existing topology

### Phase 3: Gradual Migration
- Add new sections (trust_zones, physical_topology)
- Keep old sections for compatibility
- Update generators to support both

### Phase 4: Full Migration
- Move all data to new structure
- Remove old sections
- Update all generators

### Phase 5: Automation
- Add automatic validation
- Generate diagrams from trust_zones
- Auto-generate firewall rules

## Benefits

1. **Security** - Clear trust zones enable better firewall rules
2. **Clarity** - Separation of physical/logical makes it easier to understand
3. **Validation** - Schema ensures correctness
4. **Automation** - Consistent IDs enable better code generation
5. **Scalability** - Easier to add new devices/networks
6. **Documentation** - Self-documenting through references

## Compatibility

- Keep old structure for now
- Generators read from both old and new sections
- Gradual migration path
- No breaking changes

## Next Steps

1. Create validation schema (JSON Schema or Pydantic)
2. Add trust_zones section to existing topology.yaml
3. Update validate-topology.py to check references
4. Gradually migrate sections
5. Update generators

---

**Status**: 📋 Analysis Complete - Ready for Implementation
**Priority**: Medium - Improves maintainability but not urgent
**Effort**: ~4-6 hours for full migration
