---
adr: "0039"
layer: "L4"
scope: "host-os-installation-storage-contract"
status: "Proposed"
date: "2026-02-23"
public_api:
  - "host_operating_systems[].installation.root_storage_endpoint_ref"
breaking_changes: true
---

# ADR 0039: Host OS Installation Storage Contract (Strict, No Legacy)

- Status: Proposed
- Date: 2026-02-23

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Define strict `installation` contract for host OS objects |
| Decision | Remove `root_mount`; require `root_storage_endpoint_ref` for `baremetal` and `hypervisor` |
| L1 facts | Keep optional `media_ref`, `slot_ref` |
| L3 contract | Create host-root `storage_endpoints` and reference them from L4 |
| Breaking change | Yes, legacy `root_mount` removed from schema and topology |

## Context

L4 host OS installation previously mixed:

- L1 physical facts (`media_ref`, `slot_ref`)
- L3 logical placement intent
- legacy path field `root_mount`

`root_mount` is not a stable cross-layer reference and duplicates L3 internal chain semantics. L4 must consume L3 public IDs, not path strings.

## Decision

### D1. L3 provides host-root storage endpoints

For each host with modeled root placement, L3 must expose a storage endpoint.

- `se-gamayun-root` -> `mount_point_ref: mnt-gamayun-root`
- `se-orangepi5-root` -> `mount_point_ref: mnt-orangepi5-root`

These endpoints are substrate access points, not `data_assets`.

### D2. L4 installation uses explicit layered references

`host_operating_systems[].installation` semantics:

| Field | Target layer | Purpose |
|---|---|---|
| `media_ref` | L1 | Physical install media |
| `slot_ref` | L1 | Physical slot/interface |
| `root_storage_endpoint_ref` | L3 | Logical root placement |

### D3. Remove legacy field

`installation.root_mount` is removed from schema and authoring model.

No compatibility mode. New format is mandatory.

### D4. Validation rules (strict)

For `host_type` in `{baremetal, hypervisor}`:

1. `installation` is required.
2. `installation.root_storage_endpoint_ref` is required.
3. `root_storage_endpoint_ref` must resolve to existing `storage_endpoints[].id`.
4. If resolved endpoint has `mount_point_ref.device_ref`, it must match host `device_ref`.
5. If `slot_ref` is set, it must exist in `device.specs.storage_slots`.

For `embedded`:

- `installation` remains optional.

## Implementation Status

Implemented in repository:

1. Added host-root endpoints:
   - `topology/L3-data/storage-endpoints/se-gamayun-root.yaml`
   - `topology/L3-data/storage-endpoints/se-orangepi5-root.yaml`
2. Added missing mount point:
   - `topology/L3-data/mount-points/mnt-orangepi5-root.yaml`
3. Migrated L4 host OS objects to `root_storage_endpoint_ref`.
4. Removed `root_mount` from JSON schema.
5. Extended validators with strict host OS installation checks.
6. Updated fixtures and docs template.

## Verification Checklist

- [x] Host-root endpoints exist in L3.
- [x] Baremetal/hypervisor host OS objects include `root_storage_endpoint_ref`.
- [x] Schema rejects `root_mount`.
- [x] Validator enforces endpoint existence and device consistency.
- [x] `python topology-tools/validate-topology.py --strict` passes.
- [x] `python topology-tools/validate-topology.py --strict --topology topology-tools/fixtures/new-only/topology.yaml` passes.

## Rollback

If rollback is required, revert this ADR and corresponding topology/schema/validator changes together in one commit. Partial rollback is not supported because schema and topology are now aligned to strict format.

## Consequences

Benefits:

- Clean layered contract with ID-based references.
- No duplicated root path semantics in L4.
- Deterministic validation of host root placement.

Trade-offs:

- Breaking change for any external inputs still using `root_mount`.

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

## Alternatives Considered

| Option | Decision | Reason |
|---|---|---|
| Keep `root_mount` as deprecated field | Rejected | Leaves dual model and weakens contract |
| Ban `media_ref`/`slot_ref` in L4 | Rejected | Removes valid L4 -> L1 install facts |
| Strict model: `media_ref`/`slot_ref` + required `root_storage_endpoint_ref` | Selected | Clear layered semantics and machine validation |
