---
adr: "0036"
layer: "L2, L5"
scope: "host-os-network-reference"
status: "Proposed"
date: "2026-02-22"
public_api:
  - "L2 ip_allocations[].host_os_ref"
  - "L2 bridges[].host_os_ref"
  - "L5 runtime.host_os_ref"
breaking_changes: false
supersedes: null
related:
  - "0035"
  - "0030"
---

# ADR 0036: Host OS Reference in Network Allocations

- Status: Proposed
- Date: 2026-02-22

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Replace `device_ref` with `host_os_ref` in L2 network allocations |
| Problem | IP belongs to OS, not hardware; current `device_ref` is semantically incorrect |
| Solution | Minimal change: `ip_allocations[].host_os_ref`, `bridges[].host_os_ref` |
| Breaking changes | None (additive, deprecation period for `device_ref`) |
| Complexity | Low — no new structures, no new ID namespaces |

## Context

### Current State

L2 `ip_allocations` uses `device_ref` to track host IPs:

```yaml
# L2-network/networks/net-servers.yaml
ip_allocations:
  - ip: 10.0.30.2
    device_ref: gamayun           # Points to L1 device
    interface: vmbr0.30
```

L2 bridges embed management IP with implicit device ownership:

```yaml
# L2-network/bridges/bridge-vmbr0.yaml
device_ref: gamayun
address: 192.168.88.2/24          # Whose IP? The OS, not the hardware
```

L5 services target L1 devices directly:

```yaml
# L5-application/services.yaml
runtime:
  type: docker
  target_ref: orangepi5           # L1 device, not L4 host OS
```

### Problem

1. **Semantic mismatch**: IP addresses belong to operating systems, not physical hardware. A device with dual-boot has different IPs per OS.

2. **Missing link to ADR 0035**: L4 now has `host_operating_systems[]` as first-class entities, but L2 network bindings don't reference them.

3. **L5 inconsistency**: Services target L1 devices but should target L4 host OS for capability validation.

### Why NOT a Larger Restructuring?

An earlier draft proposed moving host IPs to L4 `network_attachments[]`. This was rejected because:

- It duplicates L2 data in L4
- Creates new ID namespaces (`attach-*`) without clear benefit
- Requires 3-phase migration for 3 hosts
- The real problem is a reference type, not data location

**The fix is semantic (reference type), not structural (data location).**

## Decision

### D1. Replace `device_ref` with `host_os_ref` in L2 ip_allocations

```yaml
# BEFORE:
ip_allocations:
  - ip: 10.0.30.2
    device_ref: gamayun

# AFTER:
ip_allocations:
  - ip: 10.0.30.2
    host_os_ref: hos-gamayun-proxmox
```

Validation rules:
- `host_os_ref` must resolve to existing `host_operating_systems[].id`
- Referenced host OS `device_ref` should match network's physical topology

### D2. Add optional `host_os_ref` to L2 bridges

```yaml
# BEFORE:
id: bridge-vmbr0
device_ref: gamayun
address: 192.168.88.2/24

# AFTER:
id: bridge-vmbr0
device_ref: gamayun                    # Physical: which device has ports
host_os_ref: hos-gamayun-proxmox       # Logical: which OS manages bridge
address: 192.168.88.2/24               # Management IP (stays in L2)
```

Both fields serve different purposes:
- `device_ref`: Physical ownership (L1 ports, hardware)
- `host_os_ref`: Logical ownership (OS that configures the bridge)

### D3. Replace `target_ref` with `host_os_ref` in L5 runtime

```yaml
# BEFORE:
runtime:
  type: docker
  target_ref: orangepi5

# AFTER:
runtime:
  type: docker
  host_os_ref: hos-orangepi5-ubuntu
```

This aligns with ADR 0035 capability validation — runtime type must match host OS capabilities.

### D4. No changes to L4 workloads

Current LXC/VM network definitions are sufficient:

```yaml
networks:
  - interface: eth0
    bridge_ref: bridge-vmbr0
    network_ref: net-servers
    ip: 10.0.30.10/24
```

The workload-to-host chain is already implicit:
1. `lxc-postgresql.device_ref: gamayun` identifies host device
2. `gamayun` has one active host OS: `hos-gamayun-proxmox`
3. Bridge and network are explicit

No `host_attachment_ref` or `network_attachments[]` needed.

### D5. Deprecation period for `device_ref` in ip_allocations

- Phase 1: Accept both `device_ref` and `host_os_ref` (warning if `device_ref` used)
- Phase 2: Require `host_os_ref`, reject `device_ref`

Timeline: One release cycle between phases.

## Layer Dependency Clarification

**Question**: Does L2 referencing L4 violate layer ordering?

**Answer**: No. Layer ordering restricts *schema dependency direction*, not data references.

- L2 schema does not require L4 schema to exist
- L2 files load independently
- References are validated at runtime

This is identical to how L4 `lxc[].network_ref` references L2 networks — data references across layers are normal.

## Public API Contract

| Entity | Visibility | Stability | Notes |
|---|---|---|---|
| `ip_allocations[].host_os_ref` | Public | Stable v1 | Replaces `device_ref` |
| `ip_allocations[].device_ref` | Deprecated | Phase-out | Use `host_os_ref` instead |
| `bridges[].host_os_ref` | Public | Stable v1 | Optional, for explicit ownership |
| `runtime.host_os_ref` | Public | Stable v1 | Replaces `target_ref` for OS-level runtimes |

## Migration

### One-Time Bulk Replace

No phased migration needed. Single commit:

1. Find all `ip_allocations[].device_ref` entries
2. Replace with corresponding `host_os_ref` value
3. Update bridges with `host_os_ref`
4. Update L5 services `target_ref` → `host_os_ref`
5. Run validators
6. Commit

### Affected Files

| File | Change |
|---|---|
| `L2-network/networks/net-servers.yaml` | `device_ref` → `host_os_ref` (3 entries) |
| `L2-network/networks/net-management.yaml` | `device_ref` → `host_os_ref` (3 entries) |
| `L2-network/networks/net-lan.yaml` | `device_ref` → `host_os_ref` (if present) |
| `L2-network/bridges/bridge-vmbr0.yaml` | Add `host_os_ref` |
| `L5-application/services.yaml` | `target_ref` → `host_os_ref` (where applicable) |

Total: ~15 line changes across ~5 files.

## Schema Changes

### L2 Network ip_allocations

```json
"IpAllocation": {
  "type": "object",
  "properties": {
    "ip": { "type": "string" },
    "host_os_ref": { "$ref": "#/definitions/HostOsRef" },
    "device_ref": {
      "$ref": "#/definitions/DeviceRef",
      "x-deprecated": "Use host_os_ref instead"
    },
    "interface": { "type": "string" },
    "description": { "type": "string" }
  },
  "oneOf": [
    { "required": ["ip", "host_os_ref"] },
    { "required": ["ip", "device_ref"] }
  ]
}
```

### L2 Bridge

```json
"Bridge": {
  "properties": {
    "host_os_ref": {
      "$ref": "#/definitions/HostOsRef",
      "description": "Host OS that manages this bridge"
    }
  }
}
```

### L5 Runtime

```json
"Runtime": {
  "properties": {
    "host_os_ref": { "$ref": "#/definitions/HostOsRef" },
    "target_ref": {
      "$ref": "#/definitions/DeviceRef",
      "x-deprecated": "Use host_os_ref for OS-level runtimes"
    }
  }
}
```

## Validator Changes

### New Checks

```python
def check_ip_allocation_host_os_refs(topology, ids, errors, warnings):
    """Validate ip_allocations host_os_ref resolves correctly."""
    l2 = topology.get('L2_network', {})
    host_os_ids = ids.get('host_operating_systems', set())

    for network in l2.get('networks', []) or []:
        net_id = network.get('id')
        for alloc in network.get('ip_allocations', []) or []:
            host_os_ref = alloc.get('host_os_ref')
            device_ref = alloc.get('device_ref')

            # Deprecation warning
            if device_ref and not host_os_ref:
                warnings.append(
                    f"Network '{net_id}': ip_allocations uses deprecated "
                    f"'device_ref: {device_ref}'. Use 'host_os_ref' instead."
                )

            # Validate host_os_ref
            if host_os_ref and host_os_ref not in host_os_ids:
                errors.append(
                    f"Network '{net_id}': ip_allocations host_os_ref "
                    f"'{host_os_ref}' does not exist"
                )
```

### Updated Checks

- `check_service_runtime_refs`: Validate `host_os_ref` resolves and has required capabilities
- `check_bridge_refs`: Validate optional `host_os_ref` if present

## Toolchain Impact

| Component | Impact | Action |
|---|---|---|
| `topology-v4-schema.json` | Low | Add `host_os_ref` to IpAllocation, Bridge, Runtime |
| `validators/checks/network.py` | Low | Add host_os_ref validation |
| `validators/checks/references.py` | Low | Update service runtime validation |
| `generators/terraform/*` | None | No output changes |
| `generators/ansible/*` | None | No output changes |

## Consequences

### Benefits

- Correct semantics: IP belongs to OS, not hardware
- Aligns with ADR 0035 host OS model
- Enables capability validation for L5 runtimes
- Minimal change, no new abstractions

### Trade-offs

- One-time migration effort (~15 lines)
- Deprecation period for `device_ref`

### What This Does NOT Do

- Does not move host IPs to L4 (stays in L2)
- Does not create `network_attachments[]` structure
- Does not add `host_attachment_ref` to workloads
- Does not require multi-phase migration

## Success Metrics

| Metric | Target |
|---|---|
| `ip_allocations` using `host_os_ref` | 100% |
| `ip_allocations` using deprecated `device_ref` | 0% (after phase 2) |
| L5 runtimes using `host_os_ref` | 100% (for OS-level types) |
| Validator errors from invalid refs | 0 |
| Generated output changes | 0 (semantic change only) |

## Ownership (RACI)

| Role | Party |
|---|---|
| Responsible | Topology maintainer |
| Accountable | Architecture owner |
| Consulted | Network admin |
| Informed | Operations owner |

## References

- `topology/L2-network/networks/net-servers.yaml`
- `topology/L2-network/bridges/bridge-vmbr0.yaml`
- `topology/L4-platform/host-operating-systems/hos-gamayun-proxmox.yaml`
- `topology/L5-application/services.yaml`
- [ADR 0030](0030-l2-network-layer-enhancements.md) - L2 network enhancements
- [ADR 0035](0035-l4-host-os-foundation-and-runtime-substrates.md) - L4 host OS foundation
