# ADR 0086 — Implementation Plan (Code-Grounded)

## Overview

This plan implements ADR 0086 using only mechanisms already present in runtime:

- `PluginRegistry` DAG/phase execution and manifest validation.
- Existing deterministic manifest discovery chain:
  framework -> class -> object -> project (`project_plugins_root`).
- Existing plugin schema contract (`plugin-manifest.schema.json`) without new fields.

No new runtime protocol (for example `contributes_to`) is introduced in this ADR.
Generator host/strategy runtime protocol is explicitly out of scope for ADR 0086 and
must be handled by a separate ADR.

**Primary goals of this plan:**
1. Remove boundary rules that are not enforced by runtime and contradict OOP semantics.
2. Reduce plugin granularity where logic is duplicated.
3. Reduce cognitive load while preserving project extensibility.
4. Keep behavior parity and deterministic outputs.

---

## Current-State Findings (from code audit)

1. `PluginContext` is intentionally broad (`raw_yaml`, `compiled_json`, `classes`, `objects`),
   so level-based access isolation does not exist in runtime.
2. Discovery chain already supports project-level plugin manifests via `project_plugins_root`
   and is covered by integration tests.
3. Validator family contains repeated patterns (subscribe normalized rows -> build index ->
   validate typed refs -> emit diagnostics).
4. Plugin IDs are inconsistent across manifests (mixed naming styles), increasing migration risk.

These findings map directly to ADR 0086 Problem 1-4.

---

## Wave 1 — Contracts, Guards, and Policy (Low Risk)

### Scope

Stabilize contracts and enforce architecture through tests/linters before moving code.

### Tasks

1. **Boundary model update in tests/docs**
   - Retire strict level-visibility assumptions.
   - Replace with contract-based checks:
     - stage/phase affinity,
     - dependency validity,
     - discovery order validity,
     - project boundary checks.

2. **Manifest ID policy enforcement**
   - Define one ID naming policy and apply linter checks in CI.
   - Detect mixed namespace styles and fail early.

3. **Discovery invariants hardening**
   - Keep `plugin_manifest_discovery.py` multi-slot chain unchanged.
   - Add explicit regression checks for project slot loading.

4. **Baseline metrics snapshot**
   - Capture plugin counts by family and stage.
   - Capture stage runtime baseline for `discover/compile/validate/generate`.

### Verification Gate

- All plugin contract tests green.
- Discovery integration tests green, including project plugin manifest loading.
- ID policy linter active in CI.

---

## Wave 2 — Validator Consolidation (Medium Risk)

### Scope

Reduce duplicated validator logic without changing diagnostics contract.

### Tasks

1. **Reference validator consolidation**
   - Introduce one declarative reference validator with rules table.
   - Migrate duplicated `*_refs_validator.py` logic into rule entries.

2. **Router port validator consolidation**
   - Merge thin vendor-specific router-port validators into one rule-driven validator.

3. **Dependency rewiring**
   - Update `depends_on`/`consumes` to new consolidated validators.
   - Keep diagnostic code parity (`E7xxx` continuity).

4. **Parity test harness**
   - Golden diagnostics comparison on representative fixture set.

### Verification Gate

- Diagnostic parity: same codes/severity/paths for equivalent invalid inputs.
- `pytest tests/` green.
- No change in produced artifacts due to validator refactor.

---

## Wave 3 — Layout Cleanup for Standalone Plugins (Medium Risk)

### Scope

Move remaining standalone class/object plugins into `topology-tools/plugins/<family>/`
while preserving module-level extension points and project extensibility.

### Tasks

1. **Standalone plugin relocation**
   - Move remaining standalone validators/generators from class/object plugin dirs
     to framework plugin directories.

2. **Manifest minimization**
   - Keep class/object manifests only where they serve extension points.
   - Remove empty/legacy manifests after migration.

3. **ID normalization rollout**
   - Apply mapping table and update dependencies across manifests/tests/docs.

4. **Architecture tests update**
   - Assert no forbidden standalone plugin placements remain.
   - Assert discovery chain still loads framework/class/object/project in order.

### Verification Gate

- Full test suite green.
- Discovery order unchanged.
- Generated output parity confirmed on baseline project.

---

## Deferred Scope (Separate ADR)

The following is intentionally deferred and must not be mixed into ADR 0086 execution:

- New manifest fields not supported by current schema.
- Runtime protocol additions for strategy contributions.
- Host/strategy generator dispatch as runtime primitive.

If needed, create separate ADR (for example ADR 0087) with kernel/schema changes.

---

## Risk Matrix

| Wave | Risk | Blast Radius | Rollback |
|------|------|--------------|----------|
| 1 | Low | Tests/CI policy | Revert linter/tests/docs changes |
| 2 | Medium | Validate stage | Revert consolidated validators and manifest rewires |
| 3 | Medium | Discovery + manifests + IDs | Revert wave commit set and restore mapping |

---

## Success Criteria

- [ ] Boundary model enforced by runtime-compatible contract tests (not level ACL assumptions).
- [ ] Project plugin extensibility preserved via `project_plugins_root` discovery.
- [ ] Duplicated validator footprint materially reduced.
- [ ] ID naming policy unified and CI-enforced.
- [ ] Standalone plugin placement simplified to framework plugin dirs.
- [ ] All regression tests pass.
- [ ] Generated artifacts remain deterministic and functionally equivalent.

---

## Minimal Execution Metrics

Track before/after for each wave:

1. Plugin count by family and total.
2. Stage runtime (`discover`, `compile`, `validate`, `generate`).
3. Number of validator files and duplicated rule blocks removed.
4. CI duration for plugin-related test jobs.
5. Discovery invariants pass rate (framework/class/object/project loading).
