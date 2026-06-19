---
@pack: host-placement
@version: 1.1
@tokens: ~800
@adr: [0107]
---

# AI Rule Pack: Host Placement Defaults

## Quick Reference

| Rule | Key Point |
|------|-----------|
| workload_defaults | Define in host instance, NOT in object |
| @on in object defaults | Put @on markers in object template `defaults:` section |
| @on:host.X | Inherit from immediate host_ref |
| @on:root.X | Inherit from physical device at chain root |
| Nested hosts | LXC/VM can define own workload_defaults |
| Instance override | Explicit value overrides @on resolution |
| Deep merge | Object defaults merged with instance data |

## Load When

- Working with `workload_defaults` in host instances
- Adding `@on:host` or `@on:root` directives in objects
- Debugging E6810-E6815 errors
- Creating new host or workload instances

## @on Directive Syntax

```yaml
@on:<source>.<path>[?][:<default>]
```

| Source | Meaning |
|--------|---------|
| `host` | Immediate host (via host_ref) |
| `root` | Physical device at chain root |
| `host[N]` | N levels up (host[1] = immediate) |

| Modifier | Meaning |
|----------|---------|
| `?` | Optional (no error if missing) |
| `:<value>` | Fallback default if path not found |

## workload_defaults Structure

Define in host instance (e.g., `srv-gamayun.yaml`):

```yaml
@instance: srv-gamayun
@extends: obj.proxmox.ve

workload_defaults:
  trust_zone_ref: inst.trust_zone.servers
  network:
    bridge_ref: inst.bridge.vmbr0
    vlan_ref: inst.vlan.servers
    gateway: 10.0.30.1
  dns:
    nameserver: 192.168.88.1
    searchdomain: home.local
  storage:
    default_pool_ref: inst.storage.pool.local_lvm
  ansible:
    enabled: true
```

## Object Template Usage

Use @on markers in object `defaults:` section to inherit from host:

```yaml
# obj.proxmox.lxc.debian12.base.yaml
@object: obj.proxmox.lxc.debian12.base
@version: 1.1.0

defaults:
  trust_zone_ref: "@on:host.trust_zone_ref?"
  network:
    interface: "@on:host.network.interface?:eth0"
    bridge_ref: "@on:host.network.bridge_ref?"
    vlan_ref: "@on:host.network.vlan_ref?"
    gateway: "@on:host.network.gateway?"
    firewall: "@on:host.network.firewall?:false"
  dns:
    nameserver: "@on:host.dns.nameserver?"
    searchdomain: "@on:host.dns.searchdomain?:local"
  storage:
    rootfs:
      pool_ref: "@on:host.storage.default_pool_ref?"
  cloudinit:
    enabled: "@on:host.cloudinit.enabled?:true"
  ansible:
    enabled: "@on:host.ansible.enabled?:true"
  boot:
    onboot: "@on:host.boot.onboot?:true"
```

**Important:** Quote @on values in YAML (`"@on:host.X"`) to prevent parsing issues.

## Resolution Order

1. Object template `defaults:` section is resolved first (lower priority)
2. Instance row data is resolved second (higher priority)
3. Results are deep merged (instance values override object defaults)

## Nested Host Resolution

For Docker-in-LXC scenarios:

```yaml
# lxc-docker.yaml (intermediate host)
workload_defaults:
  network:
    bridge_ref: inst.bridge.docker0
  dns:
    nameserver: @on:host.dns.nameserver  # From srv-gamayun

# docker-app.yaml
network:
  bridge_ref: @on:host.network.bridge_ref  # → docker0 (from lxc-docker)
dns:
  nameserver: @on:root.dns.nameserver      # → 192.168.88.1 (from srv-gamayun)
```

## Error Codes

| Code | Condition | Fix |
|------|-----------|-----|
| E6810 | Required @on path not in workload_defaults | Add path to host's workload_defaults |
| E6811 | Instance has no valid host_ref | Add host_ref to instance |
| E6812 | Circular host_ref chain | Fix host_ref cycle |
| E6813 | Cannot resolve root host | Check host_ref chain terminates |
| W6814 | Optional path not found | Add to workload_defaults or use default |
| E6815 | null override on @on field | Omit field or set explicit value |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Static values in object defaults | Breaks host locality | Use @on:host.X in defaults |
| @on in instance file | Invalid context | Use only in object templates |
| Duplicate fields in instances | Redundant, error-prone | Let @on inherit from host |
| Skip host_ref for workloads | Breaks @on resolution | Always set host_ref |
| @on outside defaults section | Won't resolve | Put @on in `defaults:` only |

## Testing

Integration tests: `tests/plugin_integration/test_on_directive_object_defaults.py`

Test cases:
1. Basic @on resolution from object defaults
2. Instance values override object defaults
3. Optional @on with default value
4. Deep merge of nested structures
5. No object defaults passes through

## Validation

```bash
task compile:default   # Resolves @on markers
task validate:default  # E6810-E6815 checks
```
