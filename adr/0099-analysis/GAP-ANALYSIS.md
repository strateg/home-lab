# ADR 0099 Gap Analysis

**Analysis Date:** 2026-04-21
**Baseline:** Post ADR 0097 PR5 implementation
**Focus:** Legacy code removal and test architecture migration

## Executive Summary

Analysis of ADR 0099 requirements against current codebase state reveals:
- 55% of test files use legacy execution patterns
- ~773 lines of dead code (runtime + tests)
- 6 critical constraint violations
- 44% of acceptance criteria currently met

> Historical note: the executive summary and sections 1-7 below capture the
> initial baseline snapshot used to scope ADR0099. See the incremental updates
> for the current post-migration state.

## Incremental Update (2026-04-21, post scheduler hardening)

Completed in this iteration:
- Removed placeholder skips from runtime scheduler suites:
  - `tests/runtime/scheduler/test_execution_mode_routing.py`
  - `tests/runtime/scheduler/test_no_merge_back_primary_path.py`
  - `tests/runtime/scheduler/test_worker_failure_isolation.py`
- Added concrete routing coverage for:
  - `main_interpreter` envelope path
  - `subinterpreter` isolated path and fallback path
  - `thread_legacy` compatibility path
- Added concrete no-merge-back and side-effect application tests.
- Added ADR 0099 target directory scaffolding:
  - `tests/plugins/unit/README.md`
  - `tests/runtime/parity/README.md`
  - `tests/helpers/__init__.py`
  - `tests/helpers/plugin_execution.py`

Updated point-in-time metrics after changes:
- `_set_execution_context` references in tests: **173**
- `get_published_data` references in tests: **9**
- `pytest.skip()` in `tests/runtime/scheduler`: **0**
- `pytest.skip()` in all tests: **3**

Status impact:
- AC4 (scheduler no-merge-back routing coverage): materially improved and now executable.
- Remaining blockers are primarily legacy migration breadth (173 context-setup calls) and full layer rollout.

## Incremental Update 2 (2026-04-21, wave-2 fixture migration)

Completed in this iteration:
- Added reusable fixture publisher helper:
  - `tests/helpers/plugin_execution.py::publish_for_test(...)`
- Migrated broad validator fixture setup from direct `ctx._set_execution_context(...)` blocks
  to helper-based publish calls across integration suites.
- Updated missing-consume assertions in selected tests to accept runtime contract code `E8003`
  alongside plugin-specific legacy codes.
- Fixed declarative parity suite helper import and executed parity coverage.

Updated point-in-time metrics after wave-2 changes:
- `_set_execution_context` references in tests: **86** (down from 173 in update 1)
- `_set_execution_context` references in `tests/plugin_integration`: **60**
- `pytest.skip()` in `tests/runtime/scheduler`: **0**
- `pytest.skip()` in all tests: **3** (v4 baseline parity skips only)

Validation evidence (targeted, post-change):
- `pytest` suite over modified integration + scheduler files:
  - **450 passed**, 0 failed (`~1m40s`)
- Focused parity/contract subset:
  - **63 passed**, 0 failed

## Incremental Update 3 (2026-04-21, parity/order cleanup and helper hardening)

Completed in this iteration:
- Simplified `tests/helpers/plugin_execution.py::publish_for_test(...)` to a
  single explicit signature (`ctx, producer_plugin_id, key, value`).
- Removed direct `_set_execution_context(...)` usage from all tests touched in
  the current migration wave; changed files now use `run_plugin_for_test(...)`
  or `publish_for_test(...)`.
- Restored `tests/plugin_integration/test_parity_stage_order.py` to green by
  isolating the suite from unrelated framework-lock verification and by moving
  fixture publication onto helper-based setup.
- Added helper usage guidance to `tests/helpers/README.md` and expanded the new
  ADR0099 README stubs for plugin-unit and runtime-parity layers.
- Replaced deprecated `subinterpreter_compatible` manifest snippets in touched
  integration tests with explicit `execution_mode: subinterpreter`.

Updated point-in-time metrics after parity/order cleanup:
- `_set_execution_context` references in tests: **62**
- `_set_execution_context` references in `tests/plugin_integration`: **36**
- files in `tests/` still containing `_set_execution_context`: **14**
- files in `tests/` still containing `_set_execution_context` outside helpers: **13**
- `pytest.skip()` in `tests/runtime/scheduler`: **0**
- `pytest.skip()` in all tests: **3** (v4 baseline parity skips only)

Validation evidence (targeted, post-change):
- `pytest` over changed integration + scheduler suites:
  - **474 passed**, 0 failed (`~1m26s`)
- `pytest tests/plugin_integration/test_parity_stage_order.py -q`
  - **24 passed**, 0 failed

## 1. Problem Inventory

| ID | Problem | Severity | Impact |
|----|---------|----------|--------|
| P1 | 66 test files call `_set_execution_context` | CRITICAL | Blocks legacy removal |
| P2 | `SerializablePluginContext` class exists (144 lines) | HIGH | Technical debt |
| P3 | `test_adr0097_parity.py` tests dead code (568 lines) | HIGH | False confidence |
| P4 | Missing `tests/plugins/unit/` directory | MEDIUM | ADR 0099 non-compliance |
| P5 | Missing `tests/runtime/parity/` directory | MEDIUM | ADR 0099 non-compliance |
| P6 | 15 skipped tests (8 PR2-related) | MEDIUM | Untested code paths |
| P7 | Only 6 tests use envelope API | HIGH | Envelope model untested |
| P8 | `_mirror_context_into_pipeline_state` referenced | MEDIUM | Confusion |
| P9 | ADR 0097 marked "Proposed" in REGISTER.md | LOW | Misleading status |
| P10 | 4 of 9 acceptance criteria unmet | CRITICAL | ADR 0099 blocked |

## 2. Root Cause Analysis

### RC1: Tests bypass runtime execution model
- Tests call `ctx._set_execution_context()` directly
- 66 files affected (372 call sites)
- Prevents runtime API deprecation

### RC2: Dead code not removed after ADR 0097 PR4
- `SerializablePluginContext` never deleted (144 lines in plugin_base.py)
- Test file tests dead code (568 lines in test_adr0097_parity.py)

### RC3: Test directory structure not aligned with ADR 0099
- Missing `unit/` and `parity/` directories
- Tests scattered without layer organization

### RC4: Envelope API adoption incomplete
- Only 6 of ~70 test files use modern API
- No migration path documented for existing tests

## 3. Quantified Metrics

### Legacy Pattern Usage

| Pattern | Runtime | Tests | Total |
|---------|---------|-------|-------|
| `_set_execution_context` | 1 (def) | 186 | 187 |
| `_clear_execution_context` | 1 (def) | 186 | 187 |
| `SerializablePluginContext` | 3 | 1 | 4 |
| `_mirror_context_into_pipeline_state` | 1 (def) | 2 | 3 |

### Dead Code Inventory

| Location | Lines | Type |
|----------|-------|------|
| `plugin_base.py:977-1120` | ~144 | SerializablePluginContext class |
| `plugin_base.py` | ~24 | _mirror_context_into_pipeline_state |
| `plugin_base.py` | ~37 | thread_legacy conditionals |
| `test_adr0097_parity.py` | ~568 | Tests for dead code |
| **TOTAL** | **~773** | |

### Test Classification

| Category | Files | Percentage |
|----------|-------|------------|
| Legacy-only | ~60 | 50% |
| Hybrid | ~6 | 5% |
| Modern (envelope) | ~3 | 2.5% |
| Neutral | ~48 | 40% |
| Dead code tests | 1 | <1% |

## 4. Constraint Violations

| Constraint | Current State | Required State |
|------------|---------------|----------------|
| C1: No legacy in new tests | 66 files violate | 0 files |
| C2: SerializablePluginContext removed | Exists (144 lines) | Deleted |
| C4: 5 test layers exist | 3 of 5 | 5 of 5 |
| C5: Skipped tests resolved | 15 skipped | 0 skipped |
| C6: All tests use envelope API | 6 files | ~70 files |
| C11: Dead code deleted | ~773 lines | 0 lines |

## 5. ADR 0099 Acceptance Criteria Status

| AC# | Criterion | Status |
|-----|-----------|--------|
| AC1 | Plugin unit tests use snapshot-based execution | PARTIAL (6 files) |
| AC2 | Worker runner tests verify isolation | MINIMAL (1 file) |
| AC3 | Pipeline state tests verify commit semantics | EXISTS |
| AC4 | Scheduler tests verify no merge-back | EXISTS (skipped) |
| AC5 | Parity tests verify behavioral equivalence | EXISTS |
| AC6 | Zero `_set_execution_context` in new tests | NOT MET (66 files) |
| AC7 | Determinism tests exist | EXISTS |
| AC8 | Contract tests exist | EXISTS |
| AC9 | Dead code removed | NOT MET |

**Met:** 4/9 (44%)
**Not Met:** 5/9 (56%)

## 6. Risk Summary

| Risk | Probability | Impact | Priority |
|------|-------------|--------|----------|
| Breaking tests during migration | HIGH | HIGH | P0 |
| Incomplete migration (hybrid state) | MEDIUM | HIGH | P1 |
| New tests with legacy patterns | MEDIUM | MEDIUM | P1 |
| Dead code re-introduced | LOW | LOW | P3 |

## 7. Recommended Actions

1. **Immediate:** Delete dead code (SerializablePluginContext, dead tests)
2. **Short-term:** Create test helper and directory structure
3. **Medium-term:** Wave migration of 66 test files
4. **Final:** Delete legacy methods, update ADR status

See `IMPLEMENTATION-PLAN.md` for detailed execution plan.
