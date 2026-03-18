# ADR 0071 Implementation Plan

**ADR:** `adr/0071-sharded-instance-files-and-flat-instances-root.md`
**Status:** Completed
**Date:** 2026-03-11
**Checklist:** `adr/0071-analysis/CUTOVER-CHECKLIST.md`

## Goal

Switch from one monolithic `instance-bindings.yaml` to one-instance-per-file storage under `paths.instances_root`, while keeping downstream plugin contracts unchanged.

## Non-Negotiables

1. Keep assembled in-memory payload shape compatible with current plugins:
   - `instance_bindings: { <group>: [rows...] }`
2. Preserve deterministic behavior (discovery, ordering, diagnostics).
3. Remove legacy monolith path from active runtime after migration.
4. Do not introduce `instance-modules`; plugin location stays in class/object modules only.

## Delivery Phases

### Phase 1: Path Contract and Runtime

Files:

- `v5/topology/topology.yaml`
- `v5/topology-tools/compiler_runtime.py`

Deliver:

1. Add canonical `paths.instances_root`.
2. Remove `paths.instance_bindings` from active manifest.
3. Run instance source in `sharded-only`.

Done when:

1. Runtime reads only `instances_root`.
2. Missing `instances_root` fails with deterministic diagnostics.

### Phase 2: Sharded Loader and Validation

Files:

- `v5/topology-tools/plugins/compilers/instance_rows_compiler.py` (or dedicated loader)
- `v5/topology-tools/data/error-catalog.yaml`

Deliver:

1. Deterministic shard discovery.
2. One-row-per-file, required keys, shard version checks (`version: 1.0.0`).
3. Keep `class_ref` optional in shard files and derive/verify via compiler normalization.
4. Identity checks (`basename == instance`, global uniqueness).
5. E71xx diagnostics.

Done when:

1. Invalid shard scenarios return stable E71xx codes.
2. Assembled payload is deterministic.
3. Assembled rows include correct derived `class_ref` without requiring it in shard files.

### Phase 3: Migration and Parity

Files:

- `v5/tests/plugin_integration/*`
- `v5/topology-tools/split-instance-bindings.py`

Deliver:

1. Parity tests for assembled payload and diagnostics.
2. Determinism tests (repeat runs produce no noisy diff).
3. Split legacy monolith into per-instance shard files.

Done when:

1. Baseline profiles (`production`, `modeled`, `test-real`) are green.
2. Diagnostics are stable for invalid shard scenarios.

### Phase 4: Cutover and Cleanup

Deliver:

1. Move legacy content to `_legacy-home-lab`.
2. Update docs/tests/tooling to `instances_root` layout.
3. Remove dual-source/legacy runtime behavior.

Done when:

1. `adr/0071-analysis/CUTOVER-CHECKLIST.md` is fully green.
2. ADR0071 is `Accepted`.

## Sequencing

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4

## Rollback

Rollback is repository-level only (git revert), because runtime no longer supports legacy source modes.

## Risks (Short List)

1. Duplicate IDs during migration.
2. Accidental ingestion of non-instance YAML.
3. Contract drift between loader output and plugin expectations.
