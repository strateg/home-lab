# ADR 0098 — Implementation Plan (Aggressive Profile)

**Date**: 2026-04-13
**Profile**: Aggressive (gate-driven, hard cutover)
**Analyst**: Claude Sonnet 4.5 (SPC Mode)

---

## Executive Summary

**Strategy**: Gate-driven migration with **5 phases** replacing calendar-based waves

**Critical Success Factors**:
1. Phase A verification burst completes with all dependencies PASS
2. Phase B parity gate validates ThreadPool vs InterpreterPool equivalence
3. Rollback procedures ready before Phase E cutover

**Timeline**: Event-driven (not calendar-based), estimated 4-6 weeks total

---

## Phase Model Overview

| Phase | Name | Entry Gate | Exit Gate | Duration Est. | Rollback Risk |
|-------|------|------------|-----------|---------------|---------------|
| **A** | Verification Burst | Python 3.14 released | All deps verified | 3-5 days | None (no prod changes) |
| **B** | Dual-Path Parity | Phase A passed | Parity tests green | 5-7 days | Low (test-only) |
| **C** | Contract Flip | Phase B passed | CI green on 3.14 | 2-3 days | Medium (dev envs) |
| **D** | Integrated Validation | Phase C passed | Test nodes OK | 4-6 days | Medium (test nodes) |
| **E** | Production Cutover | Phase D passed | All nodes on 3.14 | 7-10 days | HIGH (prod impact) |

**Critical Path**: A → B → C → D → E (sequential, no parallelism)

---

## Phase A: Verification Burst

### Purpose

Verify Python 3.14 readiness across all dependencies and target platforms

### Entry Criteria

- [x] Python 3.14 officially released (stable, not beta/RC)
- [x] ADR 0098 status changed to "Accepted"
- [ ] Team capacity allocated for verification sprint

### Scope

#### A1. Dependency Verification (CRITICAL)

**Core Dependencies** (7 items):

```bash
# Verification script
for dep in pyyaml jinja2 jsonschema pytest pydantic ansible-core; do
    python3.14 -m pip install "$dep" --dry-run
    python3.14 -c "import $dep; print($dep.__version__)"
    # Document as EV-XXX evidence
done
```

**Output**: Evidence table with PASS/FAIL/BLOCKED status

| Dependency | Status | Evidence ID | Notes |
|------------|--------|-------------|-------|
| PyYAML | ⬜ Pending | EV-001 | - |
| Jinja2 | ⬜ Pending | EV-002 | - |
| jsonschema | ⬜ Pending | EV-003 | - |
| pytest | ⬜ Pending | EV-004 | - |
| pydantic | ⬜ Pending | EV-005 | - |
| ansible-core | ⬜ Pending | EV-006 | Known risk: 3.14 support in 2.17+ |

---

#### A2. C-Extension Compatibility (HIGH)

**C-extensions to verify**:
- `orjson` (fast JSON serialization)
- `ruamel.yaml` (YAML roundtrip)
- `pyyaml` (C accelerator)

**Test**:
```bash
python3.14 -m pip install orjson ruamel.yaml
python3.14 -c "import orjson; print(orjson.dumps({'test': True}))"
python3.14 -c "from ruamel.yaml import YAML; YAML().dump({'test': True}, sys.stdout)"
```

**Fallback**: If C-extension fails, identify pure-Python alternative

---

#### A3. Platform Availability Check (HIGH)

**Target Platforms**:
1. Proxmox host (x86_64, Debian-based)
2. Orange Pi 5 (ARM64, Ubuntu 22.04+)
3. LXC containers (both architectures)

**Verification**:
```bash
# Check deadsnakes PPA availability
ssh proxmox "apt-cache search python3.14"

# Check Orange Pi package availability
ssh orangepi "apt-cache search python3.14"

# Fallback: pyenv availability
pyenv install --list | grep 3.14
```

**Output**: Platform compatibility matrix

| Platform | Method | Status | Notes |
|----------|--------|--------|-------|
| Proxmox (x86_64) | apt (deadsnakes) | ⬜ Pending | - |
| Orange Pi 5 (ARM64) | apt (deadsnakes) | ⬜ Pending | - |
| LXC containers | Inherited from host | ⬜ Pending | - |
| Dev workstation | pyenv | ⬜ Pending | - |

---

#### A4. CI Preflight (MEDIUM)

**Actions**:
1. Add Python 3.14 to GitHub Actions matrix (experimental)
2. Run full test suite on 3.14
3. Collect failures and regressions
4. Fix 3.14-specific issues

**Test Command**:
```bash
python3.14 -m pytest tests/ -v --tb=short
```

**Gate**: CI green on Python 3.14 (no 3.14-specific failures)

---

### Exit Criteria (ALL must pass)

- [ ] ✅ **A1**: All core dependencies PASS (6/7 minimum, with alternatives for blocked)
- [ ] ✅ **A2**: C-extensions PASS or pure-Python alternatives identified
- [ ] ✅ **A3**: Python 3.14 confirmed available on all target platforms
- [ ] ✅ **A4**: CI green on Python 3.14 (full test suite)

**Go/No-Go Decision Point**: If ANY exit criterion fails, STOP and resolve before Phase B

---

### Rollback Criteria

**N/A** — No production changes in Phase A (verification only)

---

### Duration

**Estimated**: 3-5 days (verification burst)

**Parallel Work**:
- A1 + A2 can run concurrently (dependency + C-ext verification)
- A3 can run in parallel with A1/A2 (platform checks)
- A4 depends on A1 passing (CI needs dependencies)

---

## Phase B: Dual-Path Parity

### Purpose

Validate ThreadPoolExecutor vs InterpreterPoolExecutor produce identical outputs

### Entry Criteria

- [x] Phase A exit criteria passed
- [ ] ADR 0097 implementation complete (InterpreterPoolExecutor integrated)
- [ ] Parity test suite implemented (`tests/parity/`)

### Scope

#### B1. Parity Test Implementation (CRITICAL)

**Test Coverage**:
1. Full compilation pipeline (topology → compiled JSON)
2. Validation stage (all 57 plugins)
3. Generation stage (Terraform, Ansible, bootstrap)
4. Diagnostic output (errors, warnings, info)
5. Artifact checksums (byte-identical files)

**Test Script**:
```python
# tests/parity/test_executor_parity.py

import subprocess
import hashlib
from pathlib import Path

def test_sequential_vs_parallel_parity():
    """Verify ThreadPool and InterpreterPool produce identical outputs."""

    # Run sequential (ThreadPool)
    result_seq = run_compiler(parallel=False, use_subinterpreters=False)

    # Run parallel (InterpreterPool)
    result_par = run_compiler(parallel=True, use_subinterpreters=True)

    # Assert exit codes match
    assert result_seq.returncode == result_par.returncode

    # Assert stdout/stderr match (diagnostics)
    assert result_seq.stdout == result_par.stdout
    assert result_seq.stderr == result_par.stderr

    # Assert generated artifacts match (byte-identical)
    files_seq = list(Path("generated/home-lab").rglob("*"))
    files_par = list(Path("generated/home-lab-parallel").rglob("*"))

    assert len(files_seq) == len(files_par)

    for file_seq, file_par in zip(sorted(files_seq), sorted(files_par)):
        assert file_seq.name == file_par.name
        assert checksum(file_seq) == checksum(file_par)  # Byte-identical

def checksum(path: Path) -> str:
    """Compute SHA256 checksum of file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
```

---

#### B2. Parity Metrics Collection (HIGH)

**Metrics to track**:
- Execution time: ThreadPool vs InterpreterPool
- Memory usage: Peak RSS per executor
- Determinism: 10 repeated runs produce same output
- Plugin execution order: Submission order preserved

**Output**: Parity report

```markdown
### Parity Test Report

**Date**: 2026-04-XX
**Commit**: <commit-hash>

| Metric | ThreadPool | InterpreterPool | Delta | Status |
|--------|------------|-----------------|-------|--------|
| Exit code | 0 | 0 | ✅ Identical | PASS |
| Stdout bytes | 12345 | 12345 | ✅ Identical | PASS |
| Stderr bytes | 0 | 0 | ✅ Identical | PASS |
| Generated files | 247 | 247 | ✅ Identical | PASS |
| File checksums | SHA256 | SHA256 | ✅ All match | PASS |
| Execution time | 12.3s | 8.7s | -29% (faster) | PASS |
| Memory (peak RSS) | 450MB | 520MB | +15% (acceptable) | PASS |
| Determinism (10 runs) | Identical | Identical | ✅ | PASS |
```

---

#### B3. Regression Detection (MEDIUM)

**Comparison baseline**: Python 3.13 + ThreadPool

**Test cases**:
1. Topology with 100+ instances (stress test)
2. Complex validation rules (all validators)
3. Multi-generator pipeline (Terraform + Ansible + docs)
4. Error handling paths (intentional validation failures)

**Goal**: Ensure no regressions between:
- Python 3.13 + ThreadPool (baseline)
- Python 3.14 + ThreadPool (platform change)
- Python 3.14 + InterpreterPool (platform + executor change)

---

### Exit Criteria (ALL must pass)

- [ ] ✅ **B1**: Parity test suite passes (ThreadPool == InterpreterPool outputs)
- [ ] ✅ **B2**: Parity report shows <5% performance variance
- [ ] ✅ **B3**: No regressions detected vs 3.13 baseline

**Go/No-Go Decision**:
- **GO** → Phase C (combined migration)
- **NO-GO** → Decouple migrations:
  - Option 1: Proceed with Python 3.14 only (defer ADR 0097)
  - Option 2: Fix parity issue (extend Phase B, investigate non-determinism)
  - Option 3: Abort migration (rollback to 3.13)

---

### Rollback Criteria

- ❌ Parity test fails after 3 attempts
- ❌ Performance regression >20% (unacceptable)
- ❌ Non-deterministic output detected (different results per run)

**Rollback Procedure**:
1. Document failure mode (logs, checksums, diff)
2. File issue in ADR 0097 tracker
3. Revert to Python 3.13 + ThreadPool
4. Investigate root cause before retry

---

### Duration

**Estimated**: 5-7 days

**Breakdown**:
- B1 test implementation: 2-3 days
- B2 metrics collection: 1-2 days
- B3 regression testing: 2 days

---

## Phase C: Contract Flip

### Purpose

Update all contract files to require Python 3.14 (development environment)

### Entry Criteria

- [x] Phase B exit criteria passed (parity validated)
- [ ] Team communication sent (upgrade notice, 7-day warning)

### Scope

#### C1. Version File Updates (CRITICAL)

**Files to update**:
```bash
# .python-version
3.14.0

# pyproject.toml
[tool.poetry]
requires-python = ">=3.14"

# requirements.txt (if present)
# Update lockfile with python_version = "3.14"
```

**Commands**:
```bash
echo "3.14.0" > .python-version
sed -i 's/requires-python = ">=3.11"/requires-python = ">=3.14"/' pyproject.toml
poetry lock --update  # Regenerate lockfile
```

---

#### C2. CI Matrix Update (HIGH)

**Staged Transition** (two-step):

**Step C2.1: Dual-Lane CI** (temporary)
```yaml
# .github/workflows/ci.yml

strategy:
  matrix:
    python-version: ['3.14']  # Primary lane
    include:
      - python-version: '3.13'
        experimental: true  # Rollback lane (allowed failures)

jobs:
  test:
    continue-on-error: ${{ matrix.experimental }}
```

**Step C2.2: Remove 3.13 Lane** (after Phase C exit gate)
```yaml
strategy:
  matrix:
    python-version: ['3.14']  # 3.13 removed
```

---

#### C3. Developer Environment Migration (MEDIUM)

**Communication**:
```markdown
## Python 3.14 Migration — Action Required

**Timeline**: Upgrade by <date>
**Impact**: Python 3.13 no longer supported after Phase C

**Upgrade Steps**:
1. Install Python 3.14: `pyenv install 3.14.0`
2. Update local repo: `git pull origin main`
3. Recreate venv: `rm -rf .venv && python3.14 -m venv .venv`
4. Install deps: `.venv/bin/pip install -r requirements.txt`
5. Verify: `python --version` (should show 3.14.x)

**Support**: Contact #infrastructure for issues
```

---

### Exit Criteria (ALL must pass)

- [ ] ✅ **C1**: `.python-version`, `pyproject.toml`, lockfiles updated
- [ ] ✅ **C2.1**: Dual-lane CI green (3.14 primary + 3.13 rollback)
- [ ] ✅ **C3**: All contributors confirmed upgraded (dev env survey)

**Gate for C2.2** (remove 3.13 lane):
- [ ] 100% of active contributors on Python 3.14
- [ ] No 3.13-specific CI failures for 2 weeks
- [ ] Phase C.1 + C.3 completed

---

### Rollback Criteria

- ❌ >30% of contributors unable to upgrade (blockers identified)
- ❌ CI fails on Python 3.14 after contract flip (unexpected regression)
- ❌ Critical blocker discovered (dependency, tooling)

**Rollback Procedure**:
1. Revert `.python-version` and `pyproject.toml`
2. Revert CI matrix to 3.13 primary
3. Regenerate lockfiles with Python 3.13
4. Notify team of rollback + reason

**Rollback Deadline**: 3 days after contract flip

---

### Duration

**Estimated**: 2-3 days

**Breakdown**:
- C1 file updates: 1 hour
- C2.1 dual-lane CI: 1 day (monitor for issues)
- C3 dev env migration: 2-3 days (team coordination)
- C2.2 remove 3.13 lane: After exit gate (1 week buffer)

---

## Phase D: Integrated Validation

### Purpose

Validate full pipeline on Python 3.14 with test node bootstrap

### Entry Criteria

- [x] Phase C exit criteria passed (contract flipped)
- [ ] Test nodes allocated (1x Proxmox LXC, 1x Orange Pi container)

### Scope

#### D1. Full Pipeline Validation (CRITICAL)

**Test Sequence**:
```bash
# Run full validate-v5 → build-v5 cycle
V5_SECRETS_MODE=passthrough python scripts/orchestration/lane.py validate-v5
python topology-tools/compile-topology.py
python scripts/orchestration/lane.py build-v5
```

**Validation**:
- No Python 3.14-specific errors
- All plugins execute successfully
- Generated artifacts match expected schema

---

#### D2. Bootstrap Rehearsal (HIGH)

**Test Node Setup**:
1. Provision fresh LXC container (Proxmox)
2. Provision fresh Docker container (Orange Pi)
3. Run bootstrap with Python 3.14 installation

**Bootstrap Script**:
```bash
# Bootstrap rehearsal
ansible-playbook ansible/playbooks/bootstrap-node.yml \
  --extra-vars "target_python_version=3.14" \
  --limit test-node-01
```

**Validation**:
- Python 3.14 installed successfully
- All Ansible roles complete
- Node reports healthy status

---

#### D3. Deployment Bundle Test (MEDIUM)

**Test**:
```bash
# Create deployment bundle
task bundle:create

# Deploy to test node
task deploy:service-chain-evidence-apply-bundle -- \
  BUNDLE=<bundle-id> \
  ALLOW_APPLY=YES \
  TARGET=test-node-01
```

**Validation**:
- Bundle creation succeeds
- Deployment applies cleanly
- Services start successfully

---

### Exit Criteria (ALL must pass)

- [ ] ✅ **D1**: Full validation + build passes on Python 3.14
- [ ] ✅ **D2**: Test nodes bootstrapped with Python 3.14
- [ ] ✅ **D3**: Deployment bundle applies successfully

**Go/No-Go Decision**:
- **GO** → Phase E (production cutover)
- **NO-GO** → Extend Phase D (fix issues, retry)

---

### Rollback Criteria

- ❌ Bootstrap fails on >50% of test nodes
- ❌ Generated artifacts differ from Phase B baseline
- ❌ Deployment bundle failures

**Rollback Procedure**:
1. Preserve test node state for investigation
2. Halt production rollout
3. Fix issues in Phase D (extend timeline)
4. Retry validation

**Rollback Deadline**: N/A (test-only phase)

---

### Duration

**Estimated**: 4-6 days

**Breakdown**:
- D1 pipeline validation: 1-2 days
- D2 bootstrap rehearsal: 2-3 days (multi-platform)
- D3 deployment bundle: 1 day

---

## Phase E: Production Cutover

### Purpose

Migrate all production nodes to Python 3.14

### Entry Criteria

- [x] Phase D exit criteria passed (test nodes validated)
- [ ] Change control approved (maintenance window scheduled)
- [ ] Rollback artifacts preserved (3.13 venvs, lockfiles)

### Scope

#### E1. Production Node Migration (CRITICAL)

**Migration Sequence**:
1. Proxmox host (hypervisor)
2. LXC containers (low-risk services first)
3. Orange Pi 5 (media services, last)

**Per-Node Procedure**:
```bash
# Backup current state
ssh $NODE "tar czf /backup/python-3.13-$(date +%Y%m%d).tar.gz /opt/venv"

# Install Python 3.14
ansible-playbook ansible/playbooks/upgrade-python.yml --limit $NODE

# Verify installation
ssh $NODE "python3 --version"  # Should show 3.14.x

# Redeploy services
task deploy:service-chain-evidence-apply-bundle -- \
  NODE=$NODE \
  BUNDLE=<latest-bundle>
```

---

#### E2. Runtime Hard Gate (HIGH)

**Enforce Python 3.14 requirement**:
```python
# topology-tools/compile-topology.py (line 1)

import sys
if sys.version_info < (3, 14):
    raise SystemExit(
        "Python 3.14+ required. Current: {}.{}".format(
            sys.version_info.major, sys.version_info.minor
        )
    )
```

**Remove 3.13 compatibility**:
- Delete `if sys.version_info >= (3, 14):` conditionals
- Remove feature flags for 3.14-specific code
- Clean up version-specific workarounds

---

#### E3. Final Contract Cleanup (MEDIUM)

**Remove 3.13 remnants**:
- Remove 3.13 rollback lane from CI (if still present)
- Update all documentation (3.11+ → 3.14+)
- Archive 3.13 lockfiles (move to `archive/python-3.13/`)

---

### Exit Criteria (ALL must pass)

- [ ] ✅ **E1**: All production nodes running Python 3.14
- [ ] ✅ **E2**: Runtime hard gate enforced (3.13 rejected)
- [ ] ✅ **E3**: No 3.13 compatibility code remains

**Final Acceptance**: ADR 0098 status updated to "Accepted (Implemented)"

---

### Rollback Criteria (CRITICAL)

**Triggers** (ANY of these):
- ❌ >5% of nodes fail migration
- ❌ Production service outages (not observed in Phase D)
- ❌ Performance regression >20% on real workloads
- ❌ Critical bug discovered (not caught in testing)

**Rollback Procedure**:
```bash
# 1. FREEZE: Stop new deployments
echo "ROLLBACK IN PROGRESS" > /etc/motd

# 2. REVERT NODES: Restore 3.13 venv backups
ansible-playbook ansible/playbooks/rollback-python.yml

# 3. REVERT CI: Re-enable 3.13 lane
git revert <contract-flip-commit>

# 4. REVERT RUNTIME: Remove version gate
git revert <hard-gate-commit>

# 5. POST-MORTEM: Investigate failure
# Document in adr/0098-analysis/ROLLBACK-REPORT.md
```

**Rollback Deadline**: **48 hours** after Phase E start
- After 48h, forward fix is cheaper than rollback
- Commit to 3.14 and resolve issues in-place

---

### Duration

**Estimated**: 7-10 days

**Breakdown**:
- E1 node migration: 5-7 days (staged rollout)
- E2 hard gate: 1 day
- E3 cleanup: 1-2 days

**Monitoring Window**: 14 days post-cutover
- Watch for unexpected issues
- Rollback window closes after 48h
- After 14 days, Phase E considered stable

---

## Compliance Matrix

### ADR Policy Alignment

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Gate-driven execution | ✅ | 5 phases with entry/exit criteria |
| Evidence-based decisions | ✅ | Phase A compatibility matrix |
| Rollback procedures | ✅ | Defined for Phases C, D, E |
| Risk mitigation | ✅ | Phase B parity gate |
| ADR analysis directory | ✅ | `adr/0098-analysis/` created |

---

### SPC Mode Requirements

| Step | Requirement | Status |
|------|-------------|--------|
| 0 | Problem understanding | ✅ |
| 1 | Constraints registered | ✅ |
| 2 | SWOT analysis | ✅ |
| 3 | Critique | ✅ |
| 4 | Improvements | ✅ |
| 5 | Implementation plan | ✅ (this document) |
| 6 | Compliance check | ✅ |
| 7 | Final validation | ✅ |

**Verdict**: Plan complies with all SPC Mode requirements

---

## Risk Register Summary

| Risk ID | Description | Phase | Mitigation | Severity |
|---------|-------------|-------|------------|----------|
| R-A1 | Dependency incompatible | A | Evidence matrix, alternatives | CRITICAL |
| R-B1 | Parity test fails | B | Decouple migrations | CRITICAL |
| R-C1 | Team unable to upgrade | C | Dual-lane CI, support | HIGH |
| R-D1 | Bootstrap failures | D | Multi-platform testing | HIGH |
| R-E1 | Production outage | E | Rollback within 48h | CRITICAL |

---

## Success Metrics

| Metric | Target | Tracking |
|--------|--------|----------|
| Dependency compatibility | 100% core deps PASS | Phase A exit |
| Parity test success | 100% byte-identical | Phase B exit |
| Developer upgrade rate | 100% within 1 week | Phase C exit |
| Test node success | 100% operational | Phase D exit |
| Production cutover | 100% nodes migrated | Phase E exit |
| Rollback usage | 0 rollbacks | Post-cutover monitoring |

---

## Next Steps

1. **Update ADR 0098**: Incorporate improvements from IMPROVEMENTS.md
2. **Execute Phase A**: Begin dependency verification burst
3. **Create evidence artifacts**: `adr/0098-analysis/evidence/EV-*.md`
4. **Monitor gates**: Track exit criteria for each phase
5. **Update status**: "Proposed" → "Accepted" after Phase A → "Implemented" after Phase E

---

**Plan Metadata**:
- **Profile**: Aggressive (hard cutover, gate-driven)
- **Critical Path**: A → B → C → D → E (sequential)
- **Estimated Duration**: 4-6 weeks (variable based on gate passage)
- **Rollback Windows**: Phase C (3 days), Phase E (48 hours)
- **Success Criteria**: All phases pass exit gates, no rollbacks needed
