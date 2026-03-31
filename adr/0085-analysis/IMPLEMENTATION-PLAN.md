# ADR 0085: Implementation Plan

## Overview

ADR 0085 defines the deploy bundle contract as the canonical execution input for deploy-domain tooling.

**Dependency chain:** ADR 0085 (bundle contract) → ADR 0084 (deploy plane) → ADR 0083 (optional init)

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
| 0.8 | Refactor `service_chain_evidence.py` | Uses runner | ✅ Done |

**Gate:** ✅ All Phase 0 tasks complete.

---

## Phase 1: Deploy Profile Schema

**Goal:** Define and validate project-scoped deploy profile.

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 1.1 | Define deploy-profile schema | `schemas/deploy-profile.schema.json` | Valid JSONSchema 2020-12 |
| 1.2 | Create example profile | `projects/home-lab/deploy/deploy-profile.yaml` | Passes schema validation |
| 1.3 | Add profile loader | `scripts/orchestration/deploy/profile.py` | Loads and validates profile |
| 1.4 | Integrate with runner selection | `get_runner()` reads profile | Default runner from profile |
| 1.5 | Add unit tests | `tests/orchestration/test_profile.py` | T-P01..T-P06 pass |

### Deploy Profile Schema

```yaml
# projects/<project>/deploy/deploy-profile.yaml
schema_version: "1.0"
project: home-lab

default_runner: native  # native | wsl | docker | remote

runners:
  wsl:
    distro: Ubuntu
  docker:
    image: homelab-toolchain:latest
    network: host
  remote:
    host: control.example.com
    user: deploy
    sync_method: rsync  # rsync | git

timeouts:
  handover_total: 300
  handover_check: 30
  terraform_plan: 120
  ansible_playbook: 600

bundle:
  retention_count: 5  # Keep last N bundles
  auto_cleanup: true
```

### Test Matrix (Phase 1)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-P01 | Profile schema validates correct YAML | Unit |
| T-P02 | Profile loader rejects invalid runner | Unit |
| T-P03 | Profile loader returns defaults when file missing | Unit |
| T-P04 | `get_runner()` respects profile default | Integration |
| T-P05 | WSL-specific profile settings are applied | Unit |
| T-P06 | Remote runner settings are parsed correctly | Unit |

**Gate:** Profile schema validated, example works with runners, tests pass.

---

## Phase 2: Bundle Assembly

**Goal:** Create immutable deploy bundles from generated artifacts.

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 2.1 | Define bundle manifest schema | `schemas/deploy-bundle-manifest.schema.json` | Valid JSONSchema 2020-12 |
| 2.2 | Define bundle CLI | `scripts/orchestration/deploy/bundle.py` | `bundle create`, `list`, `inspect`, `delete` |
| 2.3 | Implement bundle creation | `bundle.py` | Creates `.work/deploy/bundles/<id>/` |
| 2.4 | Secret injection at assembly | `bundle.py` | SOPS decrypts into bundle artifacts |
| 2.5 | Bundle metadata generation | `metadata.yaml` | Hash, timestamp, source refs |
| 2.6 | Bundle ID generation | Deterministic | SHA256 of inputs |
| 2.7 | Add unit tests | `tests/orchestration/test_bundle.py` | T-B01..T-B10 pass |

### Bundle Structure

```
.work/deploy/bundles/<bundle_id>/
├── manifest.yaml              # Execution manifest (nodes, artifacts, checksums)
├── metadata.yaml              # Provenance (created_at, source_hash, creator)
├── artifacts/
│   ├── rtr-mikrotik-chateau/
│   │   ├── init-terraform.rsc     # Secret-bearing bootstrap script
│   │   └── terraform.tfvars       # Secret-bearing Terraform vars
│   ├── hv-proxmox-xps/
│   │   ├── answer.toml
│   │   └── post-install.sh
│   └── ...
└── checksums.sha256           # Integrity verification
```

### Bundle Manifest Schema

```yaml
# .work/deploy/bundles/<id>/manifest.yaml
schema_version: "1.0"
bundle_id: "b-20260331-abc123"
created_at: "2026-03-31T12:00:00Z"

source:
  project: home-lab
  topology_hash: "sha256:..."
  secrets_hash: "sha256:..."

nodes:
  - id: rtr-mikrotik-chateau
    mechanism: netinstall
    artifacts:
      - path: artifacts/rtr-mikrotik-chateau/init-terraform.rsc
        checksum: "sha256:..."
      - path: artifacts/rtr-mikrotik-chateau/terraform.tfvars
        checksum: "sha256:..."
    contract_hash: "sha256:..."
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
| T-B10 | Bundle immutability is enforced | Integration |

**Gate:** Bundle assembly creates valid immutable bundles, tests pass.

---

## Phase 3: Entry Point Migration

**Goal:** Deploy entry points consume `--bundle <bundle_id>`.

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 3.1 | Update `service_chain_evidence.py` | `--bundle` parameter | Bundle-based execution |
| 3.2 | Add `--bundle` to future `init-node.py` | CLI update | ADR 0083 integration ready |
| 3.3 | Create operator guide | `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md` | Bundle lifecycle documented |
| 3.4 | Update CLAUDE.md | Dev/Deploy plane docs | Workflow clear to AI agents |
| 3.5 | Add integration tests | `tests/orchestration/test_bundle_workflow.py` | T-W01..T-W05 pass |

### Test Matrix (Phase 3)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-W01 | Evidence tooling runs with `--bundle` | Integration |
| T-W02 | Missing bundle fails fast with clear error | Unit |
| T-W03 | Stale bundle triggers warning | Unit |
| T-W04 | Bundle selection is logged in audit trail | Integration |
| T-W05 | Cleanup removes temporary workspace | Unit |

**Gate:** All deploy entry points use bundle-ID based execution.

---

## Phase 0a: Runner Tests (NEXT)

**Goal:** Add unit tests for runner module before continuing to Phase 1.

| ID | Task | Output | Acceptance Criteria |
|----|------|--------|---------------------|
| 0a.1 | Create test file | `tests/orchestration/test_runner.py` | File exists |
| 0a.2 | Test NativeRunner | T-R01..T-R04 | All pass |
| 0a.3 | Test WSLRunner | T-R05..T-R07 | All pass (skip on Linux) |
| 0a.4 | Test get_runner() | T-R08..T-R10 | All pass |
| 0a.5 | Test RunResult | T-R11..T-R12 | All pass |

### Test Matrix (Phase 0a)

| Test ID | Description | Category |
|---------|-------------|----------|
| T-R01 | `NativeRunner.is_available()` returns True on Linux | Unit |
| T-R02 | `NativeRunner.run()` executes simple command | Unit |
| T-R03 | `NativeRunner.translate_path()` returns resolved path | Unit |
| T-R04 | `NativeRunner.capabilities()` returns expected flags | Unit |
| T-R05 | `WSLRunner.translate_path()` converts C:\\ to /mnt/c/ | Unit |
| T-R06 | `WSLRunner.is_available()` checks distro exists | Unit |
| T-R07 | `WSLRunner` skip on non-Windows | Unit |
| T-R08 | `get_runner("native")` returns NativeRunner | Unit |
| T-R09 | `get_runner("wsl")` returns WSLRunner | Unit |
| T-R10 | `get_runner("unknown")` raises ValueError | Unit |
| T-R11 | `RunResult.success` is True when exit_code=0 | Unit |
| T-R12 | `RunResult.success` is False when exit_code!=0 | Unit |

**Gate:** All runner tests pass.

---

## Phase 4: Backend Completion (Deferred)

**Goal:** Complete Docker and Remote runners when needed.

| ID | Task | Trigger | Status |
|----|------|---------|--------|
| 4.1 | Create Docker toolchain image | CI needed | 🔜 Deferred |
| 4.2 | Implement `DockerRunner` | CI needed | 🔜 Deferred |
| 4.3 | Implement `RemoteLinuxRunner` | Control VM needed | 🔜 Deferred |
| 4.4 | Add backend tests | After implementation | 🔜 Deferred |

**Gate:** Backend-specific tests pass.

---

## Timeline

| Phase | Deliverable | Status | Depends On |
|-------|-------------|--------|------------|
| Phase 0 | Runner foundation | ✅ Complete | - |
| Phase 0a | Runner tests | 📅 **NEXT** | Phase 0 |
| Phase 1 | Deploy profile | 📅 Planned | Phase 0a |
| Phase 2 | Bundle assembly | 📅 Planned | Phase 1 |
| Phase 3 | Entry point migration | 📅 Planned | Phase 2 |
| Phase 4 | Backend completion | 📅 Deferred | When needed |

---

## Integration with ADR 0083/0084

### ADR 0084 Alignment

ADR 0084 Phase 0a (runner tests) maps to ADR 0085 Phase 0a. The test matrix is shared.

### ADR 0083 Readiness

After ADR 0085 Phase 2 (bundle assembly), ADR 0083 can proceed with:
- `init-node.py --bundle <bundle_id>` execution model
- State files in `.work/deploy-state/<project>/nodes/`
- Immutable bundle as execution input

---

## Success Metrics

1. **Test coverage:** >80% for runner, profile, bundle modules
2. **Bundle determinism:** Same inputs → same bundle ID
3. **Secret isolation:** Zero secrets in `generated/`
4. **Documentation:** Operator guide complete
