# CI Verification Checklist — Python 3.14 Migration

**Branch**: `implementation_imprvement`
**Date**: 2026-04-14
**Status**: Monitoring

---

## GitHub Actions Links

**Base URL**: `https://github.com/strateg/home-lab/actions`

Direct links to check:
- https://github.com/strateg/home-lab/actions/workflows/plugin-validation.yml
- https://github.com/strateg/home-lab/actions/workflows/python-checks.yml
- https://github.com/strateg/home-lab/actions/workflows/lane-validation.yml
- https://github.com/strateg/home-lab/actions/workflows/topology-matrix.yml
- https://github.com/strateg/home-lab/actions/workflows/deploy-runner-backends.yml
- https://github.com/strateg/home-lab/actions/workflows/security.yml

---

## Workflows to Monitor

| Workflow | Python Version | Critical? | Expected Outcome |
|----------|----------------|-----------|------------------|
| plugin-validation.yml | 3.14 (matrix) | ✅ YES | All plugin tests pass |
| python-checks.yml | 3.14 only | ✅ YES | Linting, type checking pass |
| lane-validation.yml | 3.14 | ✅ YES | Lane orchestrator tests pass |
| topology-matrix.yml | 3.14 | ✅ YES | Topology compilation passes |
| deploy-runner-backends.yml | 3.14 | ⚠️ MEDIUM | Deploy tooling functional |
| security.yml | 3.14 | ⚠️ MEDIUM | Security scans pass |

---

## Expected Results

### Success Criteria (ALL must pass)

- [ ] plugin-validation.yml: ✅ Green
- [ ] python-checks.yml: ✅ Green
- [ ] lane-validation.yml: ✅ Green
- [ ] topology-matrix.yml: ✅ Green
- [ ] deploy-runner-backends.yml: ✅ Green (or acceptable failures)
- [ ] security.yml: ✅ Green (or acceptable warnings)

### Known Acceptable Failures

Based on local test results (97.5% pass rate):

- **19 test failures**: Existing issues not related to Python 3.14
  - 5× `test_parity_stage_order.py` (fail on 3.13 too)
  - 14× TUC/regression tests (need investigation)

These failures should also appear in CI and are **acceptable** for Phase B gate.

---

## If CI Fails

### Investigate

1. Check workflow logs for Python 3.14 specific errors
2. Compare with local test results (.venv-3.14)
3. Identify if failure is:
   - **Type A**: Python 3.14 regression (BLOCKER)
   - **Type B**: Existing test failure (ACCEPTABLE)
   - **Type C**: CI environment issue (INVESTIGATE)

### Actions

**Type A (3.14 regression):**
```bash
# Reproduce locally
.venv-3.14/bin/python -m pytest <failing_test> -vv

# Fix and commit
git add <fixed_files>
git commit -m "fix(adr0098): resolve Python 3.14 regression in <area>"
git push
```

**Type B (existing failure):**
- Document in CI-VERIFICATION-CHECKLIST.md
- Proceed with Phase B gate if count ≤ 19 failures

**Type C (CI environment):**
- Check GitHub Actions Python 3.14 setup
- Verify dependencies installed correctly
- May need workflow adjustments

---

## When All Green

### Phase B Gate: PASSED ✅

1. Update ADR 0098:
   - Status: Phase C (Contract Flip)
   - Evidence: Link to this checklist + CI run URLs

2. Create Phase C plan:
   - Production `.venv` migration
   - Operator environment setup
   - Rollback procedures

3. Notify team:
   - Python 3.14 is now CI baseline
   - All new development must use 3.14+

---

## Manual Verification Commands

If you want to verify locally before/during CI:

```bash
# Full test suite (matches CI)
.venv-3.14/bin/python -m pytest tests/ -v

# Specific workflow equivalent
.venv-3.14/bin/python -m pytest tests/plugin_integration/ -v  # plugin-validation
.venv-3.14/bin/python -m pylint topology-tools/              # python-checks
V5_SECRETS_MODE=passthrough .venv-3.14/bin/python scripts/orchestration/lane.py validate-v5  # lane-validation
```

---

## Status Updates

| Timestamp | Workflow | Status | Notes |
|-----------|----------|--------|-------|
| 2026-04-14 07:15 | ALL | ⏳ Pending | Pushed, waiting for CI |
| | | | |
| | | | |

---

**Last Updated**: 2026-04-14 07:15 UTC
**Next Check**: Monitor GitHub Actions page
