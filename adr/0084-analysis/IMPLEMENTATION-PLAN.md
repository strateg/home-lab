# ADR 0084: Implementation Plan

## Overview

ADR 0084 defines the execution plane model. Implementation is minimal — a simple environment check integrated into ADR 0083 deploy tooling.

---

## Phase 1: Environment Check Implementation

**Goal:** Create `check_deploy_environment()` function and integrate into deploy tooling.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 1.1 | Create environment module | `scripts/orchestration/deploy/environment.py` | `check_deploy_environment()` returns `linux`/`wsl` or exits |
| 1.2 | Add unit tests | `tests/orchestration/test_environment.py` | T-E01..T-E05 pass |
| 1.3 | Integrate into `init-node.py` | Call at startup | Windows execution fails with clear message |

### Implementation

```python
# scripts/orchestration/deploy/environment.py
"""
ADR 0084: Deploy plane environment verification.
"""

import sys
import platform


def check_deploy_environment() -> str:
    """
    Verify execution environment is Linux-backed.

    Returns:
        "linux", "wsl", or "macos"

    Raises:
        SystemExit on Windows (unsupported)
    """
    system = platform.system()

    if system == "Windows":
        _exit_with_wsl_instructions()

    if system == "Linux":
        release = platform.uname().release.lower()
        if "microsoft" in release:
            return "wsl"
        return "linux"

    if system == "Darwin":
        print("⚠ macOS detected. Some mechanisms (netinstall) may not work.")
        return "macos"

    print(f"⚠ Unknown platform: {system}. Proceeding with caution.")
    return system.lower()


def _exit_with_wsl_instructions():
    print("""
ERROR: Deploy plane requires Linux execution environment.

You are running on Windows native. Please use WSL:

    # From PowerShell or Windows Terminal
    wsl
    cd /mnt/c/path/to/home-lab
    python scripts/orchestration/deploy/init-node.py --node <node-id>

To install WSL:
    wsl --install -d Ubuntu

See: docs/guides/OPERATOR-ENVIRONMENT-SETUP.md
See: ADR 0084 for execution plane model
""")
    sys.exit(1)
```

### Gate

- [ ] `check_deploy_environment()` implemented
- [ ] Unit tests pass (T-E01..T-E05)
- [ ] Windows execution shows clear WSL instructions

---

## Phase 2: Documentation

**Goal:** Document the plane separation for operators.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 2.1 | Create environment setup guide | `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md` | WSL installation, tool setup |
| 2.2 | Update CLAUDE.md | Add plane model section | Dev vs Deploy plane documented |
| 2.3 | Update deploy runbooks | Mark as Linux-required | Clear backend requirements |

### OPERATOR-ENVIRONMENT-SETUP.md Outline

```markdown
# Operator Environment Setup

## Overview
- Dev plane: Cross-platform (Windows, Linux, macOS)
- Deploy plane: Linux required (WSL supported)

## Dev Plane Setup (All Platforms)
- Python 3.10+
- Go-Task
- Git

## Deploy Plane Setup (Linux/WSL)

### WSL Installation (Windows)
wsl --install -d Ubuntu

### Required Tools
- Ansible 2.14+
- Terraform/OpenTofu
- SOPS + age
- netinstall-cli (MikroTik)

### Tool Installation
apt install ansible sops age
# ... detailed instructions

## Verification
python scripts/orchestration/deploy/environment.py
```

### Gate

- [ ] OPERATOR-ENVIRONMENT-SETUP.md created
- [ ] CLAUDE.md updated with plane model
- [ ] Runbooks mark Linux requirement

---

## Phase 3: ADR 0083 Integration

**Goal:** ADR 0083 Phase 5 calls `check_deploy_environment()`.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 3.1 | Add Phase 0 to ADR 0083 plan | Updated IMPLEMENTATION-PLAN.md | Environment check as prerequisite |
| 3.2 | Update init-node.py | Import and call check | Fails on Windows |
| 3.3 | Add cross-reference | ADR 0083 references ADR 0084 | D-link established |

### Gate

- [ ] ADR 0083 IMPLEMENTATION-PLAN.md includes Phase 0
- [ ] init-node.py calls check_deploy_environment()
- [ ] ADR 0083 references ADR 0084 for execution model

---

## Test Matrix

| Test ID | Description | Category | Mock/HW |
|---------|-------------|----------|---------|
| T-E01 | Returns "linux" on native Linux | Unit | Mock |
| T-E02 | Returns "wsl" when uname contains "microsoft" | Unit | Mock |
| T-E03 | Returns "macos" on Darwin | Unit | Mock |
| T-E04 | Exits with code 1 on Windows | Unit | Mock |
| T-E05 | Exit message contains WSL instructions | Unit | Mock |

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Environment Check | 1 day | None |
| Phase 2: Documentation | 1 day | Phase 1 |
| Phase 3: ADR 0083 Integration | 0.5 day | Phase 1 |

**Total:** ~2.5 days

---

## What We Are NOT Implementing

| Feature | Reason | When to Revisit |
|---------|--------|-----------------|
| DeployRunner abstraction | YAGNI | Multi-operator or CI/CD needs |
| Docker backend | Not needed yet | CI pipeline integration |
| remote-linux backend | Not needed yet | Dedicated control VM scenario |
| Backend selector CLI | No multiple backends | When backends exist |

These features are deferred to a future ADR if and when concrete need arises.
