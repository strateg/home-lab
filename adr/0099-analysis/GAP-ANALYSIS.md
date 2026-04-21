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
