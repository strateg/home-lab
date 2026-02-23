---
adr: "0039"
layer: "L4"
scope: "host-os-installation-storage-contract"
status: "Proposed"
date: "2026-02-23"
public_api:
  - "host_operating_systems[].installation.root_storage_endpoint_ref"
breaking_changes: false
---

# ADR 0039: Clarify Host OS Installation Storage Contract and Layer Boundary

- Status: Proposed
- Date: 2026-02-23

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Clarify `host_operating_systems[].installation` references across L1/L3 |
| Problem | `root_mount` in L4 duplicates L3 chain semantics and causes boundary confusion |
| Decision | Keep `media_ref`/`slot_ref` as optional L4 -> L1 install facts, use `root_storage_endpoint_ref` for L4 -> L3 root placement |
| Data contract | `data_assets` remain service data semantics only; host root/swap are substrate storage |
| Migration mode | Additive in phase-1, deprecate `root_mount` gradually |

## Context

Current host OS objects use:

- `installation.media_ref`
- `installation.slot_ref`
- `installation.root_mount`

Observed ambiguity:

1. Some readers interpret L3 public contract (`storage_endpoints`, `data_assets`) as a strict ban on any L4 -> L1 references.
2. `root_mount` in L4 (`"/"`) duplicates L3 internal chain (`mount_points -> filesystems -> logical_volumes -> partitions`) and does not provide stable reference semantics.
3. Host OS substrate concerns (root/swap on partitions) are being mixed with service data semantics (`data_assets`).

Existing contract direction (already present in ADR 0035 and ADR 0032):

- L4 host OS may reference L1 install media facts (`media_ref`, `slot_ref`).
- L4 -> L3 should use stable endpoint IDs when modeling root placement.
- `data_assets` are for data semantics/governance, not host substrate block layout.

## Decision

### D1. Keep two distinct reference classes in `installation`

`host_operating_systems[].installation` may contain:

- Optional L1 install target facts:
  - `media_ref`
  - `slot_ref`
- Optional L3 root placement contract:
  - `root_storage_endpoint_ref`

Rationale:

- `media_ref`/`slot_ref` answer "where OS was installed physically".
- `root_storage_endpoint_ref` answers "which logical storage endpoint represents host root placement".

These concerns are complementary, not conflicting.

### D2. Treat `root_mount` as legacy compatibility field

`installation.root_mount` is classified as legacy and should be replaced by `root_storage_endpoint_ref`.

Rationale:

- Path strings are not stable cross-layer IDs.
- L3 already owns mount/FS/LV/partition internals.
- `root_storage_endpoint_ref` provides a stable contract ID and validation target.

### D3. Keep host root/swap outside `data_assets`

Host root and swap remain substrate storage modeling, not application/service data assets.

Rules:

- Do not create `data_assets` for generic host root/swap placement by default.
- Keep swap modeling in L3 internal chain (`partitions` and related entities).
- Keep service data in `data_assets` and bind it via workload/service references.

### D4. Authoring and validation guidance

For `host_type` in `{baremetal, hypervisor}`:

1. `installation` remains required.
2. `root_storage_endpoint_ref` is strongly recommended and should become mandatory after migration window.
3. `media_ref` and `slot_ref` stay optional (unknown/abstract installs are valid).

For `host_type: embedded`:

1. `installation` remains optional.
2. If `installation` is present, same field semantics apply.

## Migration Plan

### Phase-1 (additive, current)

1. Keep schema compatibility with `root_mount`.
2. Add `root_storage_endpoint_ref` to host OS objects where root placement is modeled.
3. Keep `media_ref`/`slot_ref` unchanged where useful as L1 install facts.
4. Update docs examples to prefer `root_storage_endpoint_ref` over `root_mount`.

### Phase-2 (deprecation)

1. Validator warning when `root_mount` is used without `root_storage_endpoint_ref`.
2. Validator warning on newly added `root_mount` in changed files.

### Phase-3 (strict)

1. Remove `root_mount` from schema.
2. Remove template/docs rendering that treats `root_mount` as primary field.

## Consequences

Benefits:

- Clearer layer boundaries: L4 -> L1 install facts and L4 -> L3 logical placement are explicit.
- Reduced duplication with L3 storage chain.
- Better long-term stability through ID-based references.

Trade-offs:

- Transitional period with dual fields (`root_mount` + `root_storage_endpoint_ref`).
- Additional migration work for existing host OS objects and docs templates.

## References

- [0032](0032-l3-data-modularization-and-layer-contracts.md)
- [0035](0035-l4-host-os-foundation-and-runtime-substrates.md)
- `topology/L4-platform/host-operating-systems/hos-gamayun-proxmox.yaml`
- `topology/L4-platform/host-operating-systems/hos-orangepi5-ubuntu.yaml`
- `topology-tools/schemas/topology-v4-schema.json`
- `topology-tools/scripts/validators/checks/references.py`
- `topology-tools/templates/docs/devices.md.j2`
- `docs/architecture/L3-DATA-MODULARIZATION-PLAN.md`

## Alternatives Considered

| Option | Decision | Reason |
|---|---|---|
| A. Keep `root_mount` as primary L4 field | Rejected | Duplicates L3 chain and weakens ID-based contract |
| B. Ban all L4 -> L1 references in `installation` | Rejected | Loses useful physical install target facts; misreads contract scope |
| C. Selected hybrid (`media_ref`/`slot_ref` + `root_storage_endpoint_ref`) | Selected | Preserves operational facts and enforces layered logical contract |
