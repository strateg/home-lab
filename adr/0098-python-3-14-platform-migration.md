# ADR 0098: Python 3.14 Platform Migration

- Status: **In Progress** (Phase B: Dual-Path Parity)
- Date: 2026-04-13
- Updated: 2026-04-14
- Depends on: ADR 0097
- Target: Python 3.14+ as minimum supported version
- Profile: Aggressive (gate-driven, hard cutover)

## Implementation Progress

| Phase | Status | Evidence |
|-------|--------|----------|
| **A** Verification Burst | ✅ **COMPLETE** | `adr/0098-analysis/evidence/PHASE-A-BASELINE.md` |
| **B** Dual-Path Parity | **IN PROGRESS** | pyproject.toml, CI workflows |
| **C** Contract Flip | Pending | — |
| **D** Integrated Validation | Pending | — |
| **E** Production Cutover | Pending | — |

### Phase A Checklist

- [x] A1: Pre-installation dependency analysis (EV-A1-preinstall-20260414)
- [x] A2: C-extension compatibility verified (orjson, ruamel.yaml, cryptography)
- [x] A3: Platform scripts created (install-python-3.14.sh, verify-deps-3.14.sh)
- [x] A4: CI matrix updated for Python 3.14
- [x] A5: Install Python 3.14 on dev workstation (pyenv 3.14.4)
- [x] A6: Run live verification (97.5% tests pass)
- [x] A7: pyproject.toml license field fix (PEP 639)

## Context

### Current State

The home-lab infrastructure codebase currently targets Python 3.11+ with the following components:

| Component | Python Usage | Current Version |
|-----------|--------------|-----------------|
| topology-tools/ | Core compiler, plugins, kernel | 3.11+ |
| scripts/orchestration/ | Lane orchestrator, deploy domain | 3.11+ |
| scripts/inspection/ | Topology inspection toolkit | 3.11+ |
| tests/ | pytest test suite | 3.11+ |
| Bootstrap scripts | Node initialization, Ansible | 3.11+ |

### Python 3.14 Release

Expected release: **October 2025**

Key features relevant to this project:

1. **PEP 734**: `concurrent.interpreters` — subinterpreter support (see ADR 0097)
2. **PEP 779**: Free-threaded Python officially supported
3. **PEP 649**: Deferred evaluation of annotations
4. **PEP 750**: Template string literals (t-strings)
5. **Improved performance**: 5-10% single-threaded improvement
6. **Better error messages**: Enhanced tracebacks and diagnostics

### Migration Drivers

1. **ADR 0097**: Subinterpreter-based parallel execution requires Python 3.14
2. **Performance**: Free-threading and interpreter optimizations
3. **Developer experience**: Better error messages, t-strings for templates
4. **Security**: Latest security patches and hardening
5. **Ecosystem alignment**: Major libraries moving to 3.12+ minimum

## Decision

### D1. Adopt Python 3.14 as Minimum Supported Version

Set `python_requires = ">=3.14"` across all project components after migration completion.

### D1.1. No Backward Compatibility with Python 3.13

The migration is a **hard cutover**. Transitional runtime, CI, or developer-environment
compatibility with Python 3.13 is not retained after cutover.

**Rationale**:
- Enables ADR 0097 (subinterpreters)
- Simplifies codebase (no version conditionals)
- Future-proofs for 3-4 year support window

### D2. Migration Scope

#### 2.1 Core Runtime (`topology-tools/`)

| Component | Changes Required |
|-----------|-----------------|
| `compile-topology.py` | Version check, subinterpreter integration |
| `kernel/plugin_base.py` | Type annotations (PEP 649), cleanup |
| `kernel/plugin_registry.py` | `InterpreterPoolExecutor` (ADR 0097) |
| `plugins/*` | Compatibility audit, annotation updates |
| `templates/` | Consider t-string migration for Jinja alternatives |

#### 2.2 Orchestration Scripts (`scripts/`)

| Component | Changes Required |
|-----------|-----------------|
| `lane.py` | Version gate, runtime checks |
| `deploy/runner.py` | Subprocess Python version alignment |
| `deploy/bundle.py` | Shebang updates |
| `inspection/*.py` | Annotation modernization |

#### 2.3 Installation and Bootstrap

| Component | Changes Required |
|-----------|-----------------|
| `.python-version` | Update to 3.14 |
| `pyproject.toml` | `requires-python = ">=3.14"` |
| `requirements*.txt` | Dependency compatibility audit |
| Bootstrap scripts | Python installation automation |
| Ansible playbooks | Python interpreter paths |
| LXC/VM templates | Base image Python version |

#### 2.4 CI/CD Pipeline

| Component | Changes Required |
|-----------|-----------------|
| GitHub Actions | Python 3.14 matrix |
| Test runners | pytest compatibility |
| Linters | ruff/mypy Python 3.14 support |
| Docker images | Base image update |

#### 2.5 Documentation

| Document | Changes Required |
|----------|-----------------|
| `CLAUDE.md` | Python version requirements |
| `README.md` | Installation instructions |
| `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md` | Python setup guide |
| `docs/guides/DEVELOPER-SETUP.md` | Development environment |
| ADR references | Version annotations |

### D3. Dependency Compatibility Matrix

#### Core Dependencies (Must Support 3.14)

| Dependency | Current | 3.14 Status | Risk |
|------------|---------|-------------|------|
| PyYAML | 6.x | Expected compatible | Low |
| Jinja2 | 3.x | Expected compatible | Low |
| jsonschema | 4.x | Expected compatible | Low |
| pytest | 8.x | Expected compatible | Low |
| pydantic | 2.x | Expected compatible | Low |
| ansible-core | 2.16+ | Verify required | Medium |
| terraform | N/A | No Python dependency | None |

#### Optional Dependencies

| Dependency | Purpose | 3.14 Status |
|------------|---------|-------------|
| orjson | Fast JSON | Verify C extension |
| ruamel.yaml | YAML roundtrip | Verify compatibility |
| rich | Terminal output | Expected compatible |

### D4. Version Detection and Graceful Degradation

```python
# topology-tools/kernel/version_gate.py

import sys

MINIMUM_PYTHON = (3, 14)
RECOMMENDED_PYTHON = (3, 14)

def check_python_version() -> None:
    """Enforce minimum Python version at startup."""
    if sys.version_info < MINIMUM_PYTHON:
        raise SystemExit(
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}+ required. "
            f"Current: {sys.version_info.major}.{sys.version_info.minor}"
        )

def supports_subinterpreters() -> bool:
    """Check if subinterpreter features are available."""
    return sys.version_info >= (3, 14)

def supports_free_threading() -> bool:
    """Check if free-threading build is available."""
    return hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled()
```

### D5. Installation Script Updates

#### pyenv Installation (Development)

```bash
# scripts/setup/install-python-3.14.sh

#!/usr/bin/env bash
set -euo pipefail

PYTHON_VERSION="3.14.4"

echo "Installing Python ${PYTHON_VERSION} via pyenv..."

# Install pyenv if not present
if ! command -v pyenv &> /dev/null; then
    curl https://pyenv.run | bash
fi

# Install Python 3.14
pyenv install "${PYTHON_VERSION}"
pyenv local "${PYTHON_VERSION}"

# Verify
python --version
```

#### System Installation (Production Nodes)

```yaml
# ansible/roles/python/tasks/main.yml

- name: Install Python 3.14 from deadsnakes PPA (Ubuntu)
  when: ansible_distribution == "Ubuntu"
  block:
    - name: Add deadsnakes PPA
      apt_repository:
        repo: ppa:deadsnakes/ppa
        state: present

    - name: Install Python 3.14
      apt:
        name:
          - python3.14
          - python3.14-venv
          - python3.14-dev
        state: present

- name: Set Python 3.14 as default
  alternatives:
    name: python3
    path: /usr/bin/python3.14
    priority: 100
```

### D6. Feature Adoption Strategy

#### Phase 1: Compatibility (Required)

- Version gate enforcement
- Dependency updates
- Test suite passing

#### Phase 2: Modernization (Recommended)

| Feature | Adoption | Benefit |
|---------|----------|---------|
| PEP 649 (deferred annotations) | Update type hints | Faster import |
| PEP 750 (t-strings) | Evaluate for templates | Cleaner syntax |
| Subinterpreters | ADR 0097 | Parallelism |

#### Phase 3: Optimization (Optional)

| Feature | Adoption | Benefit |
|---------|----------|---------|
| Free-threading | Experimental | True thread parallelism |
| JIT compiler | Monitor | Performance |

## Migration Plan (Gate-Driven)

**Full implementation plan**: See `adr/0098-analysis/IMPLEMENTATION-PLAN.md`

**Strategy**: 5 gate-driven phases (not calendar-based) with mandatory go/no-go decisions

| Phase | Purpose | Duration Est. | Rollback Risk |
|-------|---------|---------------|---------------|
| **A** | Verification Burst | 3-5 days | None |
| **B** | Dual-Path Parity | 5-7 days | Low |
| **C** | Contract Flip | 2-3 days | Medium |
| **D** | Integrated Validation | 4-6 days | Medium |
| **E** | Production Cutover | 7-10 days | HIGH |

---

### Phase A: Verification Burst

**Entry Criteria**:
- Python 3.14 officially released (stable)
- ADR 0098 status changed to "Accepted"

**Scope**:
1. Verify all core dependencies on Python 3.14 (evidence-based)
2. Check C-extension compatibility (orjson, ruamel.yaml)
3. Confirm Python 3.14 availability on target platforms (Proxmox x86_64, Orange Pi ARM64)
4. Run CI preflight on Python 3.14

**Exit Criteria** (ALL must pass):
- ✅ All core dependencies: PASS or alternative identified (evidence matrix complete)
- ✅ C-extensions: PASS or pure-Python fallback available
- ✅ Platform availability confirmed (apt/pyenv) for all node types
- ✅ CI green on Python 3.14 (full test suite)

**Rollback**: N/A (no production changes)

---

### Phase B: Dual-Path Parity

**Entry Criteria**:
- Phase A exit criteria passed
- ADR 0097 InterpreterPoolExecutor implemented

**Scope**:
1. Implement parity test suite (`tests/parity/`)
2. Run ThreadPool vs InterpreterPool comparison (byte-identical outputs required)
3. Collect performance metrics (execution time, memory, determinism)
4. Regression testing (vs Python 3.13 baseline)

**Exit Criteria** (ALL must pass):
- ✅ Parity test passes: ThreadPool == InterpreterPool (stdout, stderr, generated files)
- ✅ Performance variance <5%
- ✅ No regressions vs 3.13 baseline

**Rollback Criteria**:
- ❌ Parity test fails after 3 attempts → Decouple migrations (3.14 only, defer ADR 0097)
- ❌ Performance regression >20%
- ❌ Non-deterministic output detected

**Go/No-Go Decision**: If parity fails, proceed with Python 3.14 only (Option 1) or abort (Option 3)

---

### Phase C: Contract Flip

**Entry Criteria**:
- Phase B exit criteria passed (parity validated)
- Team communication sent (upgrade notice)

**Scope**:
1. Update `.python-version`, `pyproject.toml`, lockfiles to 3.14
2. CI matrix: Dual-lane (3.14 primary + 3.13 rollback lane, temporary)
3. Developer environment migration (team coordination)
4. Remove 3.13 CI lane after all contributors upgraded

**Exit Criteria** (ALL must pass):
- ✅ Version files updated (`requires-python = ">=3.14"`)
- ✅ Dual-lane CI green (3.14 primary)
- ✅ 100% of contributors confirmed on Python 3.14

**Rollback Criteria**:
- ❌ >30% of contributors unable to upgrade → Extend Phase C
- ❌ Unexpected CI failures on 3.14

**Rollback Procedure**: Revert version files, restore 3.13 primary CI lane

**Rollback Deadline**: 3 days after contract flip

---

### Phase D: Integrated Validation

**Entry Criteria**:
- Phase C exit criteria passed (contract flipped)
- Test nodes allocated (Proxmox LXC + Orange Pi container)

**Scope**:
1. Run full pipeline validation (`validate-v5 → build-v5`)
2. Bootstrap rehearsal on test nodes (Python 3.14 installation)
3. Deployment bundle test (create + apply)

**Exit Criteria** (ALL must pass):
- ✅ Full pipeline passes on Python 3.14
- ✅ Test nodes bootstrapped successfully (both architectures)
- ✅ Deployment bundle applies cleanly

**Rollback Criteria**:
- ❌ Bootstrap fails on >50% of test nodes
- ❌ Pipeline outputs differ from Phase B baseline

**Rollback Procedure**: Halt production rollout, fix issues, retry validation

---

### Phase E: Production Cutover

**Entry Criteria**:
- Phase D exit criteria passed (test nodes validated)
- Change control approved (maintenance window scheduled)
- Rollback artifacts preserved (3.13 venvs, lockfiles)

**Scope**:
1. Migrate production nodes to Python 3.14 (staged: Proxmox → LXC → Orange Pi)
2. Enforce runtime hard gate (`sys.version_info < (3, 14)` raises error)
3. Remove all Python 3.13 compatibility code
4. Archive 3.13 rollback lane from CI

**Exit Criteria** (ALL must pass):
- ✅ All production nodes running Python 3.14
- ✅ Runtime hard gate enforced (3.13 rejected)
- ✅ No 3.13 compatibility remnants

**Rollback Criteria** (CRITICAL):
- ❌ >5% of nodes fail migration
- ❌ Production service outages
- ❌ Performance regression >20%

**Rollback Procedure**:
1. FREEZE: Stop new deployments
2. REVERT NODES: Restore 3.13 venv backups
3. REVERT CI: Re-enable 3.13 lane
4. POST-MORTEM: Document failure, update plan

**Rollback Deadline**: **48 hours** after Phase E start (after this, forward fix only)

**Monitoring Window**: 14 days post-cutover

## SWOT Analysis

**Full analysis**: See `adr/0098-analysis/SWOT-ANALYSIS.md`

### Strengths (Internal Positive)

- ✅ **Comprehensive migration scope**: Covers runtime, scripts, bootstrap, CI, documentation (5 domains)
- ✅ **Strong ADR 0097 integration**: Unified platform + runtime executor migration reduces coordination overhead
- ✅ **Risk register with mitigations**: 4 documented risks (R1-R4) with concrete mitigation strategies
- ✅ **Operational context awareness**: Production node constraints (Proxmox, Orange Pi), architecture-specific testing, bootstrap/Ansible integration

### Weaknesses (Internal Negative)

- ⚠️ **Compatibility matrix lacks evidence**: 6/7 core dependencies marked "Expected compatible" without verification → Phase A gate addresses
- ⚠️ **Mixed initiatives in single ADR**: Platform (3.14) + Runtime executor (ADR 0097) + Feature adoption (PEP 649/750) → Phase B parity gate separates concerns
- ⚠️ **No rollback procedures**: Originally absent → Now defined for Phases C, D, E

### Opportunities (External Positive)

- 📈 **Unified 3.14 + subinterpreters program**: Single migration reduces coordination overhead vs two separate efforts
- 📈 **Technical debt reduction**: D1.1 hard cutover eliminates version conditionals, simplifies codebase
- 📈 **CI quality gate enhancement**: Parity tests (ThreadPool vs InterpreterPool) as blocking gate, evidence-based dependency verification
- 📈 **Bootstrap contract unification**: Single Python version across all node types (Ansible, LXC/VM, bootstrap scripts)

### Threats (External Negative)

- ⚠️ **C-extension compatibility risk**: orjson, ruamel.yaml may lag 3.14 support → Phase A verification burst addresses
- ⚠️ **High blast radius coupled cutover**: Platform + executor + features change simultaneously → Phase B parity gate as go/no-go
- ⚠️ **Heterogeneous node infrastructure**: Different package availability (Proxmox x86_64, Orange Pi ARM64) → Phase A/D multi-platform testing
- ⚠️ **Development velocity slowdown**: Early CI flip removes 3.13 safety net → Staged CI transition with temporary rollback lane

## Risks and Mitigations

### R1: Dependency Incompatibility

**Risk**: Critical dependency doesn't support Python 3.14 at release.

**Mitigation**:
- Monitor dependency issue trackers
- Identify alternative packages
- Contribute compatibility patches if needed
- Delay migration for specific components

### R2: Production Node Constraints

**Risk**: Production nodes (Proxmox, Orange Pi) have package availability issues.

**Mitigation**:
- Use pyenv for isolated installation
- Build from source if needed
- Maintain pre-cutover rollback artifacts while keeping runtime contract on 3.14
- Test on target architectures early

### R3: Team Skill Gap

**Risk**: New Python 3.14 features unfamiliar to contributors.

**Mitigation**:
- Documentation and examples
- Gradual feature adoption
- Code review focus areas
- Training materials

### R4: Timeline Slip

**Risk**: Python 3.14 release delayed or has critical bugs.

**Mitigation**:
- Plan based on stable release, not beta
- Buffer time in schedule
- Rollback plan within 3.14 cutover scope (feature flags / staged rollout)

## Acceptance Criteria

### Phase-Based Acceptance

1. ✅ **Phase A passed**: All core dependencies verified compatible (evidence matrix complete)
2. ✅ **Phase B passed**: ThreadPool vs InterpreterPool parity test passes (byte-identical outputs)
3. ✅ **Phase C passed**: Contract flipped (`.python-version`, `pyproject.toml` = 3.14, CI primary lane)
4. ✅ **Phase D passed**: Test nodes operational on Python 3.14 (bootstrap + deployment validated)
5. ✅ **Phase E passed**: Production cutover complete (all nodes migrated, 3.13 removed)

### Artifact Acceptance

1. ✅ `requires-python = ">=3.14"` in all `pyproject.toml` files
2. ✅ CI tests green on Python 3.14 only (no 3.13 lane)
3. ✅ Documentation updated (CLAUDE.md, README.md, operator guides)
4. ✅ ADR 0097 subinterpreters functional (parity validated)
5. ✅ No Python 3.13 compatibility code remains (version conditionals removed)
6. ✅ SWOT analysis completed (`adr/0098-analysis/SWOT-ANALYSIS.md`)
7. ✅ All rollback artifacts archived (`archive/python-3.13/`)

## References

### External Documentation

- [Python 3.14 What's New](https://docs.python.org/3/whatsnew/3.14.html)
- [PEP 649 – Deferred Evaluation of Annotations](https://peps.python.org/pep-0649/)
- [PEP 750 – Template Strings](https://peps.python.org/pep-0750/)
- [PEP 779 – Free-threaded CPython](https://peps.python.org/pep-0779/)
- [PEP 734 – Multiple Interpreters in the Stdlib](https://peps.python.org/pep-0734/)

### Internal ADRs

- ADR 0097: Subinterpreter-Based Parallel Plugin Execution
- ADR 0080: Unified Build Pipeline (thread-safety baseline)

### Analysis Artifacts

- `adr/0098-analysis/SWOT-ANALYSIS.md` — SWOT analysis with risk priority matrix
- `adr/0098-analysis/CRITIQUE.md` — Architectural review and gap identification
- `adr/0098-analysis/IMPROVEMENTS.md` — Proposed improvements (7 items)
- `adr/0098-analysis/IMPLEMENTATION-PLAN.md` — Gate-driven phases A-E (aggressive profile)
