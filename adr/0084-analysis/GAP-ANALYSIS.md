# ADR 0084: Gap Analysis

## Goal

Track remaining gap between implemented execution-plane model and full backend coverage:

- cross-platform dev plane,
- Linux-backed deploy plane,
- workspace-aware `DeployRunner`,
- deploy-bundle execution boundary aligned with ADR 0085.

---

## Current State

| Aspect | Status | Notes |
|--------|--------|-------|
| Dev workflows | ✅ Cross-platform | Python/task validation and compilation flows work across host OS |
| Terraform/OpenTofu | ✅ Integrated in deploy plane | Active deploy flow runs through runner workspace |
| Ansible | ✅ Linux-backed model explicit | Windows deploy path routes through WSL runner |
| WSL glue in entry points | ✅ Removed from business logic | Encapsulated in `WSLRunner` |
| Runner abstraction | ✅ Workspace-aware | stage/run/capabilities/cleanup contract active |
| Deploy execution input | ✅ Bundle-based for active flow | `service_chain_evidence.py` requires explicit bundle for execution |

---

## Target State

| Aspect | Target | Implementation Direction |
|--------|--------|--------------------------|
| Dev plane | Cross-platform | Keep authoring/compile workflows host-neutral |
| Deploy plane | Linux-backed | `DeployRunner` remains canonical boundary |
| Execution input | Deploy bundle | Consume explicit bundle instead of direct `generated/` paths |
| Runner contract | Workspace-aware | Stage bundle, run in workspace, report capabilities |
| Multiple backends | WSL, Docker, Remote | Same staging/execution model across backends |

---

## Remaining Gap Items

### G1: Docker backend runtime hardening follow-up

**Current:** `DockerRunner` is implemented with bundle staging by container mount and command execution via `docker run`.

**Target:** Toolchain image and CI workflow adoption are finalized.

**Action:** ✅ Completed with:

- `docker/Dockerfile.toolchain`
- task wrappers: `deploy:docker-toolchain-build`, `deploy:docker-toolchain-smoke`
- CI lane: `.github/workflows/deploy-runner-backends.yml`

### G2: Backend reliability validation is still pending

**Current:** `DockerRunner` and `RemoteLinuxRunner` are implemented with unit-test coverage.

**Target:** CI/release validation should exercise non-native backends in representative environments.

**Action:** Partially complete.

- Docker backend now has CI image build + smoke + runner tests.
- Remote runner contract tests expanded (rsync/scp staging, sync failure, cleanup semantics).
- Remaining: add remote-runner CI strategy (likely mocked contract tests + optional scheduled integration smoke on dedicated runner).

### G3: ADR 0083 entry points still need runner+bundle adoption

**Current:** Active service-chain evidence flow is migrated.

**Target:** Future ADR 0083 `init-node.py` flow uses identical runner+bundle boundary.

**Action:** enforce `--bundle` + runner workspace in ADR 0083 implementation.

---

## Implementation Progress

| Component | Status | Notes |
|-----------|--------|-------|
| `DeployRunner` module | ✅ Done | `scripts/orchestration/deploy/runner.py` |
| `NativeRunner` | ✅ Done | Full workspace-aware implementation |
| `WSLRunner` | ✅ Done | Full implementation with path translation |
| `DockerRunner` | ✅ Core implemented | Container execution + mount-based workspace |
| `RemoteLinuxRunner` | ✅ Core implemented | SSH run + remote workspace staging/cleanup |
| Workspace-aware contract | ✅ Done | `stage_bundle()`, `run()`, `capabilities()`, `cleanup_workspace()` |
| Bundle consumption in active flow | ✅ Done | `service_chain_evidence.py --bundle` |
| Legacy WSL refactor | ✅ Done | WSL logic moved into runner layer |
| Tests for runner+bundle workflow | ✅ Done | runner/profile/bundle/workflow tests |
| Operator docs for bundle workflow | ✅ Done | guide + runbook updates |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| WSL networking issues | Medium | High | Keep WSL execution guidance explicit in runbooks |
| Backend divergence (Docker/Remote) | Medium | High | Keep runner contract + unit tests as backend gate |
| Docker network mode for bootstrap | Low | Medium | Validate host-network requirements per mechanism |
| Remote staging drift | Medium | Medium | Keep bundle immutable, verify checksums pre-stage |
| ADR 0083 partial adoption | Medium | Medium | Reuse existing runner+bundle APIs instead of forked paths |

---

## Acceptance Signals

ADR 0084 is successfully adopted when:

1. [x] Linux-backed deploy plane is explicitly separated from cross-platform dev plane
2. [x] Runner contract is workspace-aware, not just path-aware
3. [x] Active deploy tooling consumes explicit bundle/workspace inputs
4. [x] `service_chain_evidence.py` is refactored away from hard-coded WSL logic
5. [x] Unit/integration tests cover runner staging and bundle-aware execution behavior
6. [x] Operator docs describe bundle-based deploy workflow and runner expectations
