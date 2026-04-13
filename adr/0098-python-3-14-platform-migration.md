# ADR 0098: Python 3.14 Platform Migration

- Status: Draft (pending SWOT analysis)
- Date: 2026-04-13
- Depends on: ADR 0097
- Target: Python 3.14+ as minimum supported version

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

PYTHON_VERSION="3.14.0"

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

## Migration Plan

### Wave 1: Preparation (Before Python 3.14 Release)

**Timeline**: August-September 2025

1. Audit all dependencies for 3.14 compatibility
2. Update CI to test against 3.14 beta/RC
3. Remove remaining 3.13-era assumptions found by 3.14 test runs
4. Prepare version gate code
5. Draft documentation updates

**Gate**: All tests pass on Python 3.14 RC

### Wave 2: Development Environment (Python 3.14 Release + 1 month)

**Timeline**: November 2025

1. Update `.python-version` to 3.14
2. Update `pyproject.toml` requires-python
3. Update development documentation
4. Update team development environments
5. CI matrix: 3.14 only (no secondary 3.13 lane)

**Gate**: All developers on Python 3.14

### Wave 3: Runtime Migration (Wave 2 + 1 month)

**Timeline**: December 2025

1. Enable version gate in `compile-topology.py`
2. Integrate ADR 0097 subinterpreters
3. Update orchestration scripts
4. Test full pipeline on 3.14

**Gate**: Production pipeline runs on 3.14

### Wave 4: Node Bootstrap (Wave 3 + 1 month)

**Timeline**: January 2026

1. Update Ansible Python installation roles
2. Update LXC/VM base images
3. Update bootstrap scripts
4. Deploy to test nodes

**Gate**: Test nodes running Python 3.14

### Wave 5: Production Cutover (Wave 4 + 1 month)

**Timeline**: February 2026

1. Deploy to production nodes
2. Enforce Python 3.14 hard gate at runtime entrypoints
3. Set `requires-python = ">=3.14"` across all package/tooling metadata
4. Remove all Python 3.13 compatibility paths from runtime, CI, and docs

**Gate**: All nodes on Python 3.14

### Wave 6: Feature Adoption (Wave 5 + ongoing)

**Timeline**: March 2026+

1. Adopt PEP 649 annotations
2. Evaluate t-strings for templates
3. Monitor free-threading stability
4. Performance benchmarking

**Gate**: Continuous improvement

## SWOT Analysis Placeholders

### Strengths (Internal Positive)

- [ ] _To be analyzed_
- [ ] _To be analyzed_
- [ ] _To be analyzed_

### Weaknesses (Internal Negative)

- [ ] _To be analyzed_
- [ ] _To be analyzed_
- [ ] _To be analyzed_

### Opportunities (External Positive)

- [ ] _To be analyzed_
- [ ] _To be analyzed_
- [ ] _To be analyzed_

### Threats (External Negative)

- [ ] _To be analyzed_
- [ ] _To be analyzed_
- [ ] _To be analyzed_

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

1. All components run on Python 3.14+
2. `requires-python = ">=3.14"` in pyproject.toml
3. CI tests pass on Python 3.14
4. All nodes (dev, test, prod) running Python 3.14
5. Documentation updated with 3.14 requirements
6. ADR 0097 subinterpreters functional
7. No Python 3.13 compatibility contracts remain in runtime, CI, or developer tooling
8. SWOT analysis completed and risks addressed

## References

- [Python 3.14 What's New](https://docs.python.org/3/whatsnew/3.14.html)
- [PEP 649 – Deferred Evaluation of Annotations](https://peps.python.org/pep-0649/)
- [PEP 750 – Template Strings](https://peps.python.org/pep-0750/)
- [PEP 779 – Free-threaded CPython](https://peps.python.org/pep-0779/)
- ADR 0097: Subinterpreter-Based Parallel Plugin Execution
