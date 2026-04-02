# ADR 0086 — Wave 1 Issues Backlog

This file contains ready-to-copy issue templates for Wave 1 execution.

---

## W1-01 — ADR/Analysis Consistency (Contract-Based Boundary Model)

**Title**
`W1-01: Align ADR 0086 + analysis docs to contract-based boundary model`

**Description**
Synchronize ADR 0086 and analysis artifacts so the boundary model is contract-based
(without runtime ACL assumptions), and remove contradictions between ADR and
implementation plan.

**Scope (files)**
- `adr/0086-flatten-plugin-hierarchy-and-reduce-granularity.md`
- `adr/0086-analysis/IMPLEMENTATION-PLAN.md`
- `adr/0086-analysis/GAP-ANALYSIS.md`
- `adr/0086-analysis/CUTOVER-CHECKLIST.md`

**Expected diff**
- Unified wording around contract boundaries (`stage/phase`, `depends_on`, `consumes`, `produces`, discovery invariants).
- Remove references to unsupported runtime protocol additions within ADR 0086 scope.
- Explicitly preserve `project_plugins_root` behavior.

**Validation**
```bat
python -m pytest tests\plugin_contract\test_manifest_discovery.py tests\plugin_integration\test_module_manifest_discovery.py -q
```

**Definition of Done**
- ADR and analysis docs are mutually consistent and executable against current runtime.

---

## W1-02 — Replace Legacy Boundary Test with Contract Checks

**Title**
`W1-02: Refactor boundary contract tests away from level-visibility assumptions`

**Description**
Refactor boundary tests to verify executable contracts, not legacy assumptions about
level-based visibility through `PluginContext`.

**Scope (files)**
- `tests/plugin_contract/test_plugin_level_boundaries.py` (refactor/replace)
- Optional new file: `tests/plugin_contract/test_plugin_contract_boundaries.py`

**Expected diff**
- Remove assertions like "class plugin must not read object data".
- Add checks for:
  - `kind -> stage` affinity,
  - dependency validity,
  - phase/order constraints.

**Validation**
```bat
python -m pytest tests\plugin_contract\test_plugin_level_boundaries.py -q
```

**Definition of Done**
- Boundary test suite reflects current runtime contract model.

**Depends on**
- W1-01

---

## W1-03 — Discovery Order Invariants

**Title**
`W1-03: Enforce deterministic manifest discovery order invariants`

**Description**
Strengthen discovery tests for strict root order:
`framework -> class -> object -> project`.

**Scope (files)**
- `tests/plugin_contract/test_manifest_discovery.py`
- `tests/plugin_integration/test_module_manifest_discovery.py`

**Expected diff**
- Explicit assertions for root ordering.
- Explicit regression check for project slot (`project_plugins_root`).
- Negative-path checks for forbidden roots.

**Validation**
```bat
python -m pytest tests\plugin_contract\test_manifest_discovery.py tests\plugin_integration\test_module_manifest_discovery.py -q
```

**Definition of Done**
- Discovery ordering regressions are caught by tests.

---

## W1-04 — Discover Boundary Guard Hardening

**Title**
`W1-04: Harden discover boundary diagnostics and forbidden-path checks`

**Description**
Stabilize `DiscoverBoundaryCompiler` diagnostics for manifests outside allowed
project plugin boundaries and under data roots.

**Scope (files)**
- `topology-tools/plugins/discoverers/discover_compiler.py`
- `tests/plugin_integration/test_module_manifest_discovery.py`

**Expected diff**
- Stable diagnostic messages and paths for forbidden locations.
- Clear handling for `topology/instances` manifest leakage.

**Validation**
```bat
python -m pytest tests\plugin_integration\test_module_manifest_discovery.py -q
```

**Definition of Done**
- Boundary violations produce deterministic diagnostics.

**Depends on**
- W1-03

---

## W1-05 — Manifest ID Policy Lint (CI Guard)

**Title**
`W1-05: Add plugin manifest ID policy test/lint`

**Description**
Add contract tests that enforce consistent plugin ID naming style across all manifests
and prevent future namespace drift.

**Scope (files)**
- New: `tests/plugin_contract/test_manifest_id_policy.py`
- Manifests under:
  - `topology-tools/plugins/plugins.yaml`
  - `topology/class-modules/*/plugins.yaml`
  - `topology/object-modules/*/plugins.yaml`

**Expected diff**
- New test validates:
  - allowed ID format,
  - no mixed styles in same domain,
  - actionable failure diagnostics for migration.

**Validation**
```bat
python -m pytest tests\plugin_contract\test_manifest_id_policy.py -q
```

**Definition of Done**
- CI fails on new ID policy violations.

**Depends on**
- W1-01

---

## W1-06 — Baseline Capture for Wave 1

**Title**
`W1-06: Capture ADR0086 Wave 1 baseline artifacts`

**Description**
Capture baseline artifacts for reproducible before/after comparison and rollback evidence.

**Scope (artifacts)**
- `build/adr0086-baseline/baseline-commit.txt`
- `build/adr0086-baseline/git-status.txt`
- `build/adr0086-baseline/tests-discovery.txt`
- `build/adr0086-baseline/tests-plugin-contract.txt`

**Expected diff**
- Baseline evidence files created/updated.

**Validation**
```bat
cd d:\Workspaces\PycharmProjects\home-lab
if not exist build\adr0086-baseline mkdir build\adr0086-baseline
git rev-parse HEAD > build\adr0086-baseline\baseline-commit.txt
git status --short > build\adr0086-baseline\git-status.txt
python -m pytest tests\plugin_contract\test_manifest_discovery.py tests\plugin_integration\test_module_manifest_discovery.py -q > build\adr0086-baseline\tests-discovery.txt
python -m pytest tests\plugin_contract -q > build\adr0086-baseline\tests-plugin-contract.txt
```

**Definition of Done**
- Reproducible baseline artifacts exist for Wave 2/3 comparisons.

---

## W1-07 — End-to-End Validation Gate

**Title**
`W1-07: Run validate-v5 gate after Wave 1 and record outcome`

**Description**
Run end-to-end validation after Wave 1 and attach result to PR/issues.

**Scope**
- Gate-only task (no mandatory code changes).

**Validation**
```bat
set V5_SECRETS_MODE=passthrough
python scripts\orchestration\lane.py validate-v5
```

**Definition of Done**
- `validate-v5` passes.
- Gate output/result linked in PR or issue comments.

**Depends on**
- W1-02
- W1-03
- W1-04
- W1-05

---

## Recommended Execution Order

1. W1-01
2. W1-03
3. W1-04
4. W1-02
5. W1-05
6. W1-06
7. W1-07

---

## Final Wave 1 Gate Command Set

```bat
python -m pytest tests\plugin_contract -q
python -m pytest tests\plugin_integration\test_module_manifest_discovery.py -q
set V5_SECRETS_MODE=passthrough
python scripts\orchestration\lane.py validate-v5
```
