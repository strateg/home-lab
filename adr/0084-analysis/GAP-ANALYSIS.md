# ADR 0084: Gap Analysis

## Goal

Define the gap between the current mixed execution model and the target model:

- cross-platform dev plane,
- Linux-backed deploy plane,
- workspace-aware `DeployRunner`,
- deploy bundle execution boundary aligned with ADR 0085.

---

## Current State

| Aspect | Status | Issue |
|--------|--------|-------|
| Dev workflows | ✅ Cross-platform | Python-based validation and compilation already work across platforms |
| Terraform/OpenTofu | ⚠️ Mixed | Can run on Windows, but canonical deploy execution should share runtime with Ansible |
| Ansible | ❌ Linux-only | Requires Linux-backed control environment |
| WSL glue | ⚠️ Hard-coded | `service_chain_evidence.py` still contains WSL-specific execution/path logic |
| Runner abstraction | ⚠️ Partial | `runner.py` exists, but current contract is process-centric rather than workspace-centric |
| Deploy execution input | ❌ Undefined | No formal bundle/workspace contract in active code paths |

---

## Target State

| Aspect | Target | Implementation Direction |
|--------|--------|--------------------------|
| Dev plane | Cross-platform | No change to authoring/compile workflows |
| Deploy plane | Linux-backed | `DeployRunner` remains the canonical execution boundary |
| Execution input | Deploy bundle | Consume explicit bundle instead of direct `generated/` paths |
| Runner contract | Workspace-aware | Stage bundle, run in workspace, report capabilities |
| Multiple backends | WSL, Docker, Remote | Same staging/execution model across backends |

---

## Gap Items

### G1: Runner abstraction exists, but wrong shape ✅ RESOLVED

**Current:** `DeployRunner` is implemented with full workspace-aware contract: `stage_bundle()`, `run()`, `capabilities()`, `cleanup_workspace()`, `translate_path()`, `is_available()`, `check_tool()`.

**Target:** `DeployRunner` must stage deploy bundles into backend workspaces, execute there, expose capabilities, and clean up workspace state.

**Status:** Implemented in `scripts/orchestration/deploy/runner.py`. NativeRunner and WSLRunner are fully functional.

### G2: Deploy execution still assumes local-path semantics

**Current:** Active tooling and surrounding analysis still assume direct execution from repo-local paths or WSL-translated paths.

**Target:** All deploy tooling consumes explicit bundle/workspace inputs per ADR 0085.

**Action:** Refactor deploy tooling and supporting docs to treat deploy bundle as the canonical execution source.

### G3: `service_chain_evidence.py` needs refactoring ✅ RESOLVED

**Current:** Uses `get_runner()`, `runner.stage_bundle()`, `runner.run()`, and `runner.cleanup_workspace()`.

**Target:** Uses bundle-aware runner staging and runner-managed execution.

**Status:** Refactored. WSL-specific path translation moved to WSLRunner. Legacy `--ansible-via-wsl` flag bridges to runner factory.

### G4: ADR 0083 integration still needs workspace context

**Current:** ADR 0083 design and nearby tooling historically assumed local execution roots.

**Target:** `init-node.py` and bootstrap adapters operate on:
- `bundle_id`,
- runner,
- workspace reference,
- deploy profile.

**Action:** Ensure ADR 0083 Phase 5 design follows the ADR 0084 + ADR 0085 execution model.

### G5: Docker backend is still only a stub

**Current:** `DockerRunner` exists as placeholder.

**Target:** Bundle staging/mounting strategy is defined and implemented.

**Action:** Defer implementation to Phase 0b, but keep the contract explicit now.

### G6: Remote Linux backend is still only a stub

**Current:** `RemoteLinuxRunner` exists as placeholder.

**Target:** Remote bundle staging strategy is defined and implemented.

**Action:** Defer implementation to Phase 0c, but keep the contract explicit now.

### G7: Operator documentation is still incomplete

**Current:** Tool installation and runner expectations are scattered.

**Target:** Operator documentation distinguishes:
- dev plane,
- deploy plane,
- bundle selection,
- backend prerequisites.

**Action:** Create or update operator environment/setup guide and deploy runbooks.

---

## Implementation Progress

| Component | Status | Notes |
|-----------|--------|-------|
| `DeployRunner` module | ✅ Done | `scripts/orchestration/deploy/runner.py` |
| `NativeRunner` | ✅ Done | Full workspace-aware implementation |
| `WSLRunner` | ✅ Done | Full workspace-aware implementation with path translation |
| `DockerRunner` | 🔜 Stub | Phase 0b |
| `RemoteLinuxRunner` | 🔜 Stub | Phase 0c |
| Workspace-aware contract | ✅ Done | `stage_bundle()`, `run()`, `capabilities()`, `cleanup_workspace()` |
| Bundle consumption | ⚠️ Transitional | Uses `stage_bundle(repo_root)` pending ADR 0085 bundle assembly |
| Legacy WSL refactor | ✅ Done | `service_chain_evidence.py` uses runner |
| Tests | ❌ Pending | Need tests for staging, capabilities, and backend selection |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| WSL networking issues | Medium | High | Document WSL2 network modes and constraints |
| Bundle/workspace mismatch across backends | Medium | High | Define runner contract before broad backend rollout |
| Docker network mode for bootstrap | Low | Medium | Validate host-network requirements per mechanism |
| Remote staging drift | Medium | Medium | Make bundle immutable and include provenance/hash |
| Partial adoption | Medium | Medium | Update ADR 0083, ADR 0084, runner code, and evidence tooling together |

---

## Acceptance Signals

ADR 0084 is successfully adopted when:

1. [x] Linux-backed deploy plane is explicitly separated from cross-platform dev plane
2. [x] Runner contract is workspace-aware, not just path-aware
3. [ ] Deploy tooling consumes explicit bundle/workspace inputs (pending ADR 0085 bundle assembly)
4. [x] `service_chain_evidence.py` is refactored away from hard-coded WSL logic
5. [ ] Unit/integration tests cover runner staging and capability behavior
6. [ ] Operator docs clearly describe dev-plane vs deploy-plane workflows
