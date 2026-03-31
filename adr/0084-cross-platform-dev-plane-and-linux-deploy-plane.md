# ADR 0084: Cross-Platform Dev Plane and Linux Deploy Plane

**Date:** 2026-03-31
**Status:** Accepted (runner foundation and active bundle integration complete; Docker/Remote backend completion deferred)
**Related:** ADR 0056 (Native Execution Workspace), ADR 0072 (Unified Secrets Management), ADR 0075 (Monorepo Framework/Project Boundary), ADR 0076 (Framework Distribution and Multi-Repository Extraction), ADR 0077 (Go-Task Developer Orchestration), ADR 0080 (Unified Build Pipeline), ADR 0085 (Deploy Bundle and Runner Workspace Contract), ADR 0083 (Unified Node Initialization Contract)

---

## Context

The repository already separates topology authoring and artifact generation from infrastructure execution:

- `scripts/orchestration/lane.py` runs Python-based validation and compilation steps.
- `topology-tools/compile-topology.py` generates Terraform, Ansible, bootstrap, and documentation artifacts under `generated/<project>/`.
- Deploy-time commands live outside the compiler boundary and must execute from deploy-domain inputs rather than directly from source-derived artifact roots.

ADR 0075 and ADR 0076 add another requirement: the deploy plane must keep working whether the project is executed from the current main repository or from an extracted project repository with framework dependency pinned and verified.

Universality is required here: both repository topologies are first-class operator modes, not a primary mode plus a compatibility mode.

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

Under ADR 0076, equivalent project-local authoring and generation workflows in an extracted project repository are also part of the dev plane, provided framework dependency verification has succeeded.

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

This Linux-backed requirement applies equally to:
- current main-repository project workspaces,
- ADR 0076 extracted project repositories,
- staged workspaces assembled from either mode for `docker` or `remote` backends.

### D4. Supported Deploy Backends

The deploy plane uses a `DeployRunner` abstraction to support multiple execution backends:

| Backend | Class | Status | Use Case |
|---------|-------|--------|----------|
| `native` | `NativeRunner` | ✅ Implemented | Local Linux workstation |
| `wsl` | `WSLRunner` | ✅ Implemented | Windows developer workflow |
| `docker` | `DockerRunner` | ✅ Implemented (core) | Reproducible CI execution |
| `remote` | `RemoteLinuxRunner` | ✅ Implemented (core) | Dedicated control node via SSH |

**Auto-detection:**
- On Windows → `WSLRunner` (default)
- On Linux → `NativeRunner` (default)
- Explicit selection via `--runner` flag

Backend selection operates on a resolved project workspace and deploy bundle. It MUST NOT assume framework sources are present in the same filesystem layout during execution.
The same runner contract and entrypoints SHOULD be usable from both the current main repository and separated project repositories.

### D5. Deploy Runner Abstraction

Deploy tooling uses `DeployRunner` abstraction for consistent workspace-aware execution across backends. The full contract is defined in ADR 0085 D5 and implemented in `scripts/orchestration/deploy/runner.py`.

**Key methods:**

| Method | Purpose |
|--------|---------|
| `stage_bundle(bundle_path)` | Stage deploy bundle, return workspace reference |
| `run(cmd, workspace_ref, env, timeout)` | Execute command in staged workspace |
| `capabilities()` | Report backend capabilities (network, path translation, etc.) |
| `cleanup_workspace(workspace_ref)` | Clean up temporary backend state |
| `translate_path(path)` | Convert host path to backend-accessible path |
| `is_available()` | Check if backend is available on current host |
| `check_tool(tool)` | Verify tool availability in backend environment |

**Implementation status:**

| Runner | Status | Notes |
|--------|--------|-------|
| `NativeRunner` | ✅ Implemented | Direct Linux execution |
| `WSLRunner` | ✅ Implemented | Windows→WSL with path translation |
| `DockerRunner` | ✅ Core implemented | Uses `docker run` with mounted bundle workspace |
| `RemoteLinuxRunner` | ✅ Core implemented | SSH execution with staged remote workspace |

**Rationale:** ADR 0085 introduces deploy bundle as the canonical execution input. A simple `run()+translate_path()` abstraction is not enough for `wsl`, `docker`, and `remote` backends. The runner contract therefore must stage bundles into backend workspaces, execute there, report capabilities, and clean up.

Per ADR 0075 and ADR 0076, that staged workspace is project-scoped. Framework dependency resolution and lock verification happen before runner execution and are not delegated to backend-specific runner logic.

### D6. ADR 0083 Would Execute Within This Plane Model

If ADR 0083 is implemented later, its node initialization and post-initialization handover are governed by this execution-plane model:

- source-derived artifacts may be generated from any supported dev plane and from any ADR 0075/0076-compliant project workspace,
- assemble/build materializes a deploy bundle per ADR 0085,
- initialization execution stages that bundle into a Linux-backed runner workspace,
- Terraform/OpenTofu handover and Ansible configuration remain in the same Linux-backed deploy plane and consume the same bundle/workspace boundary.

ADR 0084 depends on ADR 0085 for canonical execution input and workspace contract. ADR 0083, if pursued later, depends on both ADR 0085 and ADR 0084.

---

## Consequences

### Benefits

- The repository keeps a genuinely cross-platform authoring experience.
- The same deploy-plane contract works for both ADR 0075 monorepo usage and ADR 0076 extracted project repositories.
- The same deploy entry model remains usable from the current main repository and from separated project repositories.
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
2. ADR 0076 project-repo flows reuse the same deploy-plane model after framework lock verification.
3. Deploy tooling (`init-node.py`, Terraform, Ansible) runs via `DeployRunner`.
4. Deploy tooling consumes explicit `bundle_id` inputs rather than executing directly from `generated/`.
5. `service_chain_evidence.py` uses deploy bundle staging and runner-managed execution.
6. ADR 0083 adapters would receive runner and workspace context via dependency injection if ADR 0083 is implemented later.

### Implementation Phases

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0a | Workspace-aware `DeployRunner` contract + `NativeRunner` + `WSLRunner` | ✅ Complete |
| 0a.1 | `service_chain_evidence.py` refactored to use runner | ✅ Complete |
| 0b | `DockerRunner` + bundle mounting/staging strategy | ✅ Core complete (CI image/workflow pending) |
| 0c | `RemoteLinuxRunner` + remote bundle staging strategy | ✅ Core complete (operator hardening docs pending) |

See `adr/0084-analysis/` and `adr/0085-analysis/` for detailed progress tracking.

---

## References

- `scripts/orchestration/deploy/runner.py` — DeployRunner abstraction (NEW)
- `scripts/orchestration/lane.py` — Dev plane orchestration
- `topology-tools/utils/service_chain_evidence.py` — Bundle-aware service-chain execution via deploy runner
- `docs/runbooks/evidence/2026-03-28-wave-d-service-chain-evidence.md`
- `adr/0056-native-execution-workspace.md`
- `adr/0077-go-task-developer-orchestration.md`
- `adr/0083-unified-node-initialization-contract.md`
- `adr/0075-framework-project-separation.md`
- `adr/0076-framework-distribution-and-multi-repository-extraction.md`
- `adr/0085-deploy-bundle-and-runner-workspace-contract.md`
