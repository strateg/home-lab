# ADR 0085: Implementation Plan

## Overview

ADR 0085 defines the deploy bundle contract as the canonical execution input for deploy-domain tooling.

**Dependency chain:** ADR 0085 (bundle contract) -> ADR 0084 (deploy plane) -> ADR 0083 (optional init)

**State file location:** `.work/deploy-state/<project>/` per D6 (supersedes `.work/native/bootstrap/`)

---

## Phase 0: Runner Foundation ✅ COMPLETE

**Goal:** Workspace-aware runner contract.

| ID | Task | Output | Status |
|----|------|--------|--------|
| 0.1 | `DeployRunner` ABC with workspace methods | `runner.py` | ✅ Done |
| 0.2 | `NativeRunner` implementation | `runner.py` | ✅ Done |
| 0.3 | `WSLRunner` implementation | `runner.py` | ✅ Done |
| 0.4 | `DockerRunner` stub | `runner.py` | ✅ Done |
| 0.5 | `RemoteLinuxRunner` stub | `runner.py` | ✅ Done |
| 0.6 | `get_runner()` factory | `runner.py` | ✅ Done |
| 0.7 | `DeployWorkspace` resolver | `workspace.py` | ✅ Done |
| 0.8 | Refactor `service_chain_evidence.py` to runner model | Uses runner | ✅ Done |

**Gate:** ✅ All Phase 0 tasks complete.

---

## Phase 0a: Runner Tests ✅ COMPLETE

**Goal:** Add unit tests for runner module before profile/bundle rollout.

| ID | Task | Output | Status |
|----|------|--------|--------|
| 0a.1 | Create test file | `tests/orchestration/test_runner.py` | ✅ Done |
| 0a.2 | Test `NativeRunner` behavior | T-R01..T-R04 | ✅ Done |
| 0a.3 | Test `WSLRunner` behavior | T-R05..T-R07 | ✅ Done |
| 0a.4 | Test `get_runner()` selection/errors | T-R08..T-R10 | ✅ Done |
| 0a.5 | Test `RunResult.success` | T-R11..T-R12 | ✅ Done |

### Test Matrix (Phase 0a)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-R01 | `NativeRunner.is_available()` returns True on Linux | Unit |
| T-R02 | `NativeRunner.run()` executes simple command | Unit |
| T-R03 | `NativeRunner.translate_path()` returns resolved path | Unit |
| T-R04 | `NativeRunner.capabilities()` returns expected flags | Unit |
| T-R05 | `WSLRunner.translate_path()` converts `C:\` to `/mnt/c/` | Unit |
| T-R06 | `WSLRunner.is_available()` checks distro exists | Unit |
| T-R07 | `WSLRunner` skip on non-Windows | Unit |
| T-R08 | `get_runner("native")` returns `NativeRunner` | Unit |
| T-R09 | `get_runner("wsl")` returns `WSLRunner` | Unit |
| T-R10 | `get_runner("unknown")` raises `ValueError` | Unit |
| T-R11 | `RunResult.success` is True when `exit_code=0` | Unit |
| T-R12 | `RunResult.success` is False when `exit_code!=0` | Unit |

**Gate:** ✅ Runner tests pass locally.

---

## Phase 1: Deploy Profile Schema ✅ COMPLETE

**Goal:** Define and validate project-scoped deploy profile.

| ID | Task | Output | Status |
|----|------|--------|--------|
| 1.1 | Define deploy-profile schema | `schemas/deploy-profile.schema.json` | ✅ Done |
| 1.2 | Create example profile | `projects/home-lab/deploy/deploy-profile.yaml` | ✅ Done |
| 1.3 | Add profile loader | `scripts/orchestration/deploy/profile.py` | ✅ Done |
| 1.4 | Integrate with runner selection | `get_runner()` reads profile by default | ✅ Done |
| 1.5 | Add unit tests | `tests/orchestration/test_profile.py` | ✅ Done |

### Test Matrix (Phase 1)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-P01 | Profile schema validates correct YAML | Unit |
| T-P02 | Profile loader rejects invalid runner | Unit |
| T-P03 | Profile loader returns defaults when file missing | Unit |
| T-P04 | `get_runner()` respects profile default | Integration |
| T-P05 | WSL-specific profile settings are applied | Unit |
| T-P06 | Remote runner settings are parsed correctly | Unit |

**Gate:** ✅ Profile schema, loader, and tests are in place.

---

## Phase 2: Bundle Assembly ✅ COMPLETE

**Goal:** Create immutable deploy bundles from generated artifacts.

| ID | Task | Output | Status |
|----|------|--------|--------|
| 2.1 | Define bundle manifest schema | `schemas/deploy-bundle-manifest.schema.json` | ✅ Done |
| 2.2 | Implement bundle CLI/API | `scripts/orchestration/deploy/bundle.py` | ✅ Done |
| 2.3 | Implement bundle creation | `.work/deploy/bundles/<id>/` | ✅ Done |
| 2.4 | Secret injection at assembly | `bundle.py` `--inject-secrets` | ✅ Done |
| 2.5 | Bundle metadata generation | `metadata.yaml` | ✅ Done |
| 2.6 | Deterministic bundle ID generation | SHA256-derived ID | ✅ Done |
| 2.7 | Add unit tests | `tests/orchestration/test_bundle.py` | ✅ Done |
| 2.8 | Integrate assemble-stage plugin | `base.assembler.deploy_bundle` | ✅ Done |

### Bundle Structure

```
.work/deploy/bundles/<bundle_id>/
├── manifest.yaml
├── metadata.yaml
├── artifacts/
│   └── generated/
│       ├── terraform/
│       ├── ansible/
│       └── ...
└── checksums.sha256
```

### Test Matrix (Phase 2)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-B01 | Bundle manifest schema validates correct YAML | Unit |
| T-B02 | `bundle create` produces valid structure | Integration |
| T-B03 | Bundle ID is deterministic for same inputs | Unit |
| T-B04 | Secret injection from SOPS works | Integration |
| T-B05 | No secrets in bundle if SOPS fails | Unit |
| T-B06 | `bundle list` shows available bundles | Unit |
| T-B07 | `bundle inspect` shows bundle details | Unit |
| T-B08 | `bundle delete` removes bundle | Unit |
| T-B09 | Checksums are verified on bundle load | Unit |
| T-B10 | Bundle immutability constraints are enforced by workflow | Integration |

**Gate:** ✅ Bundle assembly creates valid immutable bundles and test suite passes.

---

## Phase 3: Entry Point Migration ✅ CORE COMPLETE

**Goal:** Deploy entry points consume `--bundle <bundle_id>`.

| ID | Task | Output | Status |
|----|------|--------|--------|
| 3.1 | Update `service_chain_evidence.py` | `--bundle` parameter and fail-fast in execution path | ✅ Done |
| 3.2 | Add `--bundle` to future `init-node.py` | CLI update | ⏸ Deferred to ADR 0083 implementation |
| 3.3 | Create operator guide | `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md` | ✅ Done |
| 3.4 | Update supporting docs | Runbooks + `CLAUDE.md` | ✅ Done |
| 3.5 | Add integration tests | `tests/orchestration/test_bundle_workflow.py` | ✅ Done |
| 3.6 | Bundle-path arg behavior in bundle mode | `tests/test_service_chain_evidence_plan.py` | ✅ Done |

### Test Matrix (Phase 3)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-W01 | Evidence tooling supports `--bundle` plan/execute flow | Integration |
| T-W02 | Missing bundle fails fast with clear error | Unit |
| T-W03 | Stale bundle triggers warning | Unit |
| T-W04 | Bundle selection is logged in evidence report | Integration |
| T-W05 | Runner workspace cleanup executes after run | Unit |

**Gate:** ✅ Active deploy entry point (`service_chain_evidence.py`) is bundle-ID based.

---

## Phase 4: Backend Completion (Partially Complete)

**Goal:** Complete Docker and Remote runners when needed.

| ID | Task | Trigger | Status |
|----|------|---------|--------|
| 4.1 | Create Docker toolchain image | CI needed | ✅ Done (`docker/Dockerfile.toolchain`) |
| 4.2 | Implement `DockerRunner` | CI needed | ✅ Done |
| 4.3 | Implement `RemoteLinuxRunner` | Control VM needed | ✅ Done |
| 4.4 | Add backend tests | After implementation | ✅ Done (unit contract tests + Docker backend CI lane) |

**Gate:** ✅ Implemented backend tests pass in CI; remote live-control-node smoke remains environment-dependent.

---

## Timeline

| Phase | Deliverable | Status | Depends On |
|-------|-------------|--------|------------|
| Phase 0 | Runner foundation | ✅ Complete | - |
| Phase 0a | Runner tests | ✅ Complete | Phase 0 |
| Phase 1 | Deploy profile | ✅ Complete | Phase 0a |
| Phase 2 | Bundle assembly | ✅ Complete | Phase 1 |
| Phase 3 | Entry point migration | ✅ Core complete | Phase 2 |
| Phase 4 | Backend completion | ✅ Core complete | Ongoing reliability hardening |

---

## Integration with ADR 0083/0084

### ADR 0084 Alignment

ADR 0084 execution-plane contract is now exercised with explicit bundle staging and bundle-based deploy execution for service-chain evidence flow.

### ADR 0083 Readiness

ADR 0083 is now unblocked on deploy-bundle contract:
- `init-node.py --bundle <bundle_id>` can reuse the existing bundle + runner primitives.
- Runtime mutable state remains in `.work/deploy-state/<project>/nodes/`.
- Bundle remains immutable execution input.

---

## Success Metrics

1. **Bundle determinism:** Same inputs -> same bundle ID.
2. **Secret isolation:** Zero secrets in `generated/`.
3. **Operator workflow:** Bundle create/list/inspect/delete + bundle-based evidence tasks documented.
4. **Test coverage:** Runner/profile/bundle/workflow tests pass for implemented phases.
