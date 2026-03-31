# ADR 0084: Cross-Platform Dev Plane and Linux Deploy Plane

**Date:** 2026-03-31
**Status:** Proposed (Secondary; after ADR 0085)
**Related:** ADR 0056 (Native Execution Workspace), ADR 0072 (Unified Secrets Management), ADR 0077 (Go-Task Developer Orchestration), ADR 0080 (Unified Build Pipeline), ADR 0085 (Deploy Bundle and Runner Workspace Contract), ADR 0083 (Unified Node Initialization Contract)

---

## Context

The repository already separates topology authoring and artifact generation from infrastructure execution:

- `scripts/orchestration/lane.py` runs Python-based validation and compilation steps.
- `topology-tools/compile-topology.py` generates Terraform, Ansible, bootstrap, and documentation artifacts under `generated/<project>/`.
- Deploy-time commands live outside the compiler boundary and must execute from deploy-domain inputs rather than directly from source-derived artifact roots.

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
- coupling deploy execution to local workstation filesystem layout,
- and overstating deploy-time cross-platform support when the final executor is still Linux-bound.

ADR 0085 defines the foundational deploy-domain execution input and workspace contract. This ADR defines where and how that deploy-domain execution runs so that Terraform/OpenTofu, Ansible, and any future deploy-domain tooling follow one coherent operator model.

ADR 0083 is a possible downstream consumer of this model, but it is not required to adopt ADR 0084. The intended sequence is:
1. ADR 0085 first
2. ADR 0084 second
3. ADR 0083 later, only if unified node initialization is still worth implementing

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
- deploy bundle staging and workspace preparation,
- runtime secret decryption/injection,
- SSH-based orchestration against managed nodes.

This decision applies even though Terraform/OpenTofu can run natively on Windows. Canonical deploy execution is unified under Linux so that Terraform/OpenTofu and Ansible share one runtime boundary.

### D4. Supported Deploy Backends

The deploy plane uses a `DeployRunner` abstraction to support multiple execution backends:

| Backend | Class | Status | Use Case |
|---------|-------|--------|----------|
| `native` | `NativeRunner` | ✅ Implemented | Local Linux workstation |
| `wsl` | `WSLRunner` | ✅ Implemented | Windows developer workflow |
| `docker` | `DockerRunner` | 🔜 Planned | Reproducible CI execution |
| `remote` | `RemoteLinuxRunner` | 🔜 Planned | Dedicated control node via SSH |

**Auto-detection:**
- On Windows → `WSLRunner` (default)
- On Linux → `NativeRunner` (default)
- Explicit selection via `--runner` flag

### D5. Deploy Runner Abstraction

Deploy tooling uses `DeployRunner` abstraction for consistent workspace-aware execution across backends.

```python
# scripts/orchestration/deploy/runner.py

from abc import ABC, abstractmethod
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
    def stage_bundle(self, bundle_path: str) -> str:
        """Stage a deploy bundle and return a workspace reference."""
        pass

    @abstractmethod
    def run(self, cmd: list[str], workspace_ref: str,
            env: dict[str, str] | None = None) -> RunResult:
        """Execute command in the staged deploy workspace."""
        pass

    @abstractmethod
    def capabilities(self) -> dict[str, bool]:
        """Report backend capabilities required by deploy tooling."""
        pass

    @abstractmethod
    def cleanup_workspace(self, workspace_ref: str) -> None:
        """Clean up temporary backend workspace state when needed."""
        pass
```

**Rationale:** ADR 0085 introduces deploy bundle as the canonical execution input. A simple `run()+translate_path()` abstraction is not enough for `wsl`, `docker`, and `remote` backends. The runner contract therefore must stage bundles into backend workspaces, execute there, report capabilities, and clean up.

### D6. ADR 0083 Would Execute Within This Plane Model

If ADR 0083 is implemented later, its node initialization and post-initialization handover are governed by this execution-plane model:

- source-derived artifacts may be generated from any supported dev plane,
- assemble/build materializes a deploy bundle per ADR 0085,
- initialization execution stages that bundle into a Linux-backed runner workspace,
- Terraform/OpenTofu handover and Ansible configuration remain in the same Linux-backed deploy plane and consume the same bundle/workspace boundary.

ADR 0084 depends on ADR 0085 for canonical execution input and workspace contract. ADR 0083, if pursued later, depends on both ADR 0085 and ADR 0084.

---

## Consequences

### Benefits

- The repository keeps a genuinely cross-platform authoring experience.
- Deploy execution stops pretending to be fully cross-platform when Ansible is Linux-first.
- Terraform/OpenTofu and Ansible share one canonical runtime for secrets, SSH, networking, caches, and workspace staging.
- `DeployRunner` abstraction becomes compatible with `wsl`, `docker`, and `remote` backends.
- Clear error messages guide Windows operators to WSL.
- Existing `service_chain_evidence.py` WSL logic is formalized into reusable runner.

### Trade-Offs

- Windows-native Terraform/OpenTofu deploy flows are no longer the canonical operator path.
- Local operators on Windows must use WSL for deploy operations.
- Documentation must clearly distinguish dev-plane from deploy-plane workflows.
- Runner abstraction must manage bundle staging and workspace lifecycle, not just process execution.

### Migration Impact

1. Existing Python compile/generate flows remain unchanged (dev plane).
2. Deploy tooling (`init-node.py`, Terraform, Ansible) runs via `DeployRunner`.
3. Deploy tooling consumes explicit `bundle_id` inputs rather than executing directly from `generated/`.
4. `service_chain_evidence.py` should be refactored to use deploy bundle staging instead of inline WSL path glue.
5. ADR 0083 adapters would receive runner and workspace context via dependency injection if ADR 0083 is implemented later.

### Implementation Phases

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0a | Workspace-aware `DeployRunner` contract + `NativeRunner` + `WSLRunner` alignment | 🔜 Next |
| 0b | `DockerRunner` + bundle mounting/staging strategy | 📅 When CI needed |
| 0c | `RemoteLinuxRunner` + remote bundle staging strategy | 📅 When control VM needed |

---

## References

- `scripts/orchestration/deploy/runner.py` — DeployRunner abstraction (NEW)
- `scripts/orchestration/lane.py` — Dev plane orchestration
- `topology-tools/utils/service_chain_evidence.py` — Legacy WSL logic (to be refactored)
- `docs/runbooks/evidence/2026-03-28-wave-d-service-chain-evidence.md`
- `adr/0056-native-execution-workspace.md`
- `adr/0077-go-task-developer-orchestration.md`
- `adr/0083-unified-node-initialization-contract.md`
- `adr/0085-deploy-bundle-and-runner-workspace-contract.md`
