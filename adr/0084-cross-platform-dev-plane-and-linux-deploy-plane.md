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

### D4. Supported Deploy Environments

The deploy plane runs on Linux. For Windows operators, WSL provides the Linux environment:

| Environment | Status | Use Case |
|-------------|--------|----------|
| Native Linux | ✅ Supported | Linux workstation, CI runner, Control VM |
| WSL2 (Ubuntu) | ✅ Supported | Windows developer workflow |
| macOS | ⚠️ Limited | Ansible works, but `netinstall-cli` unavailable |
| Windows native | ❌ Not supported | Use WSL instead |

**Future backends** (not implemented, defer to separate ADR when needed):
- `docker` - reproducible CI execution environment
- `remote-linux` - dedicated control node or VM

### D5. Simple Environment Check, Not Abstraction Layer

Deploy tooling MUST verify the execution environment at startup and fail fast with clear instructions if not Linux-backed.

**Implementation:**

```python
# scripts/orchestration/deploy/environment.py

import sys
import platform

def check_deploy_environment() -> str:
    """Verify Linux deploy plane. Returns 'linux' or 'wsl', exits on Windows."""
    system = platform.system()

    if system == "Windows":
        print("ERROR: Deploy plane requires Linux. Use WSL:")
        print("    wsl")
        print("    cd /mnt/c/path/to/home-lab")
        print("    python scripts/orchestration/deploy/init-node.py ...")
        sys.exit(1)

    if system == "Linux":
        if "microsoft" in platform.uname().release.lower():
            return "wsl"
        return "linux"

    return system.lower()  # macos, etc.
```

**Rationale:** A simple environment check (50 lines) is preferred over a deploy-runner abstraction layer (200+ lines). Abstract when there's a concrete need for multiple backends, not before.

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
- Simple environment check (not abstraction layer) keeps code maintainable.
- Clear error messages guide Windows operators to WSL.

### Trade-Offs

- Windows-native Terraform/OpenTofu deploy flows are no longer the canonical operator path.
- Local operators on Windows must use WSL for deploy operations.
- Documentation must clearly distinguish dev-plane from deploy-plane workflows.

### Migration Impact

1. Existing Python compile/generate flows remain unchanged (dev plane).
2. Deploy tooling (`init-node.py`, Terraform, Ansible) runs from Linux/WSL.
3. ADR 0083 integrates `check_deploy_environment()` in Phase 0.
4. Future Docker/remote-linux backends deferred to separate ADR when needed.

### What We Are NOT Doing

- ❌ No `DeployRunner` abstraction class
- ❌ No backend adapter pattern (yet)
- ❌ No Docker/remote-linux implementation (deferred)

**Rationale:** Single-operator home-lab does not need enterprise-grade runner abstraction. WSL solves the problem. Abstract later if CI/CD or multi-operator scenarios emerge.

---

## References

- `scripts/orchestration/lane.py`
- `topology-tools/utils/service_chain_evidence.py`
- `docs/runbooks/evidence/2026-03-28-wave-d-service-chain-evidence.md`
- `adr/0056-native-execution-workspace.md`
- `adr/0077-go-task-developer-orchestration.md`
- `adr/0083-unified-node-initialization-contract.md`
