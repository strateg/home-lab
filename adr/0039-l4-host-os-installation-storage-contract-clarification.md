---
adr: "0039"
layer: "L4"
scope: "host-os-installation-storage-contract"
status: "Accepted"
date: "2026-02-23"
public_api:
  - "host_operating_systems[].installation.root_storage_endpoint_ref"
breaking_changes: true
---

# ADR 0039: Clarify Host OS Installation Storage Contract and Layer Boundary

- Status: Accepted
- Date: 2026-02-23

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Clarify `host_operating_systems[].installation` references across L1/L3 |
| Problem | `root_mount` in L4 duplicates L3 chain semantics; missing storage endpoints for host root |
| Decision | Keep `media_ref`/`slot_ref` as optional L4 -> L1 install facts, use `root_storage_endpoint_ref` for L4 -> L3 root placement |
| Data contract | `data_assets` remain service data semantics only; host root/swap are substrate storage endpoints |
| Migration mode | Additive in phase-1, deprecate `root_mount` gradually |
| L3 prerequisite | Create `se-<device>-root` storage endpoints for host root placement |

## Context

### Current State

Current host OS objects (`hos-gamayun-proxmox.yaml`) use:

```yaml
installation:
  media_ref: disk-ssd-system    # L1 reference
  slot_ref: slot-sata-0         # L1 reference
  root_mount: /                 # Path string (NOT a reference)
```

### Storage Chain Analysis

The actual storage chain from L1 to mount point:

```text
L1 (Foundation):
  disk-ssd-system (media) + slot-sata-0 (slot)
        │
        ▼ media_attachment_ref
  attach-gamayun-slot-sata-0 (media attachment)
        │
        ▼
L3 (Data) - Internal Chain:
  part-gamayun-ssd-3 (partition, type: lvm-pv)
        │
        ▼ partition_ref
  vg-pve (volume group)
        │
        ▼ vg_ref
  lv-pve-root (logical volume, 58GB, thick)
        │
        ▼ lv_ref
  fs-pve-root (filesystem, ext4)
        │
        ▼ filesystem_ref
  mnt-gamayun-root (mount point, path: /)
        │
        ▼ mount_point_ref (MISSING!)
L3 (Data) - Public API:
  se-??? (NO storage endpoint for host root!)
```

### Problem Statement

1. **Missing storage endpoint**: No `storage_endpoint` exists for host root placement. Current endpoints (`se-local`, `se-lvm`) are for Proxmox VM/LXC storage, not host root.

2. **L4 -> L3 contract violation**: According to ADR 0032, L4 must only reference L3 public API (`storage_endpoints`, `data_assets`), not internal chain IDs or raw paths like `root_mount: /`.

3. **Semantic confusion**: `root_mount: /` is a path string that duplicates L3 internal `mount_points[].path` without providing stable cross-layer reference semantics.

4. **L4 -> L1 references legitimacy**: `media_ref` and `slot_ref` are valid L4 -> L1 references per ADR 0035, but this is not clearly documented.

### Cross-Layer Contract (from ADR 0032)

| Entity | Visibility | Consumers |
|---|---|---|
| `storage_endpoints[]` | Public | L4, L7 |
| `data_assets[]` | Public | L4, L5, L7 |
| `partitions[]`, `volume_groups[]`, `logical_volumes[]`, `filesystems[]`, `mount_points[]` | Internal | L3 only |

**Rule**: L4/L5/L7 must not reference internal L3 chain IDs.

## Decision Drivers

1. **Validator cannot validate `root_mount`**: Path strings are not resolvable IDs; validators cannot determine if `root_mount: "/"` is valid without duplicating L3 internal chain logic.

2. **Documentation inconsistency**: Docs render `root_mount` but cannot validate it against actual storage topology.

3. **ADR 0035 gap**: ADR 0035 mentioned `installation.root_storage_endpoint_ref` but did not specify L3 storage endpoint creation or migration path for `root_mount`.

## Decision

### D1. Create storage endpoints for host root placement

L3 must define storage endpoints that represent host root placement:

| Host | Storage Endpoint ID | Mount Point Ref | Path |
|---|---|---|---|
| gamayun | `se-gamayun-root` | `mnt-gamayun-root` | `/` |
| orangepi5 | `se-orangepi5-root` | `mnt-orangepi5-root` | `/` |

These are **substrate** storage endpoints (not data assets) and serve as stable IDs for host OS installation placement validation.

Example `se-gamayun-root.yaml`:

```yaml
id: se-gamayun-root
name: gamayun-root
platform: proxmox
type: dir
mount_point_ref: mnt-gamayun-root
path: /
shared: false
description: Host root filesystem storage endpoint for Proxmox host
```

### D2. Single reference via `root_storage_endpoint_ref`

`host_operating_systems[].installation` contains only one reference:

| Field | Target Layer | Purpose |
|---|---|---|
| `root_storage_endpoint_ref` | L3 | Logical storage endpoint for root placement |

Physical media information (disk, slot) is derivable through L3 chain:
```
root_storage_endpoint_ref -> mount_point -> filesystem -> partition -> media_attachment -> media/slot
```

Rationale:

- **No duplication**: Physical media info exists in L3 chain, no need to duplicate in L4.
- **Single source of truth**: L3 storage chain is the authoritative source for storage topology.
- **Simpler contract**: Only one reference to maintain and validate.

### D3. Treat `root_mount` as legacy compatibility field

`installation.root_mount` is classified as legacy and should be replaced by `root_storage_endpoint_ref`.

Rationale:

- Path strings are not stable cross-layer IDs.
- L3 already owns mount/FS/LV/partition internals.
- `root_storage_endpoint_ref` provides a stable contract ID and validation target.

### D4. Keep host root/swap outside `data_assets`

Host root and swap remain substrate storage modeling, not application/service data assets.

Rules:

- Use `storage_endpoints` (not `data_assets`) for host root/swap placement.
- Keep swap modeling in L3 internal chain (`partitions` and related entities).
- Keep service data in `data_assets` and bind it via workload/service references.

Semantic distinction:

| Entity Type | Purpose | Examples |
|---|---|---|
| `storage_endpoints` | Block/filesystem access points | Host root, Proxmox storage pools, NFS mounts |
| `data_assets` | Data semantics and governance | PostgreSQL database, Redis data, backup sets |

### D5. Authoring and validation guidance

For `host_type` in `{baremetal, hypervisor}`:

1. `installation` block is required.
2. `installation.root_storage_endpoint_ref` is required.

For `host_type: embedded`:

1. `installation` block is optional.
2. Many embedded devices (e.g., RouterOS) do not have modeled L3 storage chain.

## Migration Plan

### Phase-1 (additive, current) - DONE

1. ✅ Create missing storage endpoints for host root:
   - `topology/L3-data/storage-endpoints/se-gamayun-root.yaml`
   - `topology/L3-data/storage-endpoints/se-orangepi5-root.yaml`

2. ✅ Update host OS objects with `root_storage_endpoint_ref`:
   - `hos-gamayun-proxmox.yaml`
   - `hos-orangepi5-ubuntu.yaml`

3. ✅ Keep `root_mount` for backward compatibility during transition.

4. ✅ Add deprecation warning in validator for `root_mount` without `root_storage_endpoint_ref`.

5. ✅ Update docs template to prefer `root_storage_endpoint_ref` over `root_mount`.

### Phase-2 (deprecation) - DONE

1. ✅ Validator warning when `root_mount` is used without `root_storage_endpoint_ref`.
2. ✅ Docs template updated: `root_storage_endpoint_ref` shown first, `root_mount` only when ref missing.
3. ✅ Schema marks `root_mount` as deprecated (`"deprecated": true`).

### Phase-3 (strict) - DONE

1. ✅ Remove `root_mount` from schema.
2. ✅ Remove template/docs rendering that treats `root_mount` as primary field.
3. ✅ `root_storage_endpoint_ref` becomes required for `host_type: baremetal/hypervisor`.
4. ✅ Remove `root_mount` from all hos-files.

### Phase-4 (simplification) - DONE

1. ✅ Remove `media_ref` and `slot_ref` from schema (redundant with L3 chain).
2. ✅ Remove `media_ref` and `slot_ref` from all hos-files.
3. ✅ Update docs template to show only `root_storage_endpoint_ref`.
4. ✅ Remove `media_ref` validation from validator.

Rationale: Physical media/slot info is derivable from L3 chain. Keeping it in L4 was duplication.

### YAML Examples

**Before (legacy):**

```yaml
# hos-gamayun-proxmox.yaml
id: hos-gamayun-proxmox
device_ref: gamayun
distribution: proxmox-ve
version: "9.x"
host_type: hypervisor
installation:
  media_ref: disk-ssd-system      # L1 reference (valid)
  slot_ref: slot-sata-0           # L1 reference (valid)
  root_mount: /                   # Path string (DEPRECATED)
```

**After Phase-4 (final):**

```yaml
# hos-gamayun-proxmox.yaml
id: hos-gamayun-proxmox
device_ref: gamayun
distribution: proxmox-ve
version: "9.x"
host_type: hypervisor
installation:
  root_storage_endpoint_ref: se-gamayun-root  # Only L3 reference needed
```

Physical media info is derived from L3 chain:
```
se-gamayun-root -> mnt-gamayun-root -> fs-pve-root -> lv-pve-root
  -> vg-pve -> part-gamayun-ssd-3 -> attach-gamayun-slot-sata-0
  -> disk-ssd-system + slot-sata-0
```

## Blockers and Prerequisites

| Item | Status | Notes |
|---|---|---|
| Create `se-gamayun-root` storage endpoint | Done | Phase-1 complete |
| Create `se-orangepi5-root` storage endpoint | Done | Phase-1 complete |
| Add `root_storage_endpoint_ref` to schema | Done | Already in schema |
| Add reference validator for `root_storage_endpoint_ref` | Done | Already in validator |
| Add deprecation warning for `root_mount` | Done | Phase-1 complete |
| Mark `root_mount` as deprecated in schema | Done | Phase-2 complete |
| Remove `media_ref`/`slot_ref` from schema | Done | Phase-4 complete |
| Remove `media_ref`/`slot_ref` from hos-files | Done | Phase-4 complete |

## Verification Checklist

- [x] `se-gamayun-root` storage endpoint exists and references `mnt-gamayun-root`
- [x] `se-orangepi5-root` storage endpoint exists
- [x] All `host_type: baremetal/hypervisor` have `root_storage_endpoint_ref`
- [x] `root_storage_endpoint_ref` resolves to valid `storage_endpoints[].id`
- [x] Referenced storage endpoints have valid `mount_point_ref` chain
- [x] `installation` contains only `root_storage_endpoint_ref` (no media_ref/slot_ref)
- [x] `python topology-tools/validate-topology.py --strict` passes
- [x] Docs correctly render host OS installation details

## Rollback

If migration causes issues:

1. Remove `root_storage_endpoint_ref` from host OS objects.
2. Remove new `se-*-root` storage endpoint files.
3. Keep `root_mount` as primary field.
4. Revert schema changes for `root_storage_endpoint_ref`.
5. Run validation:

```bash
python topology-tools/validate-topology.py --strict
python topology-tools/regenerate-all.py
```

## Consequences

Benefits:

- Clearer layer boundaries: L4 -> L1 install facts and L4 -> L3 logical placement are explicit.
- Reduced duplication with L3 storage chain.
- Better long-term stability through ID-based references.
- Validators can now validate host root placement against L3 storage topology.

Trade-offs:

- Transitional period with dual fields (`root_mount` + `root_storage_endpoint_ref`).
- Additional migration work for existing host OS objects and docs templates.
- Need to create new storage endpoint files for host root.

## Ownership (RACI)

| Role | Party |
|---|---|
| Responsible | Topology maintainer |
| Accountable | Architecture owner |
| Consulted | L3 storage maintainers |
| Informed | Documentation consumers |

## References

- [0032](0032-l3-data-modularization-and-layer-contracts.md) - L3 public API contract
- [0035](0035-l4-host-os-foundation-and-runtime-substrates.md) - Host OS foundation contract
- `topology/L4-platform/host-operating-systems/hos-gamayun-proxmox.yaml`
- `topology/L4-platform/host-operating-systems/hos-orangepi5-ubuntu.yaml`
- `topology/L3-data/mount-points/mnt-gamayun-root.yaml`
- `topology/L3-data/storage-endpoints/se-local.yaml`
- `topology-tools/schemas/topology-v4-schema.json`
- `topology-tools/scripts/validators/checks/references.py`
- `topology-tools/templates/docs/devices.md.j2`
- `docs/architecture/L3-DATA-MODULARIZATION-PLAN.md`

## Alternatives Considered

| Option | Decision | Reason |
|---|---|---|
| A. Keep `root_mount` as primary L4 field | Rejected | Duplicates L3 chain and weakens ID-based contract; not validatable |
| B. Ban all L4 -> L1 references in `installation` | Rejected | Loses useful physical install target facts; misreads contract scope |
| C. Use `data_assets` for host root | Rejected | `data_assets` are for service data semantics, not substrate block layout |
| D. Hybrid: `media_ref`/`slot_ref` + `root_storage_endpoint_ref` | Selected | Preserves operational facts and enforces layered logical contract |
