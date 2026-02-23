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

### D2. Keep two distinct reference classes in `installation`

`host_operating_systems[].installation` contains two complementary reference types:

| Field | Target Layer | Purpose | When Needed |
|---|---|---|---|
| `media_ref` | L1 | Physical media where OS was installed | Hardware traceability |
| `slot_ref` | L1 | Physical slot/interface connection | Physical topology |
| `root_storage_endpoint_ref` | L3 | Logical storage endpoint for root placement | Workload placement validation |

Rationale:

- `media_ref`/`slot_ref` answer "where OS was installed physically" (L4 -> L1).
- `root_storage_endpoint_ref` answers "which logical storage endpoint represents host root" (L4 -> L3).

These concerns are complementary, not conflicting.

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

1. `installation` remains required.
2. `root_storage_endpoint_ref` is strongly recommended and should become mandatory after migration window.
3. `media_ref` and `slot_ref` stay optional (unknown/abstract installs are valid).

For `host_type: embedded`:

1. `installation` remains optional.
2. If `installation` is present, same field semantics apply.
3. Many embedded devices (e.g., RouterOS) do not have modeled L3 storage chain; `root_storage_endpoint_ref` may be omitted.

## Migration Plan

### Phase-1 (additive, current)

1. Create missing storage endpoints for host root:
   - `topology/L3-data/storage-endpoints/se-gamayun-root.yaml`
   - `topology/L3-data/storage-endpoints/se-orangepi5-root.yaml`

2. Update host OS objects with `root_storage_endpoint_ref`:
   - `hos-gamayun-proxmox.yaml`
   - `hos-orangepi5-ubuntu.yaml`

3. Keep `root_mount` for backward compatibility during transition.

4. Update docs examples to prefer `root_storage_endpoint_ref` over `root_mount`.

### Phase-2 (deprecation)

1. Validator warning when `root_mount` is used without `root_storage_endpoint_ref`.
2. Validator warning on newly added `root_mount` in changed files.
3. Update schema to mark `root_mount` as deprecated.

### Phase-3 (strict)

1. Remove `root_mount` from schema.
2. Remove template/docs rendering that treats `root_mount` as primary field.
3. `root_storage_endpoint_ref` becomes required for `host_type: baremetal/hypervisor`.

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

**After Phase-1 (recommended):**

```yaml
# hos-gamayun-proxmox.yaml
id: hos-gamayun-proxmox
device_ref: gamayun
distribution: proxmox-ve
version: "9.x"
host_type: hypervisor
installation:
  media_ref: disk-ssd-system           # L1 reference (valid)
  slot_ref: slot-sata-0                # L1 reference (valid)
  root_storage_endpoint_ref: se-gamayun-root  # L3 reference (NEW)
  root_mount: /                        # DEPRECATED, kept for compatibility
```

**After Phase-3 (strict):**

```yaml
# hos-gamayun-proxmox.yaml
id: hos-gamayun-proxmox
device_ref: gamayun
distribution: proxmox-ve
version: "9.x"
host_type: hypervisor
installation:
  media_ref: disk-ssd-system           # L1 reference (optional)
  slot_ref: slot-sata-0                # L1 reference (optional)
  root_storage_endpoint_ref: se-gamayun-root  # L3 reference (required)
```

## Blockers and Prerequisites

| Item | Status | Notes |
|---|---|---|
| Create `se-gamayun-root` storage endpoint | Required | Phase-1 blocker |
| Create `se-orangepi5-root` storage endpoint | Required | Phase-1 blocker |
| Add `root_storage_endpoint_ref` to schema | Required | Phase-1 blocker |
| Add reference validator for `root_storage_endpoint_ref` | Required | Phase-1 blocker |
| Mark `root_mount` as deprecated in schema | Required | Phase-2 blocker |

## Verification Checklist

- [ ] `se-gamayun-root` storage endpoint exists and references `mnt-gamayun-root`
- [ ] `se-orangepi5-root` storage endpoint exists (if applicable)
- [ ] All `host_type: baremetal/hypervisor` have `root_storage_endpoint_ref`
- [ ] `root_storage_endpoint_ref` resolves to valid `storage_endpoints[].id`
- [ ] Referenced storage endpoints have valid `mount_point_ref` chain
- [ ] `root_mount` deprecated warnings appear in validator output (Phase-2)
- [ ] `python topology-tools/validate-topology.py --strict` passes
- [ ] Docs correctly render host OS installation details

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
