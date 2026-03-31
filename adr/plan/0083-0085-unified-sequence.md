# ADR 0083/0084/0085: Unified Implementation Sequence

**Date:** 2026-03-31
**Status:** Active (ADR 0085/0084 core completed; deferred backend and ADR 0083 decisions remain)
**Purpose:** Keep one execution sequence across deploy-domain ADRs.

---

## Priority Order (Confirmed)

```
ADR 0085 (bundle contract) -> ADR 0084 (deploy plane) -> ADR 0083 (optional init)
     ↓                            ↓                         ↓
  PRIMARY                      SECONDARY                 DEFERRED
```

---

## Current State Summary

| ADR | Status | Completed Scope | Next Scope |
|-----|--------|-----------------|------------|
| 0085 | Accepted | Phases 0/0a/1/2 + active Phase 3 migration + assemble-plugin integration | Backend follow-ups + ADR0083 consumers |
| 0084 | Accepted | Runner plane + bundle-based active deploy flow + DockerRunner/RemoteRunner core + Docker toolchain image + backend CI lane + remote setup docs | Remote backend reliability follow-up |
| 0083 | Proposed (Scaffold started) | `init-node` CLI/state/status + adapter/state-machine scaffold + environment precheck + Phase 1 schema/validator baseline + MikroTik/Proxmox/OrangePi contract declarations + contract-aware bootstrap projection routing + Proxmox minimal bootstrap templates/generator update + tests | Complete concrete adapters/handover flow |

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

### Bucket A: Deferred Runner Backends (ADR 0084)

| Item | Trigger | Status |
|------|---------|--------|
| `DockerRunner` CI image/workflow hardening | CI reproducibility requirement | Completed |
| Backend CI/reliability validation | With implementation | Pending |

### Bucket B: ADR 0083 Decision

| Item | Dependency | Status |
|------|------------|--------|
| Complete `init-node.py` adapters + state transitions + handover checks | ADR 0085/0084 foundation now available | In progress (scaffold baseline merged) |

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

| Scope | Tests | Category |
|-------|-------|----------|
| Runner | T-R01..T-R12 | Unit |
| Profile | T-P01..T-P06 | Unit/Integration |
| Bundle | T-B01..T-B10 | Unit/Integration |
| Bundle workflow | T-W01..T-W05 + bundle-mode path tests | Integration/Unit |
| ADR 0083 | T-Oxx (future) | Deferred |

---

## Success Criteria Snapshot

1. ADR 0085 core flow is bundle-based and tested.
2. ADR 0084 runner plane is active for bundle staging/execution.
3. Documentation reflects bundle-first operator workflow.
4. ADR 0083 can start from existing bundle + runner contract without redesign.
