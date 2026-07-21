---
adr: "0037"
layer: "L2, L4, L5"
scope: "network-substrate-workload-binding"
status: "Superseded"
date: "2026-02-22"
public_api:
  - "L2 networks[].id"
  - "L2 networks[].scope"
  - "L2 ip_allocations[].host_os_ref (optional)"
  - "L4 lxc[].networks[].network_ref"
  - "L4 vms[].networks[].network_ref"
  - "L5 runtime.target_ref"
  - "L5 runtime.network_binding_ref"
breaking_changes: false
supersedes: null
superseded_by: "0038"
related:
  - "0030"
  - "0035"
  - "0036"
  - "0038"
---

# ADR 0037: L2 Network Substrate and Workload Binding Contracts

- Status: Superseded by [ADR 0038](0038-network-binding-contracts-phase1.md)

> **Note**: This ADR proposed a comprehensive solution. After architectural review,
> a gradual evolution approach (Phase 1) was selected and implemented in ADR 0038.
> This ADR is preserved for historical context.
- Date: 2026-02-22

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Keep L2 as canonical network contract and make runtime binding chain machine-checkable |
| Problem | Existing model validates references separately, but not end-to-end target-to-network reachability |
| Main decision | Add explicit L2 network scope + optional host OS ownership refs; keep `runtime.target_ref` stable |
| Breaking changes | None in phase-1 (additive schema + staged validators) |
| Result | Lower ambiguity for host, LXC/VM, and Docker networking without dependency inversion |

## Context

Current topology already has:

- L2 logical networks, bridges, firewall policies.
- L4 host OS objects (`host_operating_systems`) and workloads (`lxc`, `vms`).
- L5 runtime bindings (`runtime.target_ref`, `runtime.network_binding_ref`).

Current gaps:

1. `L5 runtime.network_binding_ref` is checked for existence, but not for compatibility with `runtime.target_ref`.
2. `L4 lxc/vms[].networks` are weakly typed (`array`), so `network_ref` is not schema-enforced.
3. `L2 ip_allocations` and `bridges` can represent host-level ownership only via `device_ref`, while ownership may be OS-specific.
4. L2 currently models underlay/virtual/overlay intent, but does not explicitly distinguish host-managed versus fabric-managed network scopes.

This causes ambiguity in multi-runtime scenarios (host OS + LXC + VM + Docker) even when each local reference is valid.

## Decision

### D1. Keep L2 as canonical network source of truth

L2 remains the owner of network segmentation and policy.
Do not move IP allocation or bridge ownership models to L4.

### D2. Add explicit network scope in L2

Extend `L2_network.networks[]` with:

- `scope`: `fabric | host | workload`
- `managed_by_host_os_ref` (optional, `hos-*`)
- `parent_network_ref` (optional, `net-*`)

Scope rules:

- `fabric`: infrastructure network managed by network-plane device (`managed_by_ref`, class `network`).
- `host`: host-local network managed by host OS (for example bridge/runtime host network).
- `workload`: network created for workload runtime on top of fabric/host substrate.

### D3. Keep `L5 runtime.target_ref` stable; do not replace with `host_os_ref`

`runtime.target_ref` remains the public contract:

- `lxc` -> `lxc-*`
- `vm` -> `vm-*`
- `docker`/`baremetal` -> `device_ref`

Add optional `runtime.host_os_ref` only for disambiguation (for example multiple active host OS entries on one device).
This keeps existing consumers stable and avoids broad breaking changes.

### D4. Add optional host OS ownership to L2 allocations and bridges

Add optional `host_os_ref` to:

- `networks[].ip_allocations[]`
- `bridges[]`

Policy:

- Keep `device_ref` for physical ownership/topology.
- Use `host_os_ref` when logical ownership must be explicit.
- If both are present, validator must enforce `host_os.device_ref == device_ref`.

### D5. Type L4 workload network attachments

Introduce typed schema objects for:

- `LxcNetworkAttachment`
- `VmNetworkAttachment`

Require at minimum:

- `network_ref`

Optional:

- `bridge_ref`
- `vlan_tag`
- `ip`
- `gateway`

### D6. Enforce end-to-end binding validation

Add chain checks:

1. `runtime.type=lxc` -> target LXC must have `networks[].network_ref == runtime.network_binding_ref`.
2. `runtime.type=vm` -> target VM must have `networks[].network_ref == runtime.network_binding_ref`.
3. `runtime.type=docker|baremetal` -> target device must have host-level presence in bound network through:
   - matching `ip_allocations` entry (`host_os_ref` or `device_ref`), or
   - bridge with matching ownership and network relation.
4. If `runtime.host_os_ref` is set, it must resolve and match target device.

### D7. Preserve layer dependency order

Layer order remains unchanged:

`L0 -> L1 -> L2 -> L3 -> L4 -> L5 -> L6 -> L7`

This ADR adds contracts and validations, not dependency inversion.

## Comparison with ADR 0036

| Topic | ADR 0036 | ADR 0037 (this ADR) | Outcome |
|---|---|---|---|
| L2 ownership semantics | Adds `host_os_ref` in allocations/bridges | Keeps same additive capability | Equivalent |
| L5 runtime contract | Replaces `target_ref` with `host_os_ref` | Keeps `target_ref`, adds optional `runtime.host_os_ref` | Lower break risk |
| Cross-layer validation | Focus on ref replacement | Adds explicit end-to-end reachability checks | Stronger correctness |
| L2 taxonomy | No explicit `scope` model | Adds `scope` + manager contract | Better extensibility |
| Migration cost | Low, but contract churn in L5 | Low, additive + staged strictness | Better compatibility |

## Alternatives Considered

### A. ADR 0036 direct replacement strategy

Rejected as primary path because replacing `runtime.target_ref` with `host_os_ref` expands change surface across L5 and toolchain without first fixing chain validation gaps.

### B. Move host network attachments to L4

Rejected because it duplicates network ownership and weakens L2 as canonical network/policy layer.

### C. Selected hybrid (this ADR)

Selected because it addresses semantic ownership and runtime reachability while preserving stable public contracts.

## Migration Plan

### Phase-0: Schema and validator readiness

1. Add `Network.scope`, optional `managed_by_host_os_ref`, optional `parent_network_ref`.
2. Add optional `host_os_ref` to `IpAllocation` and `Bridge`.
3. Add optional `runtime.host_os_ref` to `ServiceRuntime`.
4. Type `L4 lxc/vms[].networks` with concrete attachment definitions.
5. Add validators for ownership and target-to-network chain checks.

### Phase-1: Additive rollout

1. Keep existing data valid.
2. Start annotating host-owned entities with `host_os_ref`.
3. Add `scope` gradually (`fabric` default in existing networks).
4. Enable warnings for ambiguous runtime-to-network chains.

### Phase-2: Strictness upgrade

1. Promote unresolved runtime chain to error in strict mode.
2. Require `runtime.host_os_ref` only when target device has multiple active host OS objects.
3. Require explicit manager contract by `scope`:
   - `fabric` -> `managed_by_ref`
   - `host|workload` -> `managed_by_host_os_ref`

## Toolchain Impact

| Component | Impact | Action |
|---|---|---|
| `topology-tools/schemas/topology-v4-schema.json` | High | Add L2 scope/ownership fields; type L4 network attachments; add optional `runtime.host_os_ref` |
| `topology-tools/scripts/validators/checks/network.py` | High | Add scope manager rules and L2 ownership consistency checks |
| `topology-tools/scripts/validators/checks/references.py` | High | Add runtime target-to-network chain validation |
| `topology-tools/scripts/validators/ids.py` | Medium | Ensure host OS IDs reused consistently in new checks |
| Docs generator | Medium | Surface scope and host OS ownership where present |
| Terraform/Ansible generators | Low | No immediate output contract change in phase-1 |

## Consequences

Benefits:

- Keeps L2 contract coherent for both host-level and workload-level networking.
- Improves correctness by validating runtime reachability, not only ID existence.
- Preserves stable L5 runtime contract and minimizes migration risk.

Trade-offs:

- More validator logic and richer schema.
- Slightly higher authoring overhead when explicit host ownership is needed.

Success metrics:

| Metric | Target |
|---|---|
| Services with valid runtime target-to-network chain | 100% |
| L4 workloads with typed network attachments | 100% |
| Ambiguous host ownership in L2 allocations/bridges | 0 |
| Breaking changes for existing `runtime.target_ref` consumers | 0 |

## Ownership (RACI)

| Role | Party |
|---|---|
| Responsible | Topology maintainer |
| Accountable | Architecture owner |
| Consulted | Network and platform owners |
| Informed | Operations owner |

## References

- `adr/0030-l2-network-layer-enhancements.md`
- `adr/0035-l4-host-os-foundation-and-runtime-substrates.md`
- `adr/0036-l2-host-os-reference-in-network-allocations.md`
- `topology/L2-network.yaml`
- `topology/L4-platform.yaml`
- `topology/L5-application/services.yaml`
- `topology-tools/schemas/topology-v4-schema.json`
- `topology-tools/scripts/validators/checks/network.py`
- `topology-tools/scripts/validators/checks/references.py`
