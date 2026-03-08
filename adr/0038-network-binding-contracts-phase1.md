---
adr: "0038"
layer: "L2, L4, L5"
scope: "network-binding-contracts-phase1"
status: "Accepted"
date: "2026-02-22"
public_api:
  - "L2 ip_allocations[].host_os_ref"
  - "L2 bridges[].host_os_ref"
breaking_changes: false
supersedes: "0037"
related:
  - "0035"
  - "0036"
  - "0037"
harmonized_with: "0064"
---

# ADR 0038: Network Binding Contracts Phase 1 (Gradual Evolution)

- Status: Accepted
- Date: 2026-02-22

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Add `host_os_ref` to L2 ip_allocations and runtime reachability validation |
| Approach | Gradual evolution (Phase 1 of Variant C from ADR 0037 analysis) |
| Problem | Runtime-to-network chain is not validated end-to-end |
| Main decision | Add minimal schema + validators; defer scope taxonomy to Phase 2 |
| Breaking changes | None (additive schema, warning-level validation) |
| Result | Validated runtime→network reachability without over-engineering |

## Context

### Harmonization Note (2026-03-09)

`host_os_ref` in this v4 ADR is treated as a legacy term for runtime OS ownership.
In v5 (ADR 0062 + ADR 0064), the same intent is modeled via OS instances:
- `class.os -> obj.os.* -> inst.os.*`
- device/workload binds OS via `os_refs[]`
- validation resolves network ownership against referenced OS instance(s)

### Problem Statement

L5 services define `runtime.target_ref` (device) and `runtime.network_binding_ref` (network), but there is no validation that the target device actually has an IP allocation in the referenced network:

```yaml
# L5-application/services.yaml
runtime:
  type: docker
  target_ref: orangepi5           # L1 device
  network_binding_ref: net-servers # L2 network
  # GAP: No validation that orangepi5 has IP in net-servers
```

### ADR 0037 Analysis

ADR 0037 proposed a comprehensive solution with:
- `scope: fabric|host|workload` in networks
- `managed_by_host_os_ref` in networks
- `parent_network_ref` in networks
- `host_os_ref` in ip_allocations and bridges
- End-to-end validation

After architectural review, this was deemed over-engineered for the current infrastructure (3 compute devices, single OS per device).

### Variant C Selected

Three variants were considered:

| Variant | Description | Decision |
|---|---|---|
| A | Minimal ADR 0037 (remove scope, keep host_os_ref) | Acceptable |
| B | Validation only (no schema changes) | Rejected: fragile, no multi-OS support |
| **C** | Gradual evolution (Phase 1 + Phase 2 triggers) | **Selected** |

Variant C provides immediate value (reachability validation) with explicit contracts (host_os_ref in schema) while deferring complexity (scope taxonomy) until needed.

## Decision

### D1. Add `host_os_ref` to L2 ip_allocations (Phase 1)

Extend `ip_allocations[]` with optional `host_os_ref`:

```yaml
# BEFORE (deprecated):
ip_allocations:
- ip: 10.0.30.50
  device_ref: orangepi5
  interface: eth0.30

# AFTER (recommended):
ip_allocations:
- ip: 10.0.30.50
  host_os_ref: hos-orangepi5-ubuntu
  interface: eth0.30
```

Schema rules:
- `host_os_ref` and `device_ref` are mutually exclusive alternatives
- `host_os_ref` must resolve to existing `host_operating_systems[].id`
- `device_ref` emits deprecation warning in Phase 1

### D2. Add `host_os_ref` to L2 bridges (optional)

```yaml
# bridge-vmbr0.yaml
id: bridge-vmbr0
device_ref: gamayun                    # Physical: which device has ports
host_os_ref: hos-gamayun-proxmox       # Logical: which OS manages bridge
```

Both fields serve different purposes:
- `device_ref`: Physical ownership (L1 ports, hardware)
- `host_os_ref`: Logical ownership (OS that configures the bridge)

### D3. Add runtime-to-network reachability validation

New validator `check_runtime_network_reachability()`:

```python
# For runtime.type in {docker, baremetal}:
# 1. Resolve target_ref to device
# 2. Find host_os for device (from host_operating_systems)
# 3. Check network_binding_ref has ip_allocation with matching host_os_ref
#    OR device_ref (for backward compatibility)
```

Phase 1: Emit WARNING for unreachable chains
Phase 2: Promote to ERROR

### D4. Add single-active-OS validation

Constraint: Maximum one `status: active` host_operating_systems per device.

```python
def check_single_active_os_per_device():
    # Collect active host OS per device
    # Error if any device has >1 active
```

This supports dual-boot scenarios where only one OS is active at a time.

### D5. Defer scope taxonomy to Phase 2

Do NOT add in Phase 1:
- `networks[].scope`
- `networks[].managed_by_host_os_ref`
- `networks[].parent_network_ref`

Rationale: Current `managed_by_ref` is sufficient for fabric-level ownership. Scope can be inferred:
- `managed_by_ref` to class=network device → fabric
- `bridge_ref` present → host-managed
- Neither → overlay/workload

### D6. Keep `runtime.target_ref` stable

Do NOT change L5 runtime contract in Phase 1:
- `target_ref` remains the public API
- Optional `host_os_ref` may be added in Phase 2 for disambiguation

## Phase 2 Triggers

Transition to Phase 2 when ANY of:

1. **Multi-OS per device**: Second `status: active` host_os added to same device
2. **Provider instances with OS variability**: Cloud instance rebuild with different OS
3. **Nested workload runtimes**: LXC with docker capability as runtime target

Phase 2 will:
- Promote reachability warnings to errors
- Require `host_os_ref` for ambiguous multi-OS scenarios
- Optionally add explicit `scope` taxonomy

## Schema Changes

### IpAllocation (updated)

```json
"IpAllocation": {
  "type": "object",
  "properties": {
    "ip": { "type": "string" },
    "host_os_ref": {
      "$ref": "#/definitions/HostOsRef",
      "description": "Host OS that owns this IP allocation"
    },
    "device_ref": {
      "$ref": "#/definitions/DeviceRef",
      "x-deprecated": "Use host_os_ref for semantic OS ownership"
    },
    "interface": { "type": "string" },
    "description": { "type": "string" }
  },
  "required": ["ip"],
  "oneOf": [
    { "required": ["host_os_ref"] },
    { "required": ["device_ref"] }
  ]
}
```

### Bridge (updated)

```json
"Bridge": {
  "properties": {
    "host_os_ref": {
      "$ref": "#/definitions/HostOsRef",
      "description": "Host OS that manages this bridge (optional, for explicit ownership)"
    }
  }
}
```

## Migration

### Data Migration (~15 lines)

| File | Changes |
|---|---|
| `L2-network/networks/net-servers.yaml` | 3 ip_allocations: device_ref → host_os_ref |
| `L2-network/networks/net-management.yaml` | 3 ip_allocations: device_ref → host_os_ref |
| `L2-network/networks/net-lan.yaml` | 3 ip_allocations: device_ref → host_os_ref |
| `L2-network/bridges/bridge-vmbr0.yaml` | Add host_os_ref (optional) |

### Mapping

| device_ref | host_os_ref |
|---|---|
| `mikrotik-chateau` | `hos-mikrotik-chateau-routeros` |
| `gamayun` | `hos-gamayun-proxmox` |
| `orangepi5` | `hos-orangepi5-ubuntu` |

## Toolchain Impact

| Component | Impact | Action |
|---|---|---|
| `topology-v4-schema.json` | Medium | Add IpAllocation definition with host_os_ref |
| `validators/checks/network.py` | High | Add check_ip_allocation_host_os_refs, check_runtime_network_reachability |
| `validators/checks/__init__.py` | Low | Export new validators |
| Terraform generators | None | No output changes |
| Ansible generators | None | No output changes |

## Consequences

### Benefits

- Validates runtime→network reachability (prevents configuration drift)
- Explicit `host_os_ref` contract aligns with ADR 0035 host OS model
- Backward compatible (device_ref still works with warning)
- Clear upgrade path to Phase 2

### Trade-offs

- One-time migration effort (~15 lines)
- Additional validator complexity
- Deprecation warnings until migration complete

### What This Does NOT Do

- Does not add `scope` taxonomy (deferred to Phase 2)
- Does not change L5 `runtime.target_ref` contract
- Does not require `host_os_ref` in L5 runtime
- Does not break existing topology files

## Success Metrics

| Metric | Target |
|---|---|
| ip_allocations with host_os_ref | 100% (after migration) |
| Runtime-to-network reachability warnings | 0 |
| Deprecation warnings (device_ref) | 0 (after migration) |
| Breaking changes | 0 |
| New validation errors | 0 (existing topology passes) |

## Ownership (RACI)

| Role | Party |
|---|---|
| Responsible | Topology maintainer |
| Accountable | Architecture owner |
| Consulted | Network admin |
| Informed | Operations owner |

## References

- [ADR 0035](0035-l4-host-os-foundation-and-runtime-substrates.md) - L4 host OS foundation
- [ADR 0036](0036-l2-host-os-reference-in-network-allocations.md) - Host OS reference proposal
- [ADR 0037](0037-l2-network-substrate-and-workload-binding-contracts.md) - Full binding contracts (superseded)
- `topology/L2-network/networks/net-servers.yaml`
- `topology/L4-platform/host-operating-systems/`
- `topology/L5-application/services.yaml`
