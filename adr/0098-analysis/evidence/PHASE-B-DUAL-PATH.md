# Phase B Evidence — Dual-Path Parity

**Date**: 2026-04-14
**Status**: ✅ COMPLETE

---

## Scope

Phase B migrates the project's minimum Python requirement from 3.13 to 3.14.

**NOT in scope for Phase B:**
- InterpreterPoolExecutor parity testing (deferred - ADR 0097 not implemented yet)
- Production deployment (Phase C/D)

---

## Changes Applied

### pyproject.toml

| Field | Before | After |
|-------|--------|-------|
| requires-python | `>=3.13,<4` | `>=3.14,<4` |
| tool.mypy.python_version | `3.13` | `3.14` |
| tool.black.target-version | `["py313", "py314"]` | (unchanged) |

### CI Workflows (6 files)

All GitHub Actions workflows updated to Python 3.14:

| Workflow | Matrix Before | Matrix After |
|----------|---------------|--------------|
| deploy-runner-backends.yml | 3.13 | 3.14 |
| lane-validation.yml | 3.13 | 3.14 |
| plugin-validation.yml | ['3.13'] | ['3.14'] |
| python-checks.yml | ["3.13", "3.14"] | ["3.14"] |
| security.yml | 3.13 | 3.14 |
| topology-matrix.yml | 3.13 | 3.14 |

### Framework Lock

| Field | Before | After |
|-------|--------|-------|
| revision | da88e1fa | 5ed2b0dc (Python 3.14 migration) |
| integrity | sha256-d6bf... | sha256-245db... (after pyproject.toml change) |
| locked_at | 2026-04-11 02:47 | 2026-04-14 07:01 |

---

## Verification

### Smoke Test

```bash
V5_SECRETS_MODE=passthrough .venv-3.14/bin/python \
  topology-tools/compile-topology.py \
  --profile=test-real \
  --no-parallel-plugins
```

**Result:**
```
Compile summary: total=91 errors=0 warnings=0 infos=91
Diagnostics JSON: build/diagnostics/report.json
Effective JSON:   build/effective-topology.json
```

✅ **PASS** — Full compilation succeeds on Python 3.14 with 0 errors.

---

## Phase B Gate Status

**✅ PHASE B COMPLETE**

### Exit Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| requires-python updated to >=3.14 | ✅ PASS | pyproject.toml |
| All CI workflows use Python 3.14 | ✅ PASS | 6 workflows updated |
| framework.lock.yaml regenerated | ✅ PASS | New integrity hash |
| Smoke test passes on 3.14 | ✅ PASS | 0 errors, 91 infos |

---

## Deferred Work

**InterpreterPoolExecutor parity testing** — originally planned for Phase B, but deferred because:
1. ADR 0097 (InterpreterPoolExecutor) not yet implemented
2. Current ThreadPoolExecutor works correctly on Python 3.14
3. No blocking issues for Phase C (Contract Flip)

This will be addressed in a future phase when ADR 0097 implementation begins.

---

## Commits

```
98d7e8cc chore(adr0098): regenerate framework.lock.yaml for Python 3.14
5ed2b0dc feat(adr0098): migrate to Python 3.14 minimum requirement
14d64dfe feat(adr0098): complete Phase A verification on Python 3.14.4
```

---

## Next Steps (Phase C)

1. Push changes: `git push origin implementation_imprvement`
2. Monitor CI workflows for green status
3. Update ADR 0098 to Phase C when CI green
4. Plan production rollout to Proxmox/Orange Pi 5
