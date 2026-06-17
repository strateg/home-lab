# AI Rule Pack: Host Placement Defaults

> **Version:** 1.0 | **Updated:** 2026-06-17 | **ADRs:** 0107

## Quick Reference

| Rule | Key Point |
|------|-----------|
| workload_defaults | Define in host instance, NOT in object |
| @on:host.X | Inherit from immediate host_ref |
| @on:root.X | Inherit from physical device at chain root |
| Nested hosts | LXC/VM can define own workload_defaults |
| Instance override | Explicit value overrides @on resolution |

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

Use @on markers in object templates to inherit from host:

```yaml
# obj.proxmox.lxc.debian12.yaml
defaults:
  trust_zone_ref: @on:host.trust_zone_ref
  network:
    bridge_ref: @on:host.network.bridge_ref
    gateway: @on:host.network.gateway
  dns:
    nameserver: @on:host.dns.nameserver?
    searchdomain: @on:host.dns.searchdomain?:local
```

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
| Define defaults in object | Breaks host locality | Use workload_defaults in host |
| @on in instance file | Invalid context | Use only in object templates |
| Duplicate fields | Redundant, error-prone | Let @on inherit from host |
| Skip host_ref for workloads | Breaks @on resolution | Always set host_ref |

## Validation

```bash
task compile:default   # Resolves @on markers
task validate:default  # E6810-E6815 checks
```
