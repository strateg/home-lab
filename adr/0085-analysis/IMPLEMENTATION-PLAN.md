# ADR 0085: Implementation Plan

## Overview

ADR 0085 defines the deploy bundle contract as the canonical execution input for deploy-domain tooling.

**Dependency chain:** ADR 0085 (bundle contract) → ADR 0084 (deploy plane) → ADR 0083 (optional init)

---

## Phase 0: Runner Foundation ✅ COMPLETE

**Goal:** Workspace-aware runner contract.

| Task | Status | Notes |
|------|--------|-------|
| `DeployRunner` ABC with workspace methods | ✅ Done | `stage_bundle()`, `run()`, `capabilities()`, `cleanup_workspace()` |
| `NativeRunner` implementation | ✅ Done | Direct local execution |
| `WSLRunner` implementation | ✅ Done | Windows→WSL path translation |
| `DockerRunner` stub | ✅ Done | NotImplementedError placeholder |
| `RemoteLinuxRunner` stub | ✅ Done | NotImplementedError placeholder |
| `get_runner()` factory | ✅ Done | Auto-detection + explicit selection |

**Gate:** ✅ All Phase 0 tasks complete.

---

## Phase 1: Deploy Profile Schema

**Goal:** Define and validate project-scoped deploy profile.

| Task | Output | Status |
|------|--------|--------|
| Define deploy-profile schema | `schemas/deploy-profile.schema.json` | ❌ Pending |
| Create example profile | `projects/home-lab/deploy/deploy-profile.yaml` | ❌ Pending |
| Add profile loader | `scripts/orchestration/deploy/profile.py` | ❌ Pending |
| Integrate with runner selection | `get_runner()` reads profile | ❌ Pending |

**Gate:** Profile schema validated, example works with runners.

---

## Phase 2: Bundle Assembly

**Goal:** Create immutable deploy bundles from generated artifacts.

| Task | Output | Status |
|------|--------|--------|
| Define bundle manifest schema | `schemas/deploy-bundle-manifest.schema.json` | ❌ Pending |
| Implement assembler plugin | `base.assembler.deploy_bundle` | ❌ Pending |
| Secret injection at assembly | SOPS decryption into bundle | ❌ Pending |
| Bundle metadata generation | `metadata.yaml` with hash, provenance | ❌ Pending |
| Bundle ID generation | Deterministic from inputs | ❌ Pending |

**Gate:** Bundle assembly creates valid immutable bundles.

---

## Phase 3: Entry Point Migration

**Goal:** Deploy entry points consume `--bundle <bundle_id>`.

| Task | Output | Status |
|------|--------|--------|
| Update `service_chain_evidence.py` | `--bundle` parameter | ❌ Pending |
| Create bundle CLI | `bundle list`, `bundle inspect` | ❌ Pending |
| Update documentation | Operator guide with bundle workflow | ❌ Pending |

**Gate:** All deploy entry points use bundle-ID based execution.

---

## Phase 4: Backend Completion (Deferred)

**Goal:** Complete Docker and Remote runners when needed.

| Task | Trigger | Status |
|------|---------|--------|
| `DockerRunner` implementation | CI/CD integration | 🔜 Phase 0b |
| `RemoteLinuxRunner` implementation | Control VM needed | 🔜 Phase 0c |

**Gate:** Backend-specific tests pass.

---

## Timeline

| Phase | Deliverable | Status |
|-------|-------------|--------|
| Phase 0 | Runner foundation | ✅ Complete |
| Phase 1 | Deploy profile | 📅 Next |
| Phase 2 | Bundle assembly | 📅 After Phase 1 |
| Phase 3 | Entry point migration | 📅 After Phase 2 |
| Phase 4 | Backend completion | 📅 When needed |
