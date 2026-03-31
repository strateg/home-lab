# ADR 0083/0084/0085: Unified Implementation Sequence

**Date:** 2026-03-31
**Status:** Active
**Purpose:** Define the concrete next steps for deploy-domain implementation.

---

## Priority Order (Confirmed)

```
ADR 0085 (bundle contract) → ADR 0084 (deploy plane) → ADR 0083 (optional init)
     ↓                            ↓                         ↓
  PRIMARY                      SECONDARY                 DEFERRED
```

---

## Current State Summary

| ADR | Status | Phase Complete | Next Phase |
|-----|--------|----------------|------------|
| 0085 | Accepted | Phase 0a (Runner + tests) | **Phase 1 (Deploy Profile)** |
| 0084 | Accepted | Phase 0a (Runner + tests) | Phase 1 integration (shared with 0085) |
| 0083 | Proposed (Deferred) | - | Awaiting 0085/0084 |

---

## Immediate Next Steps (Phase 1)

### Goal: Define deploy profile schema and loader

**Priority:** HIGH - Profile contract blocks bundle assembly

| ID | Task | Output | Owner |
|----|------|--------|-------|
| 1.1 | Create schema | `schemas/deploy-profile.schema.json` | - |
| 1.2 | Create example | `projects/home-lab/deploy/deploy-profile.yaml` | - |
| 1.3 | Implement loader | `scripts/orchestration/deploy/profile.py` | - |
| 1.4 | Integrate with runner | `get_runner()` reads profile | - |
| 1.5 | Add tests | T-P01..T-P06 | - |

**Gate:** Profile schema validates and tests pass.

---

## Phase 1: Deploy Profile

**Dependency:** Phase 0a complete

| ID | Task | Output |
|----|------|--------|
| 1.1 | Create schema | `schemas/deploy-profile.schema.json` |
| 1.2 | Create example | `projects/home-lab/deploy/deploy-profile.yaml` |
| 1.3 | Implement loader | `scripts/orchestration/deploy/profile.py` |
| 1.4 | Integrate with runner | `get_runner()` reads profile |
| 1.5 | Add tests | T-P01..T-P06 |

**Gate:** Profile schema validated, tests pass.

---

## Phase 2: Bundle Assembly

**Dependency:** Phase 1 complete

| ID | Task | Output |
|----|------|--------|
| 2.1 | Create schema | `schemas/deploy-bundle-manifest.schema.json` |
| 2.2 | Implement CLI | `scripts/orchestration/deploy/bundle.py` |
| 2.3 | Bundle creation | `.work/deploy/bundles/<id>/` |
| 2.4 | Secret injection | SOPS decryption into bundle |
| 2.5 | Add tests | T-B01..T-B10 |

**Gate:** Bundle assembly creates valid immutable bundles.

---

## Phase 3: Entry Point Migration

**Dependency:** Phase 2 complete

| ID | Task | Output |
|----|------|--------|
| 3.1 | Update evidence tool | `--bundle` parameter |
| 3.2 | Create operator guide | `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md` |
| 3.3 | Update CLAUDE.md | Dev/Deploy plane documentation |
| 3.4 | Add tests | T-W01..T-W05 |

**Gate:** All deploy entry points use bundle-ID.

---

## ADR 0083 Enablement (Optional)

**Dependency:** ADR 0085 Phase 2 complete

After Phase 2, ADR 0083 can proceed with:
- `init-node.py --bundle <bundle_id>` execution model
- State files in `.work/deploy-state/<project>/nodes/`
- Immutable bundle as execution input

**Decision point:** Evaluate whether unified node initialization is still needed after deploy-domain foundation is complete.

---

## State File Locations (Unified)

All ADRs use these canonical locations:

| Path | Purpose | ADR |
|------|---------|-----|
| `.work/deploy/bundles/<bundle_id>/` | Immutable deploy bundles | 0085 |
| `.work/deploy-state/<project>/nodes/` | Initialization state | 0083 |
| `.work/deploy-state/<project>/logs/` | Audit logs | 0083 |

**Superseded:** `.work/native/bootstrap/` (removed from all docs)

---

## Test Matrix Summary

| Phase | Tests | Category |
|-------|-------|----------|
| 0a | T-R01..T-R12 | Runner unit tests |
| 1 | T-P01..T-P06 | Profile unit tests |
| 2 | T-B01..T-B10 | Bundle unit/integration tests |
| 3 | T-W01..T-W05 | Workflow integration tests |
| 0083 | T-O01..T-O18 + more | Orchestrator tests (when enabled) |

**Total:** 33 tests for ADR 0085 + 82+ for ADR 0083

---

## Success Criteria

1. **ADR 0085 Accepted:** Runner tests pass, bundle assembly works
2. **ADR 0084 Accepted:** Runner contract complete (shared with 0085)
3. **ADR 0083 Decision:** Evaluate after 0085 Phase 2 is complete
4. **Documentation:** Operator guide exists, CLAUDE.md updated
5. **Secret isolation:** Zero secrets in `generated/`
