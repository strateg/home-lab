# ADR 0083/0084/0085: Unified Implementation Sequence

**Date:** 2026-03-31 (updated)
**Status:** Active — ADR 0085/0084 core complete; ADR 0083 scaffold complete, hardware validation pending
**Purpose:** Single execution sequence across deploy-domain ADRs.

---

## Priority Order (Confirmed)

```
ADR 0085 (bundle contract) -> ADR 0084 (deploy plane) -> ADR 0083 (optional init)
     ↓                            ↓                         ↓
  COMPLETE                     COMPLETE                  SCAFFOLD READY
```

---

## Current State Summary

| ADR | Status | Completed Scope | Remaining |
|-----|--------|-----------------|-----------|
| 0085 | **Accepted** | Phases 0–4 complete: runner foundation + tests + profile + bundle assembly + entry point migration + backend implementation | Backend reliability follow-ups (remote CI) |
| 0084 | **Accepted** | Runner plane + bundle-based deploy flow + DockerRunner/RemoteRunner + Docker toolchain image + backend CI lane | Remote backend smoke tests |
| 0083 | **Proposed** (scaffold complete) | Schema + validator + contract declarations (MikroTik/Proxmox/OrangePi) + init-node CLI/state/status + 4 adapter baselines + state machine + structured logging + environment precheck + bundle-manifest mechanism inference + 83 orchestration tests | Adapter execute() implementation + hardware tests |

---

## Completed Sequence (This Wave)

### Phase 1: Deploy Profile ✅

- `schemas/deploy-profile.schema.json`
- `projects/home-lab/deploy/deploy-profile.yaml`
- `scripts/orchestration/deploy/profile.py`
- `tests/orchestration/test_profile.py`

### Phase 2: Bundle Assembly ✅

- `schemas/deploy-bundle-manifest.schema.json`
- `scripts/orchestration/deploy/bundle.py` (`create/list/inspect/delete`)
- deterministic bundle IDs + checksums + metadata
- `tests/orchestration/test_bundle.py`

### Phase 3: Entry Point Migration (Active Flow) ✅

- `topology-tools/utils/service_chain_evidence.py` consumes `--bundle`
- checksum verification + stale-bundle warning before runner staging
- bundle recorded in evidence report
- task wrappers and operator docs updated
- `tests/orchestration/test_bundle_workflow.py`

---

## Remaining Work Buckets

### Bucket A: Runner Backend Hardening (ADR 0084)

| Item | Trigger | Status |
|------|---------|--------|
| `DockerRunner` CI image/workflow | CI reproducibility | ✅ Complete |
| `RemoteLinuxRunner` contract tests | Unit coverage | ✅ Complete |
| Remote backend CI smoke | Dedicated runner infra | ⏸ Environment-dependent |

### Bucket B: ADR 0083 Hardware Validation

| Item | Dependency | Status |
|------|------------|--------|
| Adapter `execute()` implementation | Hardware access | ⏸ Pending |
| MikroTik netinstall E2E | Physical router | ⏸ Pending |
| Proxmox unattended install E2E | Fresh install media | ⏸ Pending |
| OrangePi cloud-init E2E | SBC hardware | ⏸ Pending |
| Handover check retry logic | Adapter execute | ⏸ Pending |

---

## State File Locations (Unified)

| Path | Purpose | ADR |
|------|---------|-----|
| `.work/deploy/bundles/<bundle_id>/` | Immutable deploy bundles | 0085 |
| `.work/deploy-state/<project>/nodes/` | Initialization state | 0083 |
| `.work/deploy-state/<project>/logs/` | Audit logs | 0083 |

**Superseded:** `.work/native/bootstrap/`

---

## Test Matrix Summary

| Scope | Tests | Status |
|-------|-------|--------|
| Runner | 23 tests (Native/WSL/Docker/Remote) | ✅ Pass |
| Profile | 8 tests | ✅ Pass |
| Bundle | 11 tests | ✅ Pass |
| Bundle workflow | 5 tests | ✅ Pass |
| Init-node CLI | 14 tests | ✅ Pass |
| Adapters | 9 tests | ✅ Pass |
| State machine | 5 tests | ✅ Pass |
| Logging | 2 tests | ✅ Pass |
| Environment | 5 tests | ✅ Pass |
| **Total** | **83 tests (82 pass, 1 WSL skip)** | ✅ |

---

## Success Criteria Snapshot

| Criterion | Status |
|-----------|--------|
| ADR 0085 core flow is bundle-based and tested | ✅ Complete |
| ADR 0084 runner plane is active for bundle staging/execution | ✅ Complete |
| Documentation reflects bundle-first operator workflow | ✅ Complete |
| ADR 0083 scaffold uses existing bundle + runner contract | ✅ Complete |
| ADR 0083 hardware validation | ⏸ Pending |

---

## Implementation Artifacts Summary

```
scripts/orchestration/deploy/
├── __init__.py
├── adapters/
│   ├── __init__.py          # get_adapter() factory
│   ├── base.py              # BootstrapAdapter ABC + dataclasses
│   ├── netinstall.py        # MikroTik adapter
│   ├── unattended.py        # Proxmox adapter
│   ├── cloud_init.py        # OrangePi adapter
│   └── ansible_bootstrap.py # Generic Ansible adapter
├── bundle.py                # Bundle create/list/inspect/delete
├── environment.py           # Deploy environment precheck
├── init_node.py             # Main orchestrator (30KB)
├── logging.py               # Structured JSONL audit
├── profile.py               # Deploy profile loader
├── runner.py                # DeployRunner backends (25KB)
├── state.py                 # State machine helpers
└── workspace.py             # Workspace resolver

schemas/
├── deploy-bundle-manifest.schema.json
├── deploy-profile.schema.json
└── initialization-contract.schema.json

topology-tools/plugins/validators/
└── initialization_contract_validator.py

tests/orchestration/
├── test_adapters.py
├── test_bundle.py
├── test_bundle_workflow.py
├── test_deploy_logging.py
├── test_environment.py
├── test_init_node.py
├── test_profile.py
├── test_runner.py
└── test_state.py
```
