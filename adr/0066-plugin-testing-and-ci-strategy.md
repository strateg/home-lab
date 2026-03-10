# ADR 0066: Plugin Testing and CI Strategy

**Date:** 2026-03-09
**Status:** Implemented
**Related:** ADR 0063 (Plugin Microkernel), ADR 0065 (Plugin API Contract)

---

## Context

ADR 0063 and ADR 0065 introduce a plugin runtime with deterministic ordering, dependency resolution, timeout handling, and API compatibility checks.

Current repository state is migration-in-progress:

- v5 compiler is still monolithic (`v5/topology-tools/compile-topology.py`)
- test suite is minimal in `v5/tests/`
- CI workflows are oriented to v4 and lane validation

We need an incremental testing and CI strategy that can start immediately and tighten gates as plugin runtime lands.

---

## Decision

### 1. Adopt Four-Layer Plugin Test Model

Test layers are mandatory:

1. unit tests (plugin logic in isolation)
2. contract tests (plugin API and loader compatibility)
3. integration tests (full staged pipeline behavior)
4. regression parity tests (plugin path vs legacy path during migration)

### 2. Define Canonical Test Locations

Plugin migration test tree is standardized as:

```text
v5/tests/
  plugin_api/          # dataclasses, enums, helper methods
  plugin_contract/     # entry loading, kind checks, api_version, config_schema
  plugin_integration/  # stage ordering, depends_on, diagnostics aggregation, timeout
  plugin_regression/   # parity checks against legacy flows
  fixtures/plugins/    # sample plugin modules + manifests + data
```

Module-level plugin tests are colocated:

- `v5/topology/object-modules/<module>/tests/`

### 3. Define Minimum Coverage and Scenario Gates

#### Unit gates

- coverage >= 80% for plugin API package and plugin modules under test
- required scenarios: success path, config errors, edge inputs, exception wrapping

#### Contract gates

- coverage >= 70% for loader/contract path
- required scenarios: invalid `entry`, kind mismatch, API version mismatch, missing dependency declaration

#### Integration gates

- stage order determinism test is mandatory
- dependency DAG cycle detection test is mandatory
- timeout behavior test is mandatory
- diagnostics aggregation format test is mandatory

#### Regression gates

- for migrated checks/generators, outputs and diagnostics must match legacy baseline or have approved diff

### 4. Stage CI Adoption with Existing Workflows

CI rollout is phased to avoid blocking unrelated work:

#### Phase A (immediate)

- keep existing lane workflows (`.github/workflows/lane-validation.yml`)
- add non-blocking plugin test job (allow-failure) for early signal

#### Phase B (after API package lands)

- require `plugin_api` and `plugin_contract` jobs on pull requests touching:
  - `v5/topology_tools/plugin_api/**`
  - `v5/topology-tools/compile-topology.py`
  - `v5/topology/object-modules/**`

#### Phase C (after first migrated modules)

- require `plugin_integration` and `plugin_regression` for plugin-related PRs
- require manifest validation job for all object module manifest changes

### 5. Add Dedicated Plugin Workflow

Create `.github/workflows/plugin-validation.yml` with jobs:

- `plugin-api-unit`
- `plugin-contract`
- `plugin-integration`
- `plugin-regression` (enabled once baseline fixtures are committed)

Baseline command contract:

```bash
pytest v5/tests/plugin_api -v --cov=v5/topology_tools/plugin_api --cov-fail-under=80
pytest v5/tests/plugin_contract -v --cov=v5/topology-tools --cov-fail-under=70
pytest v5/tests/plugin_integration -v
pytest v5/tests/plugin_regression -v
```

### 6. Define Exit Criteria for "Plugin CI Ready"

Plugin CI is considered ready when:

1. all four layers have active test suites in `v5/tests/`
2. plugin workflow is required for plugin-related PRs
3. manifest validation runs in CI for changed module manifests
4. at least one module has green end-to-end plugin path

---

## Consequences

### Positive

1. plugin regressions are detected before merge
2. migration from monolithic compiler to plugin runtime is auditable
3. API drift becomes visible through contract tests
4. rollout can begin immediately without big-bang CI switch

### Negative

1. extra CI time and fixture maintenance overhead
2. temporary dual-path regression tests increase complexity
3. initial flaky tests risk until timeouts and fixtures stabilize

---

## Implementation Status

### Test Structure (Complete)

```
v5/tests/
├── plugin_api/
│   └── test_dataclasses.py      # 10 tests
├── plugin_contract/
│   └── test_manifest.py         # 7 tests
├── plugin_integration/
│   └── test_execution.py        # 7 tests
├── plugin_regression/
│   └── test_parity.py           # 1 placeholder
└── test_plugin_registry.py      # 16 tests (original)
```

**Total: 41 tests passing**

### CI Workflow (Complete)

- [x] Create `.github/workflows/plugin-validation.yml`
- [x] Add coverage reporting (codecov integration)
- [x] Integrate with PR checks (path-based triggers)

---

## References

- ADR 0063: `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- ADR 0065: `adr/0065-plugin-api-contract-specification.md`
- Test locations: `v5/tests/plugin_*/`
- v5 compiler baseline: `v5/topology-tools/compile-topology.py`
