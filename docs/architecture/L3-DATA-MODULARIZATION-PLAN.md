# L3 Data Modularization Plan

Date: 2026-02-22  
Scope: `L3_data` split into modular structure with preserved behavior.

## Goal

Modularize `L3_data` while preserving:

1. Stable IDs for `storage_endpoints` and `data_assets`.
2. Existing generator output equivalence.
3. Strict layered dependency rules (downward and upward contracts).

## Target Layout

```text
topology/L3-data/
  partitions/
  volume-groups/
  logical-volumes/
  filesystems/
  mount-points/
  storage-endpoints/
  data-assets/
```

`topology/L3-data.yaml` remains composition root with `!include`.

## Phased Rollout

### Phase 0: Preconditions

1. Freeze non-L3 topology edits for the migration window.
2. Run baseline checks:
   - `python topology-tools/validate-topology.py --strict`
   - `python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate`
3. Capture current generated snapshots for comparison (`generated/`).

Exit criteria:

- Validation and generation pass before migration.

### Phase 1: Structural Split (No Semantics Change)

1. Create `topology/L3-data/*` directories.
2. Move each L3 object into dedicated module files.
3. Add `_index.yaml` per subdirectory.
4. Convert `topology/L3-data.yaml` to include-based composition root.

Rules:

1. Keep all existing IDs unchanged.
2. Keep object content unchanged except file movement.

Exit criteria:

- `validate-topology.py --strict` passes.

### Phase 2: Equivalence Verification

1. Run full regeneration:
   - `python topology-tools/regenerate-all.py --topology topology.yaml --strict --skip-mermaid-validate`
2. Compare generated artifacts with pre-split baseline.
3. Investigate and fix any non-whitelisted diffs.

Allowed diffs:

1. Timestamp-only changes in docs.

Exit criteria:

- No functional diffs in Terraform/Ansible outputs.

### Phase 3: Contract Hardening (Upward/Downward)

1. Add validator policy paths for L3 placement checks.
2. Add semantic checks:
   - L4/L5/L7 may reference only `storage_endpoints`/`data_assets` from L3.
   - Disallow upper-layer refs to internal chain IDs (`part-*`, `vg-*`, `lv-*`, `fs-*`, `mnt-*`).
   - Verify L7 `storage_ref` resolves to endpoint IDs.
3. Fix topology drift found by new checks.

Exit criteria:

- Strict mode passes with new semantic checks.

### Phase 4: Documentation and Governance

1. Update `topology/MODULAR-GUIDE.md` to mark L3 as modularized.
2. Add migration notes in `docs/CHANGELOG.md`.
3. Link this plan and ADR in architecture docs.

Exit criteria:

- Documentation reflects final canonical layout.

## Dependency Analysis Checklist

### Downward (L3 -> lower layers)

1. `partitions.media_attachment_ref` points only to L1 attachments.
2. `mount_points.device_ref` points only to L1 devices.
3. No references from L3 to L4-L7 entities.

### Upward (upper layers -> L3)

1. L4 uses only `storage_endpoint_ref` and `data_asset_ref`.
2. L5 uses only `data_asset_ref`.
3. L7 backup uses `data_asset_ref` and endpoint IDs for storage binding.
4. L6 has no direct dependency on L3 internal chain.

## Risk Register

1. ID drift during split:
   - Mitigation: enforce unchanged IDs and run strict validation.
2. Hidden generator assumptions about monolithic file:
   - Mitigation: regression regeneration and diff checks.
3. Legacy refs in upper layers:
   - Mitigation: add semantic validator checks before finalization.

## Rollback Plan

1. Restore previous `topology/L3-data.yaml` monolith from git.
2. Remove `topology/L3-data/` subtree.
3. Re-run strict validation/regeneration.

