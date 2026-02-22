---
adr: "0035"
layer: "L4"
scope: "host-os-foundation"
status: "Proposed"
date: "2026-02-22"
public_api:
  - "host_operating_systems[].id"
  - "lxc[].id"
  - "vms[].id"
breaking_changes: false
---

# ADR 0035: L4 Host OS Foundation and Runtime Substrate Contracts

- Status: Proposed
- Date: 2026-02-22

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Make `host_operating_systems` a first-class, validated L4 contract |
| Problem | Host OS facts are authored, but schema/validators do not enforce them |
| Public API | `host_operating_systems[].id`, `lxc[].id`, `vms[].id` |
| Breaking changes | None in phase-1 (additive) |
| Main risk | Partial adoption without validator guardrails |

## Context

`L4_platform` now contains `host_operating_systems` in composition root and module files, for example:

- `topology/L4-platform.yaml`
- `topology/L4-platform/host-operating-systems/hos-orangepi5-ubuntu.yaml`

Current contract gap:

1. `host_operating_systems` is present in topology data but not typed in `topology-v4-schema.json`.
2. ID collector and reference checks do not validate host OS objects.
3. Workload and service models rely on `device_ref`/`target_ref`, so host OS state is not part of runtime readiness checks.

Cross-layer dependency direction for this decision:

| Direction | Contract |
|---|---|
| L4 host OS -> L1 | `device_ref`, `installation.media_ref`, `installation.slot_ref` |
| L4 workloads -> L1/L2/L3 | Existing `device_ref`, `bridge_ref`, `network_ref`, `storage_endpoint_ref`, `data_asset_ref` |
| L5 services -> L4/L1 | Existing `runtime.target_ref` model stays unchanged |

## Alternatives Considered

| Option | Decision | Reason |
|---|---|---|
| A. Keep host OS as documentation-only YAML | Rejected | No machine-checked guarantees, drift risk grows |
| B. Move host OS inventory to L1 | Rejected | OS lifecycle is runtime/platform state, not physical underlay fact |
| C. Invert dependency and make L2 depend on L4 | Rejected | Creates cyclic semantics and breaks strict downward-layer model |
| D. Keep layer order, formalize host OS in L4 | Selected | Preserves existing architecture and adds enforceable runtime foundation |

## Decision

### D1. Host OS is a first-class L4 entity

Add typed schema support for `L4_platform.host_operating_systems[]` with stable ID pattern `hos-*`.

Minimum contract in v1:

- `id`
- `device_ref`
- `distribution`
- `status`
- `installation.media_ref` (optional when unknown)
- `installation.slot_ref` (optional when unknown)

### D2. Separate host OS from guest OS explicitly

L4 keeps two different OS concerns:

- Host OS lifecycle:
  - `host_operating_systems[]`
  - Example: Ubuntu on OrangePi5 NVMe
- Guest OS/runtime image intent:
  - `lxc[].os`, `vms[].os`, template image metadata

This keeps platform substrate facts (`host`) separate from workload image semantics (`guest`).

### D3. Keep runtime references backward-compatible in phase-1

No immediate breaking changes to existing runtime contracts:

- LXC/VM remain referenced by `lxc[].id` and `vms[].id`.
- L5 runtime keeps `runtime.target_ref`.

Add optional extension field in phase-1 schema:

- `lxc[].host_os_ref` (optional)
- `vms[].host_os_ref` (optional)

Validation behavior:

1. If `host_os_ref` exists, it must resolve to existing `host_operating_systems[].id`.
2. If both `host_os_ref` and `device_ref` exist, referenced host OS must belong to the same `device_ref`.
3. If a workload has `device_ref` and device has exactly one active host OS, omission of `host_os_ref` is allowed (warning-free).
4. If a workload has `device_ref` and device has multiple active host OS objects, missing `host_os_ref` is a warning in phase-1 and an error in phase-2.

### D4. Do not change layer dependency order

Layer model remains:

- `L0 -> L1 -> L2 -> L3 -> L4 -> L5 -> L6 -> L7`

Provisioning sequence in real operations (install OS, then configure network) does not require reversing architectural dependency direction. L2 continues to define logical network contract consumed by L4 workloads.

## Public API Contract (L4 v1)

| Entity | Visibility | Stability | Consumers |
|---|---|---|---|
| `host_operating_systems[].id` (`hos-*`) | Public | Stable v1 | L4 validators, docs, future runtime guardrails |
| `lxc[].id` (`lxc-*`) | Public | Stable v1 | L5 runtime, L6, L7 |
| `vms[].id` (`vm-*`) | Public | Stable v1 | L5 runtime, L6, L7 |
| `resource_profiles[]`, `templates.*`, `_defaults` | Internal | Mutable | L4 only |

Evolution policy:

1. Breaking changes to public IDs require a new ADR.
2. Deprecation window is one release cycle before removal.

## Migration Plan

### Phase-0: Contract Readiness

1. Add schema definition for `host_operating_systems`.
2. Extend ID collector with `host_operating_systems`.
3. Add reference validators for `host_os_ref` consistency rules.

### Phase-1: Additive Adoption

1. Keep all existing workload references valid.
2. Add `host_os_ref` only where ambiguity exists or where explicit substrate pinning is needed.
3. Add docs rendering for host OS inventory and workload-to-host-OS links when present.

### Phase-2: Strictness Upgrade

1. Promote missing `host_os_ref` to error only for ambiguous multi-OS-per-device cases.
2. Keep single-host-OS-per-device omission valid to minimize authoring overhead.

## Rollback

If phase-0 or phase-1 introduces regressions:

1. Revert schema and validator changes for `host_operating_systems`.
2. Keep authored topology objects as inert data (no strict checks).
3. Run:
   - `python topology-tools/validate-topology.py --strict`
   - `python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate`

## Toolchain Impact

| Component | Impact | Action |
|---|---|---|
| `topology-tools/schemas/topology-v4-schema.json` | Medium | Add typed `host_operating_systems` and optional `host_os_ref` |
| `topology-tools/scripts/validators/ids.py` | Low | Collect `hos-*` IDs |
| `topology-tools/scripts/validators/checks/references.py` | Medium | Add host OS reference and consistency checks |
| `topology-tools/scripts/generators/docs/generator.py` | Low | Render host OS inventory section and optional links |
| Terraform generators | None (phase-1) | Keep existing runtime generation path |

## Consequences

Benefits:

- Host OS facts become enforceable instead of informational.
- Clear host/guest OS separation reduces layer ambiguity.
- Extensibility for cloud nodes and mixed runtime substrates without changing L1/L2 contracts.

Trade-offs:

- Additional schema and validator complexity.
- More explicit references when devices have multiple host OS states.

Success metrics:

| Metric | Target |
|---|---|
| Host OS objects with valid `device_ref` | 100% |
| Invalid `host_os_ref` accepted in strict mode | 0 |
| Workload breakage after phase-1 rollout | 0 |
| Docs show host OS inventory deterministically | 100% |

## Ownership (RACI)

| Role | Party |
|---|---|
| Responsible | Topology maintainer |
| Accountable | Architecture owner |
| Consulted | L5/L6/L7 maintainers |
| Informed | Operations owner |

## References

- `topology/L4-platform.yaml`
- `topology/L4-platform/host-operating-systems/hos-orangepi5-ubuntu.yaml`
- `topology-tools/schemas/topology-v4-schema.json`
- `topology-tools/scripts/validators/ids.py`
- `topology-tools/scripts/validators/checks/references.py`
- `topology/MODULAR-GUIDE.md`
- [0032](0032-l3-data-modularization-and-layer-contracts.md)
- [0034](0034-l4-platform-modularization-and-runtime-taxonomy.md)
