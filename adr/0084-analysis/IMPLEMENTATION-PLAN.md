# ADR 0084: Implementation Plan

## Overview

ADR 0084 defines the execution-plane model:

- cross-platform dev plane,
- Linux-backed deploy plane,
- workspace-aware `DeployRunner`,
- bundle/workspace execution aligned with ADR 0085.

This plan tracks runner-plane adoption and backend completion gates.

---

## Phase 0a: Runner Contract Alignment ✅ COMPLETE

**Goal:** Align `DeployRunner`, `NativeRunner`, and `WSLRunner` with workspace-aware execution.

| ID | Task | Output | Status |
|----|------|--------|--------|
| 0a.1 | Update runner contract | `scripts/orchestration/deploy/runner.py` | ✅ Done |
| 0a.2 | Align `NativeRunner` | `runner.py` | ✅ Done |
| 0a.3 | Align `WSLRunner` | `runner.py` | ✅ Done |
| 0a.4 | Update package exports | `scripts/orchestration/deploy/__init__.py` | ✅ Done |
| 0a.5 | Add runner tests | `tests/orchestration/test_runner.py` | ✅ Done |
| 0a.6 | Refactor evidence tooling to runner API | `service_chain_evidence.py` | ✅ Done |

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

### Gate

- [x] ADR 0084 wording aligned to bundle/workspace model
- [x] `runner.py` exposes workspace-aware contract
- [x] `NativeRunner` and `WSLRunner` aligned
- [x] Runner tests pass
- [x] Evidence tooling uses runner API

---

## ADR 0085 Integration: Bundle-Based Execution ✅ COMPLETE

**Goal:** Ensure active deploy entry points execute from explicit bundles in runner workspaces.

| ID | Task | Output | Status |
|----|------|--------|--------|
| I.1 | Add explicit bundle resolution | `service_chain_evidence.py --bundle` | ✅ Done |
| I.2 | Verify bundle integrity before staging | `inspect_bundle(..., verify_checksums=True)` | ✅ Done |
| I.3 | Stage selected bundle in runner workspace | `runner.stage_bundle(bundle_path)` | ✅ Done |
| I.4 | Include bundle in evidence report | `render_report(..., bundle=...)` | ✅ Done |
| I.5 | Handle bundle-mode path arguments safely | preserve relative backend/var paths | ✅ Done |
| I.6 | Add bundle workflow tests | `tests/orchestration/test_bundle_workflow.py` | ✅ Done |

### Active Flow Snapshot

```python
runner = get_runner(args.deploy_runner, repo_root=repo_root, project_id=args.project_id)
bundle_path = _resolve_bundle_for_execution(repo_root=repo_root, bundle_ref=args.bundle)
bundle_details = inspect_bundle(bundle_path, verify_checksums=True)
workspace_ref = runner.stage_bundle(bundle_path)
result = runner.run(step.command, workspace_ref=workspace_ref)
runner.cleanup_workspace(workspace_ref)
```

---

## Phase 0b: Docker Runner ✅ CORE IMPLEMENTED

**Goal:** Add `DockerRunner` for reproducible CI execution.

**Trigger:** CI/CD pipeline integration or reproducible deploy sandbox requirement.

| ID | Task | Output | Status |
|----|------|--------|--------|
| 0b.1 | Create Docker toolchain image | `docker/Dockerfile.toolchain` | ✅ Done |
| 0b.2 | Implement bundle staging strategy | `runner.py` | ✅ Done (mount bundle path into container workspace) |
| 0b.3 | Implement `DockerRunner` | `runner.py` | ✅ Done |
| 0b.4 | Add tests | `tests/orchestration/test_runner.py` | ✅ Done |
| 0b.5 | Integrate CI usage | workflow/docs | ✅ Done (`.github/workflows/deploy-runner-backends.yml`, Docker runner guide + task wrappers) |

---

## Phase 0c: Remote Linux Runner ✅ CORE IMPLEMENTED

**Goal:** Add `RemoteLinuxRunner` for dedicated control-node execution.

**Trigger:** Dedicated control VM, multi-operator usage, or remote execution requirement.

| ID | Task | Output | Status |
|----|------|--------|--------|
| 0c.1 | Define remote staging strategy | `runner.py` | ✅ Done (`rsync|scp` upload) |
| 0c.2 | Implement `RemoteLinuxRunner` | `runner.py` | ✅ Done |
| 0c.3 | Define remote secret handling | docs | ✅ Done (`docs/guides/REMOTE-RUNNER-SETUP.md`) |
| 0c.4 | Add tests | `tests/orchestration/test_runner.py` | ✅ Done |

---

## Integration with ADR 0083

ADR 0083 entry points should consume runner + workspace context with explicit bundle selection:

```python
runner = get_runner(args.runner, repo_root=repo_root, project_id=args.project_id)
workspace_ref = runner.stage_bundle(bundle_path)
adapter = get_adapter(mechanism, runner=runner, workspace_ref=workspace_ref)
```

This preserves:
- bundle selection in orchestrator layer,
- execution inside runner workspace,
- mutable state/logs outside immutable bundle.

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 0a: Contract alignment | 2 days | ✅ Complete |
| ADR 0085 integration in active flow | 1 day | ✅ Complete |
| Phase 0b: Docker | 2 days | ✅ Complete |
| Phase 0c: Remote | 3 days | ✅ Core implemented |
