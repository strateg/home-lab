# ADR 0084: Implementation Plan

## Overview

ADR 0084 defines the execution plane model with a `DeployRunner` abstraction supporting multiple backends (WSL, native, Docker, remote-linux).

---

## Phase 0a: Runner Abstraction + WSL + Native (CURRENT)

**Goal:** Create `DeployRunner` ABC and implement `WSLRunner` + `NativeRunner`.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 0a.1 | Create runner module | `scripts/orchestration/deploy/runner.py` | ABC + 2 implementations |
| 0a.2 | Create package init | `scripts/orchestration/deploy/__init__.py` | Exports public API |
| 0a.3 | Add unit tests | `tests/orchestration/test_runner.py` | T-R01..T-R12 pass |
| 0a.4 | Refactor service_chain_evidence.py | Use `get_runner()` | WSL logic moved to runner |

### Implementation

```python
# scripts/orchestration/deploy/runner.py

class DeployRunner(ABC):
    @abstractmethod
    def run(self, cmd, cwd, env, timeout) -> RunResult: ...
    @abstractmethod
    def translate_path(self, path) -> str: ...
    @abstractmethod
    def is_available(self) -> bool: ...
    def check_tool(self, tool) -> bool: ...

class NativeRunner(DeployRunner): ...  # Linux/macOS
class WSLRunner(DeployRunner): ...      # Windows via WSL

def get_runner(preference=None) -> DeployRunner:
    # Auto-detect or explicit selection
```

### Test Matrix

| Test ID | Description | Category |
|---------|-------------|----------|
| T-R01 | `NativeRunner.is_available()` returns True on Linux | Unit |
| T-R02 | `NativeRunner.run()` executes command | Unit |
| T-R03 | `NativeRunner.translate_path()` returns resolved path | Unit |
| T-R04 | `WSLRunner.translate_path()` converts C:\\ to /mnt/c/ | Unit |
| T-R05 | `WSLRunner.is_available()` checks distro exists | Unit |
| T-R06 | `get_runner()` auto-detects on Linux | Unit |
| T-R07 | `get_runner()` auto-detects WSL on Windows | Unit |
| T-R08 | `get_runner("native")` returns NativeRunner | Unit |
| T-R09 | `get_runner("wsl")` returns WSLRunner | Unit |
| T-R10 | `get_runner("unknown")` raises ValueError | Unit |
| T-R11 | `runner.check_tool("ansible-playbook")` works | Integration |
| T-R12 | `RunResult.success` property correct | Unit |

### Gate

- [x] `runner.py` created with ABC + NativeRunner + WSLRunner
- [x] `__init__.py` exports public API
- [ ] Unit tests pass (T-R01..T-R12)
- [ ] `service_chain_evidence.py` refactored

---

## Phase 0b: Docker Runner (PLANNED)

**Goal:** Add `DockerRunner` for reproducible CI execution.

**Trigger:** CI/CD pipeline integration needed.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 0b.1 | Create Dockerfile | `docker/Dockerfile.toolchain` | Python, Ansible, Terraform, SOPS |
| 0b.2 | Implement DockerRunner | `runner.py` update | Volume mounts, network mode |
| 0b.3 | Add CI workflow | `.github/workflows/deploy.yml` | Uses DockerRunner |
| 0b.4 | Add tests | `tests/orchestration/test_docker_runner.py` | T-R13..T-R18 |

### Dockerfile Outline

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ansible \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform/OpenTofu
RUN curl -fsSL https://get.opentofu.org/install-opentofu.sh | sh

# Install SOPS + age
RUN curl -LO https://github.com/getsops/sops/releases/download/v3.8.1/sops-v3.8.1.linux.amd64 \
    && mv sops-v3.8.1.linux.amd64 /usr/local/bin/sops \
    && chmod +x /usr/local/bin/sops

WORKDIR /workspace
ENTRYPOINT ["python"]
```

### Gate

- [ ] Dockerfile builds successfully
- [ ] DockerRunner passes all tests
- [ ] CI workflow uses DockerRunner

---

## Phase 0c: Remote Linux Runner (PLANNED)

**Goal:** Add `RemoteLinuxRunner` for dedicated control node execution.

**Trigger:** Dedicated control VM or multi-operator scenario.

### Tasks

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 0c.1 | Implement RemoteLinuxRunner | `runner.py` update | SSH-based execution |
| 0c.2 | Define sync strategy | Documentation | rsync or git-based |
| 0c.3 | Secret handling on remote | `SECRETS-REMOTE.md` | SOPS key deployment |
| 0c.4 | Add tests | `tests/orchestration/test_remote_runner.py` | T-R19..T-R24 |

### Design Considerations

```python
class RemoteLinuxRunner(DeployRunner):
    def __init__(self, host: str, user: str = "deploy",
                 sync_method: str = "rsync"):
        self.host = host
        self.user = user
        self.sync_method = sync_method  # "rsync" | "git"

    def sync_workspace(self, local_path: Path) -> str:
        """Sync local workspace to remote."""
        if self.sync_method == "rsync":
            # rsync -avz local_path user@host:remote_path
            ...
        elif self.sync_method == "git":
            # git push to remote, git pull on remote
            ...

    def run(self, cmd, cwd, env, timeout) -> RunResult:
        # SSH execution
        ssh_cmd = ["ssh", f"{self.user}@{self.host}", "--", *cmd]
        ...
```

### Gate

- [ ] RemoteLinuxRunner passes all tests
- [ ] File sync works (rsync or git)
- [ ] Secrets accessible on remote

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 0a: WSL + Native | 2 days | 🔄 In Progress |
| Phase 0b: Docker | 2 days | 📅 When CI needed |
| Phase 0c: Remote | 3 days | 📅 When control VM needed |

---

## Integration with ADR 0083

ADR 0083 Phase 5 adapters receive runner via dependency injection:

```python
# scripts/orchestration/deploy/adapters/base.py

class BootstrapAdapter(ABC):
    def __init__(self, runner: DeployRunner):
        self.runner = runner

    def execute(self, node: Node) -> BootstrapResult:
        # Use self.runner.run() for all commands
        ...

# scripts/orchestration/deploy/init-node.py

def main():
    runner = get_runner(args.runner)
    adapter = get_adapter(mechanism, runner=runner)
    result = adapter.execute(node)
```

---

## Refactoring service_chain_evidence.py

Current WSL logic in `topology-tools/utils/service_chain_evidence.py`:

```python
# BEFORE (hard-coded WSL logic)
def _ansible_wsl_command(...):
    wsl_cmd = ["wsl", "bash", "-lc", ...]
    ...

def _to_wsl_path(path: Path) -> str:
    if len(resolved) >= 3 and resolved[1] == ":":
        return f"/mnt/{resolved[0].lower()}{resolved[2:]}"
    ...
```

After refactoring:

```python
# AFTER (uses DeployRunner)
from scripts.orchestration.deploy import get_runner

runner = get_runner()
result = runner.run(["ansible-playbook", playbook_path])
```

### Migration Steps

1. Import `get_runner` from deploy package
2. Replace `_to_wsl_path()` calls with `runner.translate_path()`
3. Replace `_ansible_wsl_command()` with `runner.run()`
4. Remove `_resolve_deploy_runner()` function
5. Remove `SUPPORTED_DEPLOY_RUNNERS` constant
6. Update tests
