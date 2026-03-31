# ADR 0084: Implementation Plan

## Overview

ADR 0084 defines the execution-plane model:

- cross-platform dev plane,
- Linux-backed deploy plane,
- workspace-aware `DeployRunner`,
- bundle/workspace execution aligned with ADR 0085.

This plan focuses on evolving the current runner implementation and surrounding tooling to match that model.

---

## Phase 0a: Runner Contract Alignment (Current)

**Goal:** Align `DeployRunner`, `NativeRunner`, and `WSLRunner` with the workspace-aware execution model.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 0a.1 | Update runner contract | `scripts/orchestration/deploy/runner.py` | Workspace-aware interface defined |
| 0a.2 | Align `NativeRunner` | `runner.py` update | Stages bundle and executes in workspace |
| 0a.3 | Align `WSLRunner` | `runner.py` update | Stages bundle and executes in WSL workspace |
| 0a.4 | Update package exports | `scripts/orchestration/deploy/__init__.py` | Public API matches new contract |
| 0a.5 | Add/refresh tests | `tests/orchestration/test_runner.py` | Runner contract tests pass |
| 0a.6 | Refactor `service_chain_evidence.py` | Uses runner staging | WSL glue removed from evidence tool |

### Target Contract

```python
class DeployRunner(ABC):
    @abstractmethod
    def stage_bundle(self, bundle_path: str) -> str: ...

    @abstractmethod
    def run(self, cmd, workspace_ref, env=None, timeout=None) -> RunResult: ...

    @abstractmethod
    def capabilities(self) -> dict[str, bool]: ...

    @abstractmethod
    def cleanup_workspace(self, workspace_ref: str) -> None: ...
```

### Test Matrix

| Test ID | Description | Category |
|---------|-------------|----------|
| T-R01 | `NativeRunner` stages bundle into local workspace | Unit |
| T-R02 | `NativeRunner.run()` executes in staged workspace | Unit |
| T-R03 | `NativeRunner.capabilities()` returns expected flags | Unit |
| T-R04 | `WSLRunner` stages bundle into translated WSL workspace | Unit |
| T-R05 | `WSLRunner` availability detection works | Unit |
| T-R06 | `get_runner()` auto-detects Linux native runner | Unit |
| T-R07 | `get_runner()` auto-detects WSL on Windows | Unit |
| T-R08 | `get_runner("native")` returns `NativeRunner` | Unit |
| T-R09 | `get_runner("wsl")` returns `WSLRunner` | Unit |
| T-R10 | Unknown runner raises `ValueError` | Unit |
| T-R11 | Required capability mismatch fails fast | Integration |
| T-R12 | `RunResult.success` behaves correctly | Unit |

### Gate

- [x] ADR 0084 wording aligned to bundle/workspace model
- [ ] `runner.py` exposes workspace-aware contract
- [ ] `NativeRunner` and `WSLRunner` aligned
- [ ] Unit tests pass
- [ ] `service_chain_evidence.py` refactored

---

## Phase 0b: Docker Runner (Planned)

**Goal:** Add `DockerRunner` for reproducible CI execution.

**Trigger:** CI/CD pipeline integration or reproducible deploy sandbox requirement.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 0b.1 | Create Docker toolchain image | `docker/Dockerfile.toolchain` | Python, Ansible, Terraform/OpenTofu, SOPS |
| 0b.2 | Implement bundle staging strategy | `runner.py` update | Bundle mounted or copied into container workspace |
| 0b.3 | Implement `DockerRunner` | `runner.py` update | Runner executes against staged workspace |
| 0b.4 | Add tests | `tests/orchestration/test_docker_runner.py` | Docker runner tests pass |
| 0b.5 | Integrate CI usage | workflow/docs | CI can run deploy-domain checks via Docker |

### Gate

- [ ] Docker image builds successfully
- [ ] Bundle staging works in container workspace
- [ ] `DockerRunner` passes tests
- [ ] CI/docs updated

---

## Phase 0c: Remote Linux Runner (Planned)

**Goal:** Add `RemoteLinuxRunner` for dedicated control-node execution.

**Trigger:** Dedicated control VM, multi-operator usage, or remote execution requirement.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 0c.1 | Define remote staging strategy | docs/design notes | rsync/scp/git approach agreed |
| 0c.2 | Implement `RemoteLinuxRunner` | `runner.py` update | Bundle staged remotely |
| 0c.3 | Define remote secret handling | docs | Remote deploy prerequisites documented |
| 0c.4 | Add tests | `tests/orchestration/test_remote_runner.py` | Remote runner tests pass |

### Gate

- [ ] Remote bundle staging works
- [ ] Remote execution runs from staged workspace
- [ ] Remote secret/tooling assumptions documented
- [ ] Tests pass

---

## Integration with ADR 0083

ADR 0083 deploy tooling should consume runner + workspace context rather than raw local paths.

Target direction:

```python
def main():
    runner = get_runner(args.runner)
    workspace_ref = runner.stage_bundle(bundle_path)
    adapter = get_adapter(mechanism, runner=runner, workspace_ref=workspace_ref)
    result = adapter.execute(node)
```

This keeps:
- bundle selection in the orchestrator,
- execution inside runner workspace,
- state/logs outside the immutable bundle.

---

## Refactoring `service_chain_evidence.py`

Current issues:
- hard-coded WSL path conversion,
- inline WSL command construction,
- subprocess execution that bypasses `DeployRunner`.

Target direction:

```python
from scripts.orchestration.deploy import get_runner

runner = get_runner()
workspace_ref = runner.stage_bundle(bundle_path)
result = runner.run(["ansible-playbook", "..."], workspace_ref=workspace_ref)
```

### Migration Steps

1. Import `get_runner` from deploy package
2. Introduce explicit bundle selection/staging
3. Replace inline WSL command assembly with `runner.run(...)`
4. Remove WSL-specific helper functions from the evidence tool
5. Update tests and evidence docs

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 0a: Contract alignment | 2 days | 🔄 In Progress |
| Phase 0b: Docker | 2 days | 📅 When CI needed |
| Phase 0c: Remote | 3 days | 📅 When control node needed |
