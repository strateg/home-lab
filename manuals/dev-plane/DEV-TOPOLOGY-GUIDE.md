# Topology Authoring Guide

Complete guide for authoring Class-Object-Instance topology definitions.

---

## Table of Contents

1. [Topology Model](#topology-model)
2. [Class Definitions](#class-definitions)
3. [Object Definitions](#object-definitions)
4. [Instance Bindings](#instance-bindings)
5. [Layer Structure](#layer-structure)
6. [Capabilities](#capabilities)
7. [Initialization Contracts](#initialization-contracts)
8. [Secrets Management](#secrets-management)
9. [Common Patterns](#common-patterns)
10. [Validation](#validation)

---

## Topology Model

### Three-Level Hierarchy (ADR 0062)

```
Class (Template)
    │
    └── Object (Concrete implementation)
            │
            └── Instance (Deployed entity)
```

| Level | Purpose | Example |
|-------|---------|---------|
| **Class** | Abstract template with schema | `cls.compute.lxc_container` |
| **Object** | Concrete implementation of class | `obj.proxmox.gamayun` |
| **Instance** | Deployed entity binding object | `lxc-adguard` on `pve-gamayun` |

### Directory Structure

```
topology/
├── topology.yaml              # Entry point
├── framework.yaml             # Framework manifest
├── module-index.yaml          # Module discovery
├── model.lock.yaml            # Version lock
├── layer-contract.yaml        # Layer definitions
├── capability-catalog.yaml    # Capability definitions
├── capability-packs.yaml      # Capability bundles
├── class-modules/             # Class definitions
│   ├── compute/
│   ├── network/
│   ├── device/
│   └── storage/
└── object-modules/            # Object definitions
    ├── proxmox/
    ├── mikrotik/
    └── orangepi/

projects/<project>/
├── project.yaml               # Project manifest
├── framework.lock.yaml        # Framework lock
├── topology/instances/        # Instance bindings
│   ├── L1-foundation/
│   ├── L2-network/
│   ├── L3-transport/
│   ├── L4-platform/
│   ├── L5-application/
│   ├── L6-observability/
│   └── L7-operations/
├── secrets/                   # SOPS secrets
└── deploy/                    # Deploy profile
```

---

## Class Definitions

### Location

```
topology/class-modules/<domain>/cls.<domain>.<name>.yaml
```

### Schema

```yaml
# topology/class-modules/compute/cls.compute.lxc_container.yaml

# Required metadata
class_id: cls.compute.lxc_container
version: "1.0.0"
description: "LXC container running on Proxmox VE"

# JSON Schema for instance properties
schema:
  type: object
  required:
    - vmid
    - hostname
    - cores
    - memory_mb
  properties:
    vmid:
      type: integer
      minimum: 100
      maximum: 999999
      description: "Proxmox VM ID"
    hostname:
      type: string
      pattern: "^[a-z][a-z0-9-]*$"
      minLength: 1
      maxLength: 63
      description: "Container hostname"
    cores:
      type: integer
      minimum: 1
      maximum: 128
      default: 1
    memory_mb:
      type: integer
      minimum: 128
      maximum: 524288
      default: 512
    disk_gb:
      type: integer
      minimum: 1
      maximum: 10000
      default: 8
    unprivileged:
      type: boolean
      default: true
    start_on_boot:
      type: boolean
      default: true
    network:
      type: object
      properties:
        bridge:
          type: string
          default: "vmbr0"
        ip:
          type: string
          format: ipv4
        gateway:
          type: string
          format: ipv4

# Capabilities this class provides
capabilities:
  - cap.compute
  - cap.container
  - cap.linux

# Required capabilities from host
requires_capabilities:
  - cap.hypervisor.proxmox

# Inheritance (optional)
extends: cls.compute.base
```

### Class Examples

#### Network VLAN Class

```yaml
# topology/class-modules/network/cls.network.vlan.yaml
class_id: cls.network.vlan
version: "1.0.0"
description: "VLAN network segment"

schema:
  type: object
  required:
    - vlan_id
    - name
    - cidr
  properties:
    vlan_id:
      type: integer
      minimum: 1
      maximum: 4094
    name:
      type: string
      pattern: "^[a-z][a-z0-9-]*$"
    cidr:
      type: string
      pattern: "^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+/[0-9]+$"
    gateway:
      type: string
      format: ipv4
    dhcp_enabled:
      type: boolean
      default: false
    dhcp_range:
      type: object
      properties:
        start:
          type: string
          format: ipv4
        end:
          type: string
          format: ipv4

capabilities:
  - cap.network
  - cap.vlan
```

#### Device Router Class

```yaml
# topology/class-modules/device/cls.device.mikrotik_router.yaml
class_id: cls.device.mikrotik_router
version: "1.0.0"
description: "MikroTik RouterOS device"

schema:
  type: object
  required:
    - management_ip
    - model
  properties:
    management_ip:
      type: string
      format: ipv4
    model:
      type: string
      enum:
        - chateau_lte7_ax
        - hap_ax2
        - rb5009
    api_port:
      type: integer
      default: 8729
    ssh_port:
      type: integer
      default: 22
    firmware_channel:
      type: string
      enum: [stable, long-term, testing]
      default: stable

capabilities:
  - cap.router
  - cap.firewall
  - cap.mikrotik
```

---

## Object Definitions

### Location

```
topology/object-modules/<domain>/obj.<domain>.<name>.yaml
```

### Schema

```yaml
# topology/object-modules/proxmox/obj.proxmox.gamayun.yaml

# Required metadata
object_id: obj.proxmox.gamayun
class_ref: cls.device.proxmox_host
version: "1.0.0"
description: "Proxmox VE hypervisor on Dell XPS L701X"

# Object-specific properties (class schema applied)
properties:
  management_ip: 10.0.99.1
  api_port: 8006
  node_name: pve
  storage_pools:
    - local-lvm
    - local
  cpu_model: Intel Core i7
  memory_total_gb: 8
  storage_total_gb: 680

# Initialization contract for bootstrap
initialization_contract:
  version: "1.0.0"
  mechanism: unattended_install
  bootstrap:
    template: bootstrap/answer.toml.j2
    post_install: bootstrap/post-install-minimal.sh
  requirements:
    - type: tool
      name: proxmox-iso
      required: true
  handover:
    checks:
      - type: api_reachable
        target: "https://{{ obj.management_ip }}:{{ obj.api_port }}"
      - type: ssh_reachable
        target: "{{ obj.management_ip }}"
        port: 22

# Object-level capabilities (added to class capabilities)
capabilities:
  - cap.storage.local
  - cap.network.bridge

# Tags for filtering
tags:
  - hypervisor
  - dell-xps
```

### Object Examples

#### MikroTik Router Object

```yaml
# topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml
object_id: obj.mikrotik.chateau_lte7_ax
class_ref: cls.device.mikrotik_router
version: "1.0.0"
description: "MikroTik Chateau LTE7 ax home router"

properties:
  management_ip: 192.168.88.1
  model: chateau_lte7_ax
  api_port: 8729
  ssh_port: 22
  firmware_channel: stable

initialization_contract:
  version: "1.0.0"
  mechanism: netinstall
  bootstrap:
    template: bootstrap/init-terraform.rsc.j2
  requirements:
    - type: tool
      name: netinstall
      required: true
  handover:
    checks:
      - type: api_reachable
        target: "https://{{ obj.management_ip }}:{{ obj.api_port }}"
      - type: ssh_reachable
        target: "{{ obj.management_ip }}"
        port: 22

capabilities:
  - cap.lte
  - cap.wifi6
```

#### Orange Pi SBC Object

```yaml
# topology/object-modules/orangepi/obj.orangepi.orangepi5.yaml
object_id: obj.orangepi.orangepi5
class_ref: cls.device.sbc
version: "1.0.0"
description: "Orange Pi 5 single-board computer"

properties:
  management_ip: 10.0.10.5
  soc: rk3588s
  memory_gb: 16
  storage_type: nvme
  storage_gb: 256

initialization_contract:
  version: "1.0.0"
  mechanism: ansible_bootstrap
  bootstrap:
    playbook: bootstrap/sbc-bootstrap.yml
  requirements:
    - type: ssh_access
      required: true
  handover:
    checks:
      - type: ssh_reachable
        target: "{{ obj.management_ip }}"
        port: 22
      - type: service_running
        target: docker

capabilities:
  - cap.docker
  - cap.arm64
```

---

## Instance Bindings

### Location

```
projects/<project>/topology/instances/<layer>/<domain>/<instance>.yaml
```

### Schema

```yaml
# projects/home-lab/topology/instances/L4-platform/compute/lxc-adguard.yaml

# Required metadata
instance_id: lxc-adguard
object_ref: obj.proxmox.gamayun
class_ref: cls.compute.lxc_container

# Binding-specific values (override object/class defaults)
binding:
  vmid: 101
  hostname: adguard
  cores: 1
  memory_mb: 512
  disk_gb: 4
  unprivileged: true
  start_on_boot: true
  network:
    bridge: vmbr0
    ip: 10.0.10.101
    gateway: 10.0.10.1

# Instance-specific capabilities
capabilities:
  - cap.dns
  - cap.adblock

# Service definitions
services:
  - name: adguard-home
    type: docker
    image: adguard/adguardhome:latest
    ports:
      - "53:53/tcp"
      - "53:53/udp"
      - "80:80/tcp"
      - "443:443/tcp"
      - "3000:3000/tcp"

# Tags for filtering
tags:
  - dns
  - adblock
  - network-services
```

### Instance Examples

#### Network VLAN Instance

```yaml
# projects/home-lab/topology/instances/L2-network/vlans/vlan-servers.yaml
instance_id: vlan-servers
object_ref: obj.mikrotik.chateau_lte7_ax
class_ref: cls.network.vlan

binding:
  vlan_id: 10
  name: servers
  cidr: 10.0.10.0/24
  gateway: 10.0.10.1
  dhcp_enabled: false

capabilities:
  - cap.server-network

tags:
  - infrastructure
  - servers
```

#### VM Instance

```yaml
# projects/home-lab/topology/instances/L4-platform/compute/vm-kubernetes.yaml
instance_id: vm-kubernetes
object_ref: obj.proxmox.gamayun
class_ref: cls.compute.proxmox_vm

binding:
  vmid: 200
  hostname: k8s-master
  cores: 4
  memory_mb: 8192
  disk_gb: 100
  network:
    bridge: vmbr0
    ip: 10.0.10.200
    gateway: 10.0.10.1

capabilities:
  - cap.kubernetes
  - cap.container-orchestration

tags:
  - kubernetes
  - orchestration
```

---

## Layer Structure

### OSI-Inspired Layers (L0-L7)

| Layer | Name | Purpose | Examples |
|-------|------|---------|----------|
| L0 | Physical | Hardware inventory | (not topology-managed) |
| L1 | Foundation | Hypervisors, base infra | pve-gamayun, rtr-mikrotik |
| L2 | Network | VLANs, bridges, routing | vlan-servers, bridge-lan |
| L3 | Transport | VPNs, tunnels, DNS | wireguard-home, dns-internal |
| L4 | Platform | Containers, VMs | lxc-adguard, vm-kubernetes |
| L5 | Application | Services, apps | nextcloud, homeassistant |
| L6 | Observability | Monitoring, logging | prometheus, grafana |
| L7 | Operations | Automation, backups | ansible-runner, backup-job |

### Layer Directory Structure

```
projects/home-lab/topology/instances/
├── L1-foundation/
│   ├── hypervisors/
│   │   └── pve-gamayun.yaml
│   ├── routers/
│   │   └── rtr-mikrotik-chateau.yaml
│   └── sbcs/
│       └── sbc-orangepi5.yaml
├── L2-network/
│   ├── vlans/
│   │   ├── vlan-servers.yaml
│   │   ├── vlan-users.yaml
│   │   └── vlan-iot.yaml
│   └── bridges/
│       └── bridge-lan.yaml
├── L3-transport/
│   ├── vpn/
│   │   └── wireguard-home.yaml
│   └── dns/
│       └── dns-internal.yaml
├── L4-platform/
│   ├── compute/
│   │   ├── lxc-adguard.yaml
│   │   ├── lxc-nginx.yaml
│   │   └── vm-kubernetes.yaml
│   └── storage/
│       └── nfs-share.yaml
├── L5-application/
│   ├── media/
│   │   └── jellyfin.yaml
│   └── home/
│       └── homeassistant.yaml
├── L6-observability/
│   ├── monitoring/
│   │   ├── prometheus.yaml
│   │   └── grafana.yaml
│   └── logging/
│       └── loki.yaml
└── L7-operations/
    ├── automation/
    │   └── ansible-runner.yaml
    └── backup/
        └── restic-backup.yaml
```

---

## Capabilities

### Capability Catalog

```yaml
# topology/capability-catalog.yaml
schema_version: "1.0"

capabilities:
  # Compute capabilities
  cap.compute:
    description: "Generic compute resource"
    category: compute

  cap.container:
    description: "Container runtime"
    category: compute
    requires: [cap.compute]

  cap.hypervisor:
    description: "Virtualization host"
    category: compute

  cap.hypervisor.proxmox:
    description: "Proxmox VE hypervisor"
    category: compute
    requires: [cap.hypervisor]

  # Network capabilities
  cap.network:
    description: "Network connectivity"
    category: network

  cap.router:
    description: "Network routing"
    category: network
    requires: [cap.network]

  cap.firewall:
    description: "Firewall functionality"
    category: network

  cap.vlan:
    description: "VLAN support"
    category: network
    requires: [cap.network]

  # Service capabilities
  cap.dns:
    description: "DNS resolution"
    category: service

  cap.docker:
    description: "Docker container runtime"
    category: service
    requires: [cap.container]
```

### Capability Packs

```yaml
# topology/capability-packs.yaml
schema_version: "1.0"

packs:
  pack.web-server:
    description: "Web server capability pack"
    capabilities:
      - cap.compute
      - cap.network
      - cap.http
      - cap.https

  pack.dns-server:
    description: "DNS server capability pack"
    capabilities:
      - cap.compute
      - cap.network
      - cap.dns

  pack.container-host:
    description: "Container hosting capability pack"
    capabilities:
      - cap.compute
      - cap.container
      - cap.docker
```

### Using Capabilities

```yaml
# In class definition
capabilities:
  - cap.compute
  - cap.container

requires_capabilities:
  - cap.hypervisor.proxmox

# In instance binding
capabilities:
  - cap.dns
  - cap.adblock
```

---

## Initialization Contracts

### Mechanisms

| Mechanism | Use Case | Bootstrap Artifacts |
|-----------|----------|---------------------|
| `netinstall` | MikroTik routers | `.rsc` scripts |
| `unattended_install` | Proxmox hosts | `answer.toml`, `post-install.sh` |
| `cloud_init` | VMs, LXC | `user-data`, `meta-data`, `network-config` |
| `ansible_bootstrap` | SBCs, servers | Ansible playbooks |

### Contract Schema

```yaml
initialization_contract:
  version: "1.0.0"
  mechanism: netinstall

  bootstrap:
    template: bootstrap/init-terraform.rsc.j2
    # Additional files for the mechanism
    files:
      - backup-restore-overrides.rsc

  requirements:
    - type: tool
      name: netinstall
      required: true
    - type: network
      name: direct-ethernet
      required: true

  handover:
    timeout: 300
    checks:
      - type: api_reachable
        target: "https://{{ obj.management_ip }}:{{ obj.api_port }}"
        timeout: 30
      - type: ssh_reachable
        target: "{{ obj.management_ip }}"
        port: 22
        timeout: 30
      - type: service_running
        target: api-ssl
```

### Handover Check Types

| Type | Description |
|------|-------------|
| `api_reachable` | HTTP(S) endpoint responds |
| `ssh_reachable` | SSH port accepts connections |
| `service_running` | Systemd/service is running |
| `file_exists` | File exists on target |
| `command_success` | Command exits with 0 |

---

## Secrets Management

### SOPS Structure

```
projects/home-lab/secrets/
├── .sops.yaml                 # SOPS configuration
├── terraform/
│   ├── proxmox.yaml           # Proxmox credentials
│   └── mikrotik.yaml          # MikroTik credentials
├── ansible/
│   └── vault.yaml             # Ansible secrets
└── services/
    └── credentials.yaml       # Service credentials
```

### SOPS Configuration

```yaml
# projects/home-lab/secrets/.sops.yaml
creation_rules:
  - path_regex: \.yaml$
    age: >-
      age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Using Secrets

```yaml
# In instance binding (passthrough mode)
binding:
  api_user: "{{ secrets.terraform.proxmox.api_user }}"
  api_token: "{{ secrets.terraform.proxmox.api_token }}"
```

### Secrets Mode

| Mode | Behavior |
|------|----------|
| `passthrough` | Keep placeholders (validation only) |
| `inject` | Decrypt and inject values |
| `strict` | Fail if secrets not available |

---

## Common Patterns

### Compute Instance Pattern

```yaml
instance_id: <hostname>
object_ref: obj.proxmox.<hypervisor>
class_ref: cls.compute.<type>

binding:
  vmid: <unique-id>
  hostname: <hostname>
  cores: <cores>
  memory_mb: <memory>
  disk_gb: <disk>
  network:
    bridge: vmbr0
    ip: <ip-address>
    gateway: <gateway>

capabilities:
  - <service-capabilities>

tags:
  - <category>
```

### Network VLAN Pattern

```yaml
instance_id: vlan-<name>
object_ref: obj.mikrotik.<router>
class_ref: cls.network.vlan

binding:
  vlan_id: <1-4094>
  name: <name>
  cidr: <network/mask>
  gateway: <gateway-ip>

capabilities:
  - cap.<purpose>-network
```

### Service Container Pattern

```yaml
instance_id: <service-name>
object_ref: obj.proxmox.<hypervisor>
class_ref: cls.compute.lxc_container

binding:
  vmid: <id>
  hostname: <hostname>
  cores: 1
  memory_mb: 512
  disk_gb: 8

services:
  - name: <service>
    type: docker
    image: <image>:<tag>
    ports:
      - "<host>:<container>/<protocol>"
    volumes:
      - "<host-path>:<container-path>"
    environment:
      KEY: value
```

---

## Validation

### Validate Topology

```bash
# Full validation
task validate:passthrough

# Layer contract only
task validate:layers
```

### Common Validation Errors

| Code | Cause | Fix |
|------|-------|-----|
| `E1001` | File not found | Check path exists |
| `E1003` | YAML parse error | Fix YAML syntax |
| `E2001` | Invalid reference | Check class_ref/object_ref |
| `E3001` | Schema validation failed | Check binding against class schema |
| `E3201` | Missing required field | Add required field |

### Schema Validation

All instance bindings are validated against their class schema:

```bash
# Class schema defines:
schema:
  required: [vmid, hostname]
  properties:
    vmid:
      type: integer
      minimum: 100

# Instance must satisfy:
binding:
  vmid: 101        # ✓ integer >= 100
  hostname: myhost # ✓ present
```

---

## Best Practices

### Naming Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Class | `cls.<domain>.<name>` | `cls.compute.lxc_container` |
| Object | `obj.<domain>.<name>` | `obj.proxmox.gamayun` |
| Instance | `<type>-<name>` | `lxc-adguard`, `vm-k8s` |
| VLAN | `vlan-<purpose>` | `vlan-servers` |
| Capability | `cap.<category>.<name>` | `cap.dns`, `cap.docker` |

### File Organization

- One class per file
- One object per file
- One instance per file
- Group by domain/purpose
- Use descriptive filenames

### Version Management

- Use semantic versioning for classes/objects
- Lock framework version in `framework.lock.yaml`
- Document breaking changes in ADRs

### Documentation

- Include `description` in all definitions
- Document non-obvious properties
- Explain capability requirements
