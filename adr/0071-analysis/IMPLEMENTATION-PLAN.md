# ADR 0071 Implementation Plan

**ADR:** `adr/0071-sharded-instance-files-and-flat-instances-root.md`
**Status:** Planned
**Date:** 2026-03-11
**Checklist:** `adr/0071-analysis/CUTOVER-CHECKLIST.md`

## Goal

Switch from one monolithic `instance-bindings.yaml` to one-instance-per-file storage under `paths.instances_root`, while keeping downstream plugin contracts unchanged.

## Non-Negotiables

1. Keep assembled in-memory payload shape compatible with current plugins:
   - `instance_bindings: { <group>: [rows...] }`
2. Preserve deterministic behavior (discovery, ordering, diagnostics).
3. Keep rollback path (`legacy-only`) until cutover is proven.
4. Do not introduce `instance-modules`; plugin location stays in class/object modules only.

## Delivery Phases

### Phase 1: Path Contract and Runtime Modes

Files:

- `v5/topology/topology.yaml`
- `v5/topology-tools/compiler_runtime.py`

Deliver:

1. Add canonical `paths.instances_root`.
2. Keep deprecated compatibility key `paths.instance_bindings`.
3. Support runtime modes: `legacy-only`, `dual-read`, `sharded-only`.

Done when:

1. Runtime starts in all three modes.
2. Legacy key usage emits deprecation warning.

### Phase 2: Sharded Loader and Validation

Files:

- `v5/topology-tools/plugins/compilers/instance_rows_compiler.py` (or dedicated loader)
- `v5/topology-tools/data/error-catalog.yaml`

Deliver:

1. Deterministic shard discovery.
2. One-row-per-file, required keys, schema-version checks.
3. Derive `class_ref` from `object_ref` in loader assembly path.
4. Identity checks (`basename == instance`, global uniqueness).
5. E71xx diagnostics.

Done when:

1. Invalid shard scenarios return stable E71xx codes.
2. Assembled payload is deterministic.
3. Assembled rows include correct derived `class_ref` without requiring it in shard files.

### Phase 3: Compatibility and Parity

Files:

- `v5/tests/plugin_integration/*`

Deliver:

1. Parity tests for assembled payload and diagnostics.
2. Determinism tests (repeat runs produce no noisy diff).
3. CLI compatibility checks for baseline workflows.

Done when:

1. Baseline profiles (`production`, `modeled`, `test-real`) are green.
2. Diagnostics parity (`code`, `severity`, `path`) is green.

### Phase 4: Cutover and Cleanup

Deliver:

1. Switch default to `sharded-only`.
2. Keep rollback switch during stabilization.
3. Retire or hard-disable legacy path after checklist is green.

Done when:

1. `adr/0071-analysis/CUTOVER-CHECKLIST.md` is fully green.
2. ADR0071 can be promoted to `Accepted`.

## Sequencing

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4

## Rollback

Trigger rollback on any of:

1. parity failure
2. deterministic ordering regression
3. critical CLI regression

Rollback action:

1. set runtime mode to `legacy-only`
2. open blocking issue
3. resume cutover only after parity returns green

## Risks (Short List)

1. Duplicate IDs during migration.
2. Accidental ingestion of non-instance YAML.
3. Contract drift between loader output and plugin expectations.
