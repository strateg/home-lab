# ADR0063 Hardening Implementation Plan

- Date: 2026-03-11
- Scope: bring runtime behavior in full alignment with ADR 0063 contracts
- Branch: `adr/0070-acceptance-testing`

## Problem Statement

Current plugin runtime is functional, but there are contract gaps against ADR0063:

1. Execution ordering does not honor `depends_on -> order -> id` deterministically.
2. Diagnostics report payload does not match `diagnostics.schema.json`.
3. Runtime does not enforce plugin manifest JSON Schema for every loaded manifest.
4. Compile-stage fail-fast policy is not explicitly enforced.
5. CI validates only base manifest, not module-level manifests.

## Delivery Strategy (3 commits)

## Commit 1: Deterministic execution order + fail-fast compile

### Changes

1. Fix stage ordering algorithm in `PluginRegistry.get_execution_order()`:
   - keep topological constraints from `depends_on`
   - for ready-to-run nodes select by `(order, id)` (stable tie-break)
2. Add explicit compile fail-fast behavior in orchestrator:
   - compile stage must stop on `FAILED|TIMEOUT`.
3. Add/adjust tests:
   - ordering tests for independent plugins with different `order`
   - ordering tests for tie-break by `id`
   - compile fail-fast integration check.

### Target files

- `v5/topology-tools/kernel/plugin_registry.py`
- `v5/topology-tools/compile-topology.py`
- `v5/tests/test_plugin_registry.py`
- `v5/tests/plugin_integration/test_execution.py`

### Acceptance for Commit 1

1. Plugin order is independent of manifest insertion order.
2. Tests demonstrate `depends_on` precedence and `(order,id)` selection.
3. Compile stage stops immediately after critical plugin failure.

## Commit 2: Diagnostics contract alignment

### Changes

1. Align report writer and schema:
   - either move writer to schema `2.0.0` format, or
   - update schema to reflect actual runtime format.
2. Ensure stage vocabulary is consistent:
   - include real runtime stages (`compile`, `generate`) if emitted.
3. Add contract tests validating generated diagnostics JSON against schema.
4. Include plugin summary section if schema requires it.

### Target files

- `v5/topology-tools/compiler_reporting.py`
- `v5/topology-tools/schemas/diagnostics.schema.json`
- `v5/tests/plugin_contract/` (new diagnostics contract test)
- optional: `v5/tests/plugin_integration/` (compile report validation)

### Acceptance for Commit 2

1. Real compile output validates against `diagnostics.schema.json`.
2. No schema/runtime drift for `report_version` and stages.
3. CI has a diagnostics schema validation test.

## Commit 3: Manifest schema enforcement in runtime + CI expansion

### Changes

1. Validate every loaded manifest against
   `v5/topology-tools/schemas/plugin-manifest.schema.json`
   directly in runtime loader.
2. Fail manifest load on schema violations
   (`additionalProperties`, missing required fields, enum mismatches).
3. Extend CI manifest-validation job:
   - validate base manifest and all module manifests discovered under
     `v5/topology/class-modules/**/plugins.yaml`
     `v5/topology/object-modules/**/plugins.yaml`.
4. Add tests for invalid extra fields and broken manifests in runtime.

### Target files

- `v5/topology-tools/kernel/plugin_registry.py`
- `.github/workflows/plugin-validation.yml`
- `v5/tests/plugin_contract/test_manifest.py`
- `v5/tests/plugin_contract/test_manifest_discovery.py`

### Acceptance for Commit 3

1. Runtime rejects invalid manifests even outside CI.
2. CI fails if any module-level manifest violates schema.
3. Discovery + validation policy is deterministic and documented.

## Validation Matrix (run after each commit)

1. `python -m pytest -q -o addopts="" v5/tests/plugin_api`
2. `python -m pytest -q -o addopts="" v5/tests/plugin_contract`
3. `python -m pytest -q -o addopts="" v5/tests/plugin_integration`
4. `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock`

## Risks and Controls

1. Risk: behavior change in ordering may expose hidden dependency bugs.
   - Control: add explicit `depends_on` where implicit order was assumed.
2. Risk: diagnostics schema tightening may fail existing tooling.
   - Control: migrate schema and writer in the same commit.
3. Risk: strict manifest validation may break existing custom manifests.
   - Control: provide clear diagnostics and migration notes.

## Done Criteria

1. ADR0063 critical contracts are enforced in code, not only documented.
2. Plugin runtime behavior is deterministic and test-covered.
3. Diagnostics and manifests are schema-valid by default in CI and local runs.
