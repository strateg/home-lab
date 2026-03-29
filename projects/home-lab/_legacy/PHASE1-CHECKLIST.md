# Phase 1 Checklist: Inventory and Mapping

Goal: map every active v4 entity (L1/L4/L5) to planned v5 `class_ref` + `object_ref`.

## Inputs

- `v4/topology.yaml`
- `v4-build/effective-topology.json`
- `v5/topology/class-modules/**`
- `v5/topology/object-modules/**`
- `v5/topology/instances/_legacy-home-lab/v4-to-v5-mapping.yaml`
- `v5/topology/instances/_legacy-home-lab/phase1-module-backlog.yaml`

## Workflow

1. Refresh inventory baseline:
   - `python v5/topology-tools/utils/bootstrap-phase1-mapping.py --refresh-effective`
   - `python v5/scripts/phase1/reconcile_phase1_mapping.py`
   - `python v5/scripts/phase1/refresh_phase1_backlog.py`
2. For each `instance_id` in mapping file:
   - set `class_ref`
   - set `object_ref` (or leave pending with explicit gap note)
   - set `status` to `mapped` or `gap`
   - keep expected layer placement consistent (`l1_devices -> L1`, `l4_vms/l4_lxc -> L4`, `l5_services -> L5`)
   - for duplicated `L5` service IDs use composite IDs (`service_id@runtime_type:target_ref`)
3. Fill capability notes for unresolved items:
   - missing class capability
   - missing object implementation
   - profile-specific constraint (`production`, `modeled`, `test-real`)
4. Validate consistency:
   - `task validate:phase1-gate`
   - `task validate:v5-layers`
   - inspect `v5-build/diagnostics/phase1-gate-report.json` for machine-readable error context
   - inspect `v5-build/diagnostics/layer-contract-report.json` for layer-contract errors
   - `task validate:v4`
   - `task validate:v5`
5. Freeze Phase 1 output:
   - no entries with empty `status`
   - every non-mapped entry has actionable `notes`

## Exit Criteria (ADR 0062 / Phase 1)

- 100% active entities in L1/L4/L5 are present in mapping inventory.
- Every entity has planned `class_ref` and `object_ref`, or documented capability gap with owner/action.
- Mapping file is committed and serves as baseline for Phase 2/3 module coverage work.
- Backlog file contains actionable class/object module gaps grouped by references.
- `task validate:phase1-gate` returns `PASS` and reports zero unresolved gaps.
- `task validate:v5-layers` returns `PASS` (class/object/instance layer contract is consistent).
