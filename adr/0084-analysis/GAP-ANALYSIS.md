# ADR 0084: Gap Analysis

## Goal

Define the gap between the current mixed execution model and the target model:

- Cross-platform dev plane
- Linux-backed deploy plane
- `DeployRunner` abstraction for multiple backends

---

## Current State

| Aspect | Status | Issue |
|--------|--------|-------|
| Dev workflows | ✅ Cross-platform | Python-based validation and compilation |
| Terraform/OpenTofu | ⚠️ Mixed | Can run on Windows, but should share runtime with Ansible |
| Ansible | ❌ Linux-only | Requires WSL on Windows |
| WSL glue | ⚠️ Hard-coded | `service_chain_evidence.py` has WSL-specific logic |
| Runner abstraction | ❌ Missing | No unified interface for deploy execution |

---

## Target State

| Aspect | Target | Implementation |
|--------|--------|----------------|
| Dev plane | Cross-platform | No changes needed |
| Deploy plane | Linux-backed | `DeployRunner` abstraction |
| Multiple backends | WSL, Docker, Remote | Phased implementation |
| Terraform + Ansible | Unified runtime | Both use `runner.run()` |

---

## Gap Items

### G1: No runner abstraction ✅ RESOLVED

**Current:** Hard-coded WSL logic in `service_chain_evidence.py`.
**Target:** `DeployRunner` ABC with `NativeRunner`, `WSLRunner`.
**Status:** `runner.py` created with full implementation.

### G2: service_chain_evidence.py needs refactoring

**Current:** Contains `_to_wsl_path()`, `_ansible_wsl_command()`, `_resolve_deploy_runner()`.
**Target:** Use `get_runner()` and `runner.run()`.
**Action:** Refactor to use deploy runner package.

### G3: No operator setup guide

**Current:** Scattered tool installation notes.
**Target:** Unified `OPERATOR-ENVIRONMENT-SETUP.md`.
**Action:** Create guide with WSL setup, tool installation, verification.

### G4: ADR 0083 Phase 5 integration

**Current:** Adapters don't have runner injection.
**Target:** `BootstrapAdapter.__init__(runner: DeployRunner)`.
**Action:** Design adapter interface with runner dependency.

### G5: Docker backend not implemented

**Current:** `DockerRunner` stub with `NotImplementedError`.
**Target:** Full implementation when CI needed.
**Action:** Defer to Phase 0b.

### G6: Remote Linux backend not implemented

**Current:** `RemoteLinuxRunner` stub with `NotImplementedError`.
**Target:** Full implementation when control VM needed.
**Action:** Defer to Phase 0c.

---

## Implementation Progress

| Component | Status | Notes |
|-----------|--------|-------|
| `DeployRunner` ABC | ✅ Done | Abstract methods defined |
| `NativeRunner` | ✅ Done | Linux/macOS execution |
| `WSLRunner` | ✅ Done | Windows via WSL |
| `DockerRunner` | 🔜 Stub | Phase 0b |
| `RemoteLinuxRunner` | 🔜 Stub | Phase 0c |
| `get_runner()` factory | ✅ Done | Auto-detection + explicit |
| `RunResult` dataclass | ✅ Done | exit_code, stdout, stderr |
| Tests | ❌ Pending | T-R01..T-R12 |
| Refactor legacy | ❌ Pending | service_chain_evidence.py |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| WSL networking issues | Medium | High | Document WSL2 network modes |
| Path translation bugs | Low | Medium | Comprehensive unit tests |
| Docker network mode | Low | Medium | Test `--network=host` for netinstall |
| Remote file sync | Medium | Medium | Support both rsync and git strategies |

---

## Acceptance Signals

ADR 0084 is successfully adopted when:

1. ✅ Runner abstraction implemented (`runner.py`)
2. ✅ WSL + Native runners work
3. [ ] `service_chain_evidence.py` refactored
4. [ ] Unit tests pass (T-R01..T-R12)
5. [ ] `OPERATOR-ENVIRONMENT-SETUP.md` guides Windows users
6. [ ] ADR 0083 Phase 5 uses runner injection
