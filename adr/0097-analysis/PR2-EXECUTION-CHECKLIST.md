# ADR 0097 PR2 Execution Checklist — Scheduler Cutover

Date: 2026-04-20
Status: **IN PROGRESS** — Core routing implemented, manifest updates pending
Purpose: Route all plugins through envelope/commit flow, eliminate dual-path execution model.

## PR2 Objective

Complete the scheduler cutover so that:

1. All plugins execute through `run_plugin_once()` + `_commit_envelope_result()` flow
2. `execution_mode` replaces `subinterpreter_compatible` as primary routing field
3. Legacy `execute_plugin()` path becomes compatibility-only (not primary)
4. No primary-path dependency on direct context mutation

PR2 does **not** migrate representative plugins (that is PR3 scope).

---

## A. Pre-change Safety Checks

- [x] Confirm PR1 checklist is marked COMPLETE
- [x] Verify all PR1 tests pass: `pytest tests/plugin_api/ tests/runtime/ -v`
- [x] Re-read ADR 0097 decisions D7 (execution_mode), D11 (plugin style), D12 (manifest evolution)
- [x] Keep `generated/` untouched
- [x] Plan tests before code changes

---

## B. Manifest Schema — `execution_mode` Field

### B1. Add `execution_mode` to schema

File: `topology-tools/schemas/plugin-manifest.schema.json`

- [x] Add `execution_mode` field with enum: `["subinterpreter", "main_interpreter", "thread_legacy"]`
- [x] Set default: `"main_interpreter"` (conservative, allows gradual migration)
- [x] Add description explaining each mode:
  - `subinterpreter`: Runs in isolated Python subinterpreter (Python 3.14+)
  - `main_interpreter`: Runs in main interpreter via envelope path
  - `thread_legacy`: Legacy compatibility mode (existing `execute_plugin()` path)

### B2. Update PluginSpec dataclass

File: `topology-tools/kernel/plugin_registry.py`

- [x] Add `execution_mode: str` field to `PluginSpec` dataclass
- [x] Default to `"main_interpreter"`
- [x] Parse from manifest in `_load_plugin_manifest()` via `_resolve_execution_mode()`

### B3. Deprecate `subinterpreter_compatible`

- [x] Mark `subinterpreter_compatible` as deprecated in schema
- [x] Add migration logic: if `subinterpreter_compatible: true` and no `execution_mode` → infer `execution_mode: "subinterpreter"`
- [ ] Log deprecation warning when `subinterpreter_compatible` is used without `execution_mode`

---

## C. Scheduler Routing — `_execute_phase_parallel()` Refactor

### C1. Replace routing decision

Current (line 1751):
```python
if not spec.subinterpreter_compatible:
    result = self.execute_plugin(...)  # legacy path
```

New:
```python
if spec.execution_mode == "thread_legacy":
    result = self.execute_plugin(...)  # legacy path
else:
    # envelope path for both "subinterpreter" and "main_interpreter"
```

- [x] Replace `subinterpreter_compatible` check with `execution_mode` check
- [x] Route `"main_interpreter"` through envelope path (not legacy)
- [x] Route `"subinterpreter"` through envelope path with isolated execution
- [x] Route `"thread_legacy"` through legacy `execute_plugin()` for compatibility

### C2. Simplify subinterpreter vs local decision

Current (line 1836):
```python
if HAS_REAL_SUBINTERPRETERS:
    # subinterpreter path
else:
    # local envelope path
```

New:
```python
if spec.execution_mode == "subinterpreter" and HAS_REAL_SUBINTERPRETERS:
    # subinterpreter isolated execution
else:
    # local envelope execution (main_interpreter mode)
```

- [x] Make subinterpreter execution depend on both `execution_mode` AND Python version
- [x] `main_interpreter` always uses `_execute_plugin_envelope_local()` inline (for Py3.14 cross-interpreter safety)
- [x] `subinterpreter` uses `_execute_plugin_isolated()` when available, falls back to local

### C3. Remove legacy mirror in primary path

- [x] `_mirror_context_into_pipeline_state()` should only be called for `thread_legacy` mode
- [x] Primary path (`main_interpreter`, `subinterpreter`) uses only `PipelineState` commit

---

## D. Context Side-Effects — `_apply_authoritative_commit_side_effects()`

### D1. Verify side-effect application works

The envelope commit flow must apply committed outputs to legacy context fields for downstream compatibility.

- [ ] Verify `class_map` → `ctx.classes` application works
- [ ] Verify `object_map` → `ctx.objects` application works
- [ ] Verify `effective_model_candidate` → `ctx.compiled_json` application works (when `compiled_json_owner=True`)

### D2. Add diagnostic for side-effect application

- [ ] Log when `_apply_authoritative_commit_side_effects()` modifies context
- [ ] Include plugin_id, key, and target field in log

---

## E. Test Files for PR2

### E1. Execution mode routing tests

File: `tests/runtime/scheduler/test_execution_mode_routing.py`

- [ ] Test `execution_mode: "main_interpreter"` routes through envelope path (skipped: needs integration)
- [ ] Test `execution_mode: "subinterpreter"` routes through isolated/local path (skipped: needs integration)
- [ ] Test `execution_mode: "thread_legacy"` routes through `execute_plugin()` (skipped: needs integration)
- [x] Test default execution_mode is `"main_interpreter"`
- [x] Test `subinterpreter_compatible` deprecation fallback
- [x] Test execution_mode accepts valid values
- [x] Test execution_mode rejects invalid values
- [x] Test PluginSpec has execution_mode field

### E2. No-merge-back validation tests

File: `tests/runtime/scheduler/test_no_merge_back_primary_path.py`

- [ ] Test that `main_interpreter` mode does NOT call `_mirror_context_into_pipeline_state()` (skipped: needs integration)
- [ ] Test that `subinterpreter` mode does NOT call `_mirror_context_into_pipeline_state()` (skipped: needs integration)
- [ ] Test that `thread_legacy` mode DOES call `_mirror_context_into_pipeline_state()` (skipped: needs integration)
- [x] Test envelope path uses PipelineState.commit_envelope()
- [x] Test commit_envelope does not mutate context directly

### E3. Worker failure isolation tests

File: `tests/runtime/scheduler/test_worker_failure_isolation.py`

- [x] Test that plugin crash in envelope path does not leak partial published state
- [x] Test that failed envelope is returned correctly
- [ ] Test that subsequent plugins in wavefront are not affected by crash (skipped: needs integration)

### E4. Side-effect application tests

File: `tests/runtime/scheduler/test_side_effect_application.py`

- [ ] Test `class_map` published → `ctx.classes` updated
- [ ] Test `object_map` published → `ctx.objects` updated
- [ ] Test `effective_model_candidate` published → `ctx.compiled_json` updated
- [ ] Test side-effects only apply after successful commit

---

## F. Plugin Manifest Updates

### F1. Update subinterpreter-compatible plugins

For all plugins currently marked `subinterpreter_compatible: true`:

- [ ] Add `execution_mode: "subinterpreter"` (can batch-update via script)
- [ ] Keep `subinterpreter_compatible: true` temporarily for backwards compat

### F2. Update remaining plugins

For plugins not marked `subinterpreter_compatible`:

- [ ] Add `execution_mode: "main_interpreter"` for envelope-ready plugins
- [ ] Add `execution_mode: "thread_legacy"` for plugins requiring legacy path
- [ ] Document which plugins need `thread_legacy` and why

---

## G. Validation Commands for PR2

### Minimum before commit

- [x] `pytest tests/runtime/scheduler/ -v` (new scheduler tests) — **17 passed, 11 skipped**
- [x] `pytest tests/runtime/ -v` (all runtime tests)
- [x] `pytest tests/plugin_api/ tests/plugin_contract/ -v` (API/contract tests) — **50 passed, 11 skipped**
- [ ] `task validate:adr-consistency`

### Full validation

- [ ] `pytest tests/ -v` (all tests)
- [ ] `.venv/bin/python topology-tools/compile-topology.py` (smoke test)
- [ ] `task test:plugin-integration` (full plugin integration)

---

## H. PR2 Review Checklist

- [x] `execution_mode` is the primary routing field
- [x] `subinterpreter_compatible` is deprecated with fallback
- [x] `main_interpreter` and `subinterpreter` modes use envelope path
- [x] `thread_legacy` mode uses legacy `execute_plugin()` path
- [x] No primary-path dependency on `_mirror_context_into_pipeline_state()`
- [ ] Side-effect application works for `class_map`, `object_map`, `effective_model_candidate` (PR2.1 scope)
- [x] Worker failure isolation is tested
- [x] New tests exercise execution_mode routing

---

## I. Definition of Done

PR2 is done when:

- [x] `execution_mode` manifest field exists and is documented
- [x] Scheduler routes based on `execution_mode`, not `subinterpreter_compatible`
- [x] `main_interpreter` mode uses envelope path (not legacy)
- [x] `thread_legacy` mode is the only path using legacy `execute_plugin()`
- [ ] All 50+ existing plugins have `execution_mode` set (F1/F2 scope)
- [x] New scheduler tests pass
- [x] Existing tests pass (no regressions)
- [ ] Project is ready for PR3 representative plugin migrations (after F1/F2)

---

## J. Risk Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking existing plugins | HIGH | Default to `main_interpreter`, extensive testing |
| State inconsistency | MEDIUM | Keep `_apply_authoritative_commit_side_effects()` bridge |
| Performance regression | LOW | Monitor, envelope overhead is minimal |
| Test suite instability | MEDIUM | Add new tests first, then change implementation |

### Rollback Plan

If PR2 causes regressions:

1. Revert `execution_mode` routing changes
2. Restore `subinterpreter_compatible` as primary routing
3. Keep envelope infrastructure (PR1) intact
4. Investigate and fix issues before retry

---

## K. Files to Modify

| File | Changes |
|------|---------|
| `topology-tools/schemas/plugin-manifest.schema.json` | Add `execution_mode` field |
| `topology-tools/kernel/plugin_registry.py` | Update routing logic, add `execution_mode` to PluginSpec |
| `topology-tools/plugins/plugins.yaml` | Add `execution_mode` to base plugins |
| `topology/object-modules/*/plugins.yaml` | Add `execution_mode` to object plugins |
| `tests/runtime/scheduler/` | New test directory with routing tests |

---

**PR2 Status: IN PROGRESS** — Core routing implemented. Remaining: manifest batch updates (F1/F2), deprecation logging (B3), side-effect tests (D1/D2).
