---
adr: "0039"
layer: "L4"
scope: "host-os-installation-storage-contract"
status: "Accepted"
date: "2026-02-23"
public_api:
  - "host_operating_systems[].installation.root_storage_endpoint_ref"
breaking_changes: true
harmonized_with: "0064"
---

# ADR 0039: Host OS Installation Storage Contract (Strict)

- Status: Accepted
- Date: 2026-02-23

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Normalize host OS installation contract for L4/L3 |
| Decision | Keep only `installation.root_storage_endpoint_ref` |
| Breaking change | Remove `root_mount`, `media_ref`, `slot_ref` from host OS installation model |
| L3 prerequisite | Provide host root storage endpoints (`se-*-root`) |

## Context

### Harmonization Note (2026-03-09)

The storage-installation intent remains valid. Terminology is mapped for v5:
- `host_operating_systems[]` maps to OS entity chain `class.os -> obj.os.* -> inst.os.*`
- runtime binding to compute/router instances is instance-based (`os_refs[]`)
- installation storage linkage stays explicit via storage endpoint references

L4 host OS installation had mixed semantics:

- path-based field (`root_mount`),
- optional L1 physical hints (`media_ref`, `slot_ref`),
- and L3 logical placement.

This caused duplicate representation and weak machine validation. The L3 public contract already provides stable IDs through `storage_endpoints`.

## Decision

### D1. Single L4 installation reference

`host_operating_systems[].installation` contains one field:

- `root_storage_endpoint_ref` -> L3 `storage_endpoints[].id`.

### D2. Strict field removal

Removed from host OS installation contract:

- `root_mount`
- `media_ref`
- `slot_ref`

This is intentional and breaking.

### D3. Host root modeled as L3 endpoints

L3 must expose host root endpoints for runtime hosts:

- `se-gamayun-root`
- `se-orangepi5-root`

### D4. Validation rules

For `host_type` in `{baremetal, hypervisor}`:

1. `installation` is required.
2. `installation.root_storage_endpoint_ref` is required.
3. endpoint must exist in L3 `storage_endpoints`.
4. if endpoint has `mount_point_ref.device_ref`, it must match host `device_ref`.

For `host_type: embedded`:

- `installation` remains optional.

## Implementation

Implemented in topology and tooling:

1. Added host-root endpoints in `topology/L3-data/storage-endpoints/`.
2. Added Orange Pi root chain entities (`partitions`, `filesystems`, `mount_points`).
3. Migrated `hos-*` objects to `root_storage_endpoint_ref`.
4. Updated schema and validators to strict mode.
5. Updated docs template rendering for installation block.

## Verification

- `python topology-tools/validate-topology.py --strict` passes.
- `python topology-tools/validate-topology.py --strict --topology topology-tools/fixtures/new-only/topology.yaml` passes.

## Consequences

Benefits:

- deterministic ID-based cross-layer contract,
- no duplicate host root semantics,
- clearer ownership of physical chain in L3.

Trade-offs:

- breaking change for any old host OS installation payloads.

## Ownership (RACI)

| Role | Party |
|---|---|
| Responsible | Topology maintainer |
| Accountable | Architecture owner |
| Consulted | L3/L4 maintainers |
| Informed | Tooling and docs consumers |

## References

- [0032](0032-l3-data-modularization-and-layer-contracts.md)
- [0035](0035-l4-host-os-foundation-and-runtime-substrates.md)
- `topology/L4-platform/host-operating-systems/hos-gamayun-proxmox.yaml`
- `topology/L4-platform/host-operating-systems/hos-orangepi5-ubuntu.yaml`
- `topology/L3-data/storage-endpoints/se-gamayun-root.yaml`
- `topology/L3-data/storage-endpoints/se-orangepi5-root.yaml`
- `topology-tools/schemas/topology-v4-schema.json`
- `topology-tools/scripts/validators/checks/references.py`
- `topology-tools/templates/docs/devices.md.j2`
