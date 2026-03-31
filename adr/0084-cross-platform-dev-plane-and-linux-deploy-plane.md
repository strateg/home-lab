# ADR 0084: Cross-Platform Dev Plane and Linux Deploy Plane

**Date:** 2026-03-31
**Status:** Proposed
**Related:** ADR 0056 (Native Execution Workspace), ADR 0072 (Unified Secrets Management), ADR 0077 (Go-Task Developer Orchestration), ADR 0080 (Unified Build Pipeline), ADR 0083 (Unified Node Initialization Contract)

---

## Context

The repository already separates topology authoring and artifact generation from infrastructure execution:

- `scripts/orchestration/lane.py` runs Python-based validation and compilation steps.
- `topology-tools/compile-topology.py` generates Terraform, Ansible, bootstrap, and documentation artifacts under `generated/<project>/`.
- Deploy-time commands live outside the compiler boundary and consume generated artifacts plus runtime secrets.

That separation is conceptually correct, but the execution model is still ambiguous on workstation platforms.

Current reality:

1. Authoring and compile-time workflows are largely cross-platform because they are implemented in Python and `task`.
2. Terraform/OpenTofu work well on Windows, Linux, and macOS.
3. Ansible remains Linux-first as a control-node technology.
4. The repository already contains WSL-specific execution glue for Ansible checks in `topology-tools/utils/service_chain_evidence.py`.
5. Existing evidence records that native Windows `ansible-playbook` execution is not usable in the current environment.

Without an explicit execution-plane decision, the repo risks:

- leaking WSL-specific conditionals into orchestration code,
- splitting Terraform and Ansible across different control environments,
- creating inconsistent handling for SSH, `sops`/`age`, provider plugins, and secret injection,
- and overstating deploy-time cross-platform support when the final executor is still Linux-bound.

ADR 0083 defines a unified node initialization contract and deploy-domain lifecycle. That ADR needs an explicit execution-plane decision so that initialization, Terraform/OpenTofu handover, and Ansible configuration all run in a coherent operator model.

---

## Decision

### D1. Separate Development Plane from Deploy Plane

The repository adopts two explicit planes:

- **Dev plane**: authoring, validation, compilation, generation, unit/integration tests that do not require live infrastructure.
- **Deploy plane**: runtime execution of infrastructure changes against real or target-like environments.

These planes have different requirements and may run on different operating environments.

### D2. Dev Plane Must Remain Cross-Platform

The dev plane MUST remain usable from Windows, Linux, and macOS, subject to normal tool availability.

The dev plane includes:

- editing topology, templates, plugins, and docs,
- `python scripts/orchestration/lane.py validate-v5`,
- `python topology-tools/compile-topology.py`,
- `task`-based validation and test entrypoints that do not require Linux-only runtime tooling,
- artifact generation under `generated/<project>/`.

Cross-platform here means repository contributors MUST NOT need a Linux deploy executor just to perform normal authoring, compile, and non-live validation tasks.

### D3. Deploy Plane Is Linux-Backed

The canonical deploy plane is Linux-backed.

All commands that perform deploy-time execution SHOULD run from a Linux environment, including:

- node initialization execution after artifact generation,
- Terraform/OpenTofu `init`, `plan`, and `apply` for real deploy lanes,
- Ansible `syntax-check`, `--check`, and apply,
- runtime secret decryption/injection,
- SSH-based orchestration against managed nodes.

This decision applies even though Terraform/OpenTofu can run natively on Windows. Canonical deploy execution is unified under Linux so that Terraform/OpenTofu and Ansible share one runtime boundary.

### D4. Supported Deploy Backends

The deploy plane uses a `DeployRunner` abstraction to support multiple execution backends:

| Backend | Class | Status | Use Case |
|---------|-------|--------|----------|
| `native` | `NativeRunner` | ✅ Implemented | Linux/macOS workstation |
| `wsl` | `WSLRunner` | ✅ Implemented | Windows developer workflow |
| `docker` | `DockerRunner` | 🔜 Planned | Reproducible CI execution |
| `remote` | `RemoteLinuxRunner` | 🔜 Planned | Dedicated control node via SSH |

**Auto-detection:**
- On Windows → `WSLRunner` (default)
- On Linux/macOS → `NativeRunner` (default)
- Explicit selection via `--runner` flag

### D5. Deploy Runner Abstraction

Deploy tooling uses `DeployRunner` abstraction for consistent command execution across backends:

```python
# scripts/orchestration/deploy/runner.py

from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class DeployRunner(ABC):
    """Abstract deploy runner for Linux-backed execution."""

    @abstractmethod
    def run(self, cmd: list[str], cwd: Path | None = None,
            env: dict[str, str] | None = None) -> RunResult:
        """Execute command in deploy environment."""
        pass

    @abstractmethod
    def translate_path(self, path: Path) -> str:
        """Translate host path to runner path."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if runner is available."""
        pass

    def check_tool(self, tool: str) -> bool:
        """Check if tool exists in runner environment."""
        result = self.run(["which", tool])
        return result.success


def get_runner(preference: str | None = None) -> DeployRunner:
    """Get deploy runner based on preference or auto-detect."""
    if preference:
        return _get_explicit_runner(preference)
    return _auto_detect_runner()
```

**Rationale:** The abstraction enables future Docker and remote-linux backends without rewriting deploy tooling. Current implementations (WSL, native) provide immediate value while establishing the interface contract.

### D6. ADR 0083 Executes Within This Plane Model

ADR 0083 node initialization and post-initialization handover are governed by this execution-plane model:

- initialization artifacts may be generated from any supported dev plane,
- initialization execution belongs to the Linux-backed deploy plane,
- Terraform/OpenTofu handover and Ansible configuration remain in the same Linux-backed deploy plane.

ADR 0083 therefore depends on this ADR for execution semantics, while retaining its own scope over initialization contracts and deploy-domain lifecycle phases.

---

## Consequences

### Benefits

- The repository keeps a genuinely cross-platform authoring experience.
- Deploy execution stops pretending to be fully cross-platform when Ansible is Linux-first.
- Terraform/OpenTofu and Ansible share one canonical runtime for secrets, SSH, networking, and caches.
- `DeployRunner` abstraction enables future Docker and remote-linux backends.
- Clear error messages guide Windows operators to WSL.
- Existing `service_chain_evidence.py` WSL logic is formalized into reusable runner.

### Trade-Offs

- Windows-native Terraform/OpenTofu deploy flows are no longer the canonical operator path.
- Local operators on Windows must use WSL for deploy operations.
- Documentation must clearly distinguish dev-plane from deploy-plane workflows.
- Runner abstraction adds ~150 lines of code (justified by planned Docker/remote backends).

### Migration Impact

1. Existing Python compile/generate flows remain unchanged (dev plane).
2. Deploy tooling (`init-node.py`, Terraform, Ansible) runs via `DeployRunner`.
3. `service_chain_evidence.py` refactored to use `DeployRunner` abstraction.
4. ADR 0083 Phase 5 adapters receive runner via dependency injection.

### Implementation Phases

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0a | `DeployRunner` ABC + `NativeRunner` + `WSLRunner` | 🔜 Next |
| 0b | `DockerRunner` + Dockerfile | 📅 When CI needed |
| 0c | `RemoteLinuxRunner` + SSH setup | 📅 When control VM needed |

---

## References

- `scripts/orchestration/deploy/runner.py` — DeployRunner abstraction (NEW)
- `scripts/orchestration/lane.py` — Dev plane orchestration
- `topology-tools/utils/service_chain_evidence.py` — Legacy WSL logic (to be refactored)
- `docs/runbooks/evidence/2026-03-28-wave-d-service-chain-evidence.md`
- `adr/0056-native-execution-workspace.md`
- `adr/0077-go-task-developer-orchestration.md`
- `adr/0083-unified-node-initialization-contract.md`
