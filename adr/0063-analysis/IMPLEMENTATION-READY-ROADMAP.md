# ADR 0063/0065/0066 Implementation-Ready Roadmap

**Date:** 2026-03-09
**Scope:** ADR 0063, ADR 0065, ADR 0066
**Status:** Ready for execution (Phase 0)

---

## 1. Current State Assessment

### Architecture

- ADR 0063 defines microkernel direction and migration phases.
- ADR 0065 now defines Plugin API contract (interfaces, result envelope, compatibility).
- ADR 0066 now defines test/CI rollout model.

### Codebase Reality

- `v5/topology-tools/compile-topology.py` is still monolithic.
- No `v5/topology_tools/plugin_api/` package exists yet.
- No plugin manifests or plugin tests exist in `v5/tests/plugin_*`.
- CI has lane checks and python checks, but no dedicated plugin workflow.

### Conclusion

Design is ready. Execution blockers are implementation tasks, not decision gaps.

---

## 2. Execution Plan (Implementation Preparation)

### Phase 0 - Scaffolding (1-2 days)

1. Create package skeleton:
   - `v5/topology_tools/__init__.py`
   - `v5/topology_tools/plugin_api/__init__.py`
   - `v5/topology_tools/plugin_api/types.py`
   - `v5/topology_tools/plugin_api/base.py`
2. Create test skeleton:
   - `v5/tests/plugin_api/`
   - `v5/tests/plugin_contract/`
   - `v5/tests/plugin_integration/`
   - `v5/tests/plugin_regression/`
   - `v5/tests/fixtures/plugins/`
3. Add placeholder workflow:
   - `.github/workflows/plugin-validation.yml` (non-blocking)

### Phase 1 - API and Loader Foundation (3-5 days)

1. Implement API enums/dataclasses per ADR 0065.
2. Implement `BasePlugin` + four plugin kind interfaces.
3. Implement plugin manifest loader/validator in v5 toolchain.
4. Add unit + contract tests for:
   - `entry` loading
   - kind matching
   - `api_version` compatibility
   - config schema validation

### Phase 2 - First Runtime Slice (4-7 days)

1. Migrate one low-risk validator into plugin form.
2. Add plugin execution path in compiler behind feature flag:
   - `--plugin-runtime=off|shadow|on`
3. Add integration tests:
   - deterministic order
   - timeout behavior
   - diagnostics aggregation

### Phase 3 - CI Hardening (2-3 days)

1. Turn plugin workflow to required for plugin-touching PRs.
2. Enforce coverage gates from ADR 0066.
3. Add regression parity suite for migrated logic.

---

## 3. Implementation Backlog (Ticket-Ready)

1. `PLUG-001` Create `topology_tools.plugin_api` package skeleton.
2. `PLUG-002` Implement `PluginStatus`/`PluginSeverity` + dataclasses.
3. `PLUG-003` Implement `BasePlugin` and kind-specific interfaces.
4. `PLUG-004` Add manifest loader contract validation.
5. `PLUG-005` Add plugin API unit tests (coverage >= 80%).
6. `PLUG-006` Add contract tests (coverage >= 70%).
7. `PLUG-007` Introduce shadow-mode plugin execution in compiler.
8. `PLUG-008` Migrate first YAML validator plugin.
9. `PLUG-009` Add plugin integration tests and timeout tests.
10. `PLUG-010` Add `plugin-validation.yml` and enforce PR gates.

---

## 4. Definition of Done (Per ADR)

### ADR 0063 done when

1. compiler executes at least one plugin in pipeline
2. deterministic ordering and dependency checks are active
3. diagnostics include plugin attribution

### ADR 0065 done when

1. API package exists and is importable as `topology_tools.plugin_api`
2. all plugin kinds share common `PluginResult` envelope
3. compatibility checks block incompatible plugins pre-flight

### ADR 0066 done when

1. four test layers exist in `v5/tests/`
2. plugin CI workflow runs on pull requests
3. coverage and contract gates are enforced for plugin code

---

## 5. Risks and Controls

1. Risk: path mismatch (`topology-tools` vs `topology_tools`).
   - Control: keep CLI paths unchanged, add importable package in parallel.
2. Risk: migration stalls in dual-runtime period.
   - Control: feature flag with explicit shadow-mode exit criteria.
3. Risk: flaky integration tests.
   - Control: deterministic fixtures and strict timeout budgets.

---

## 6. Immediate Next Command Set

```bash
# 1) Validate ADR consistency after updates
python v4/topology-tools/check-adr-consistency.py --strict-titles

# 2) Create implementation scaffold in next change set
# (Phase 0 from this roadmap)

# 3) Run baseline v5 checks before plugin changes
python v5/scripts/lane.py validate-v5
```
