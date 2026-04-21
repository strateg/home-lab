# ADR 0099 Cutover Checklist

**Purpose:** Final verification before marking ADR 0099 as Implemented

## Pre-Cutover Verification

### Dead Code Removal

- [ ] `SerializablePluginContext` class deleted from `plugin_base.py`
- [ ] `_mirror_context_into_pipeline_state` removed or marked internal
- [ ] `thread_legacy` conditionals removed
- [ ] `test_adr0097_parity.py` refactored (no dead code tests)

**Verification:**
```bash
grep -r "SerializablePluginContext" topology-tools/
# Expected: 0 matches

grep -r "thread_legacy" topology-tools/kernel/
# Expected: 0 matches (or only comments)
```

### Directory Structure

- [ ] `tests/plugins/unit/` exists with README.md
- [ ] `tests/runtime/parity/` exists with README.md
- [ ] `tests/helpers/` exists with `__init__.py` and `plugin_execution.py`

**Verification:**
```bash
ls -la tests/plugins/unit/
ls -la tests/runtime/parity/
ls -la tests/helpers/
```

### Legacy Pattern Migration

- [ ] Zero `_set_execution_context` calls outside `tests/helpers/plugin_execution.py`
- [ ] All 66 test files migrated to use helper
- [ ] CI baseline at 0 (or only helper file)

**Verification:**
```bash
grep -r "_set_execution_context" tests/ --include="*.py" -l | grep -v helpers
# Expected: 0 matches
```

### Test Execution

- [ ] All tests pass: `pytest tests/ -q`
- [ ] No skipped tests in `tests/runtime/scheduler/`
- [ ] Parity maintained (no behavioral changes)

**Verification:**
```bash
pytest tests/ -q
pytest tests/runtime/scheduler/ -v --tb=short
```

### CI Guards

- [ ] `.github/workflows/test-legacy-guard.yml` active
- [ ] `.github/legacy-baseline.txt` exists with value 0
- [ ] Guard blocks PRs with legacy patterns

### Documentation

- [ ] ADR 0097 status: Implemented in REGISTER.md
- [ ] ADR 0099 status: Implemented in REGISTER.md
- [ ] ADR 0099 status: Implemented in ADR file header
- [ ] Test helper documented in README

---

## Cutover Execution

### Step 1: Final Test Run
```bash
pytest tests/ -q --tb=short
```
**Expected:** All tests pass, 0 skipped in runtime/scheduler

### Step 2: Compliance Script
```bash
python scripts/validation/verify_adr0099_compliance.py
```
**Expected:** Exit code 0, "ADR 0099 COMPLIANT" message

### Step 3: Update ADR 0099 Status

**File:** `adr/0099-refactor-test-architecture-for-snapshot-envelope-pipeline-runtime.md`
```markdown
Status: Implemented
```

### Step 4: Update REGISTER.md

**File:** `adr/REGISTER.md`
```markdown
| 0099 | Test architecture for snapshot/envelope/pipeline runtime | Implemented |
```

### Step 5: Create Cutover Commit
```bash
git add -A
git commit -m "feat(tests): complete ADR 0099 test architecture migration

- Migrated 66 test files to envelope-based execution helper
- Deleted SerializablePluginContext dead code (~144 lines)
- Created test helper module (tests/helpers/plugin_execution.py)
- Added CI legacy pattern guard
- Created ADR 0099 compliance verification script

Closes ADR 0099.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Post-Cutover Verification

### Immediate (Same Day)

- [ ] CI pipeline passes on main branch
- [ ] No regression reports from developers
- [ ] Legacy guard blocks test PR with old pattern

### Short-term (1 Week)

- [ ] No new `_set_execution_context` introduced
- [ ] New tests use `run_plugin_for_test()` helper
- [ ] Compliance script runs in CI

### Long-term (1 Month)

- [ ] Migrate remaining tests to `run_plugin_isolated()`
- [ ] Consider deprecating `run_plugin_for_test()` helper
- [ ] Delete `_set_execution_context` method from runtime

---

## Rollback Procedure

If critical issues discovered post-cutover:

```bash
# Identify cutover commit
git log --oneline -5

# Revert cutover commit
git revert <cutover-commit-hash>

# Update baseline back to previous value
echo "372" > .github/legacy-baseline.txt

# Commit revert
git commit -m "revert: rollback ADR 0099 cutover due to <reason>"
```

**Rollback is safe** - no data loss, all changes are additive/removable.

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Implementer | | | |
| Reviewer | | | |
| Tech Lead | | | |

---

## Acceptance Criteria Verification

| AC# | Criterion | Verified |
|-----|-----------|----------|
| AC1 | Plugin unit tests use snapshot-based execution | [ ] |
| AC2 | Worker runner tests verify isolation | [ ] |
| AC3 | Pipeline state tests verify commit semantics | [ ] |
| AC4 | Scheduler tests verify no merge-back | [ ] |
| AC5 | Parity tests verify behavioral equivalence | [ ] |
| AC6 | Zero `_set_execution_context` in new tests | [ ] |
| AC7 | Determinism tests exist | [ ] |
| AC8 | Contract tests exist | [ ] |
| AC9 | Dead code removed | [ ] |

**All 9 criteria must be checked before marking ADR 0099 as Implemented.**
