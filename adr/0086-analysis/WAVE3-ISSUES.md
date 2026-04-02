# ADR 0086 — Wave 3 Issues Backlog

This file contains ready-to-copy issue templates for Wave 3 execution
(layout cleanup, manifest minimization, ID normalization, final gates).

---

## W3-01 — Inventory Remaining Standalone Class/Object Plugins

**Title**
`W3-01: Build final inventory of remaining standalone class/object plugins`

**Description**
Create authoritative list of class/object standalone plugin entries still outside
`topology-tools/plugins/<family>/` before relocation.

**Scope (files)**
- New: `adr/0086-analysis/WAVE3-STANDALONE-INVENTORY.md`
- Inputs:
  - `topology/class-modules/*/plugins.yaml`
  - `topology/object-modules/*/plugins.yaml`
  - `topology-tools/plugins/plugins.yaml`

**Expected diff**
- Inventory with fields: plugin id, kind, source manifest, target family path,
  relocation action, dependency notes.

**Validation**
```bat
python -m pytest tests\plugin_contract\test_manifest_discovery.py -q
```

**Definition of Done**
- Inventory is complete and reviewed before relocation begins.

---

## W3-02 — Relocate Remaining Standalone Plugins to Framework Directories

**Title**
`W3-02: Move remaining standalone class/object plugins into topology-tools/plugins`

**Description**
Relocate remaining standalone class/object plugins to framework plugin family directories
without changing discovery semantics.

**Scope (files)**
- Source plugin modules under:
  - `topology/class-modules/*/plugins/**`
  - `topology/object-modules/*/plugins/**`
- Target plugin modules under:
  - `topology-tools/plugins/validators/`
  - `topology-tools/plugins/generators/`
  - (other families if needed)

**Expected diff**
- Files moved to framework family dirs.
- Imports adjusted where module-local paths changed.
- No behavior changes intended.

**Validation**
```bat
python -m pytest tests\plugin_integration -k "validator or generator" -q
```

**Definition of Done**
- No remaining standalone plugin code in class/object plugin directories.

**Depends on**
- W3-01

---

## W3-03 — Rewire Manifests After Relocation

**Title**
`W3-03: Update manifests and dependencies after standalone plugin relocation`

**Description**
Rewire plugin entries and references after moving plugin code into framework directories.

**Scope (files)**
- `topology-tools/plugins/plugins.yaml`
- `topology/class-modules/*/plugins.yaml`
- `topology/object-modules/*/plugins.yaml`

**Expected diff**
- Add/update entries in framework manifest.
- Remove obsolete class/object standalone entries.
- Update `depends_on` and `consumes.from_plugin` references.

**Validation**
```bat
python -m pytest tests\plugin_contract -q
```

**Definition of Done**
- Manifest load and dependency graph validation are green.

**Depends on**
- W3-02

---

## W3-04 — Minimize Module-Level Manifests (Keep Extension Points)

**Title**
`W3-04: Minimize class/object manifests to required extension points only`

**Description**
Clean up class/object manifests by removing migrated standalone entries while preserving
explicit extension points and project extensibility contracts.

**Scope (files)**
- `topology/class-modules/*/plugins.yaml`
- `topology/object-modules/*/plugins.yaml`

**Expected diff**
- Empty legacy manifests removed.
- Non-empty manifests kept only where extension points are still required.
- No changes to discovery chain implementation.

**Validation**
```bat
python -m pytest tests\plugin_integration\test_module_manifest_discovery.py -q
```

**Definition of Done**
- Module manifests are minimal and intentional.

**Depends on**
- W3-03

---

## W3-05 — Normalize Plugin IDs and Apply Mapping

**Title**
`W3-05: Normalize plugin IDs and apply cross-manifest mapping`

**Description**
Apply Wave 3 ID normalization using reviewed mapping, then update all references.

**Scope (files)**
- `topology-tools/plugins/plugins.yaml`
- `topology/class-modules/*/plugins.yaml`
- `topology/object-modules/*/plugins.yaml`
- New: `adr/0086-analysis/WAVE3-ID-MAPPING.md`

**Expected diff**
- ID mapping table committed.
- All references (`depends_on`, `consumes.from_plugin`) updated.
- Mixed naming styles removed from active manifests.

**Validation**
```bat
python -m pytest tests\plugin_contract -q
python -m pytest tests\plugin_integration\test_module_manifest_discovery.py -q
```

**Definition of Done**
- ID policy is applied consistently and tests are green.

**Depends on**
- W3-04

---

## W3-06 — Update Architecture Tests for Final Layout Policy

**Title**
`W3-06: Update architecture tests to enforce final standalone plugin placement`

**Description**
Add/adjust tests to enforce final layout rule: standalone plugins are framework-hosted,
module manifests are extension-point only, discovery order remains unchanged.

**Scope (files)**
- `tests/plugin_contract/test_plugin_level_boundaries.py` (or replacement contract test file)
- `tests/plugin_contract/test_manifest_discovery.py`
- Optional new test: `tests/plugin_contract/test_plugin_layout_policy.py`

**Expected diff**
- Assertions for forbidden standalone placements outside framework dirs.
- Assertions preserving framework/class/object/project discovery behavior.

**Validation**
```bat
python -m pytest tests\plugin_contract -q
```

**Definition of Done**
- Layout policy is enforced by automated tests.

**Depends on**
- W3-05

---

## W3-07 — Full Pipeline Parity Gate (Parallel + Sequential)

**Title**
`W3-07: Run full compile parity gates in parallel and sequential plugin modes`

**Description**
Run compile pipeline in default and `--no-parallel-plugins` mode and validate no
unexpected drift.

**Scope**
- Gate-only task (execution evidence + drift review)

**Validation**
```bat
python topology-tools\compile-topology.py
python topology-tools\compile-topology.py --no-parallel-plugins
```

**Definition of Done**
- Both runs succeed.
- No unapproved diagnostic/artifact drift.

**Depends on**
- W3-06

---

## W3-08 — Final Validation Gate and Cutover Sign-Off

**Title**
`W3-08: Execute final Wave 3 gates and update cutover checklist`

**Description**
Execute final validation gates and mark `CUTOVER-CHECKLIST.md` status for Wave 3 completion.

**Scope (files)**
- `adr/0086-analysis/CUTOVER-CHECKLIST.md`
- Optional run evidence under `build/adr0086-baseline/`

**Validation**
```bat
python -m pytest tests\plugin_contract -q
python -m pytest tests\plugin_integration -q
set V5_SECRETS_MODE=passthrough
python scripts\orchestration\lane.py validate-v5
```

**Definition of Done**
- Final gates pass.
- Cutover checklist updated and reviewed.

**Depends on**
- W3-07

---

## Recommended Execution Order

1. W3-01
2. W3-02
3. W3-03
4. W3-04
5. W3-05
6. W3-06
7. W3-07
8. W3-08

---

## Rollback Boundaries

Create rollback boundary after each block:

- Block A: W3-01..W3-03
- Block B: W3-04..W3-05
- Block C: W3-06
- Block D: W3-07..W3-08

Suggested tag pattern:
- `adr0086-wave3-block-a`
- `adr0086-wave3-block-b`
- `adr0086-wave3-block-c`
- `adr0086-wave3-done`

---

## Final Wave 3 Gate Command Set

```bat
python -m pytest tests\plugin_contract -q
python -m pytest tests\plugin_integration -q
python topology-tools\compile-topology.py
python topology-tools\compile-topology.py --no-parallel-plugins
set V5_SECRETS_MODE=passthrough
python scripts\orchestration\lane.py validate-v5
```
