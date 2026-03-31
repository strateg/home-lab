# ADR 0085: Gap Analysis

## Goal

Define the gap between current artifact-execution model and the target deploy bundle contract.

---

## Current State

| Aspect | Status | Notes |
|--------|--------|-------|
| Deploy bundle concept | ✅ Defined | ADR 0085 defines bundle as canonical execution input |
| Bundle assembly | ❌ Not implemented | No `base.assembler.deploy_bundle` plugin |
| Deploy profile | ❌ Not implemented | No schema, no examples |
| Runner workspace-awareness | ✅ Implemented | `runner.py` has `stage_bundle()`, `cleanup_workspace()`, `capabilities()` |
| Bundle consumption | ⚠️ Partial | `service_chain_evidence.py` uses `stage_bundle(repo_root)` as transitional |
| Secret join point | ❌ Not implemented | Bundle assembly should be the join point |
| `generated/` remains inspectable | ✅ Preserved | No secrets in generated artifacts |

---

## Target State

| Aspect | Target | Implementation Direction |
|--------|--------|--------------------------|
| Deploy bundle | Immutable execution input | `.work/deploy/bundles/<bundle_id>/` |
| Deploy profile | Project-scoped config | `projects/<project>/deploy/deploy-profile.yaml` |
| Bundle assembly | Assemble stage plugin | `base.assembler.deploy_bundle` |
| Runner contract | Workspace-aware | Stage bundle, execute, report capabilities, cleanup |
| Entry points | Bundle-ID based | `--bundle <bundle_id>` parameter |

---

## Gap Items

### G1: Bundle assembly plugin missing

**Current:** No mechanism to create deploy bundles from generated artifacts.

**Target:** `base.assembler.deploy_bundle` plugin creates immutable bundles.

**Action:** Implement assembler plugin with:
- Manifest generation from generated artifacts
- Secret injection from SOPS
- Bundle hash/provenance metadata
- Artifact packaging per node

### G2: Deploy profile schema missing

**Current:** No formal deploy profile structure.

**Target:** Project-scoped YAML with backend selection, timeouts, logical input resolution.

**Action:** Create schema and example.

### G3: Bundle-ID based entry points not implemented

**Current:** Deploy tooling uses repo paths or transitional `stage_bundle(repo_root)`.

**Target:** `--bundle <bundle_id>` as primary execution input.

**Action:** Update deploy entry points to require explicit bundle selection.

### G4: Bundle lifecycle not documented

**Current:** No bundle retention, cleanup, or versioning policy.

**Target:** Clear lifecycle: create → use → archive or delete.

**Action:** Document bundle lifecycle in operator guide.

---

## Implementation Progress

| Component | Status | Notes |
|-----------|--------|-------|
| Runner workspace contract | ✅ Done | `runner.py` fully implements stage/run/capabilities/cleanup |
| Native + WSL runners | ✅ Done | Functional implementations |
| Docker runner | 🔜 Stub | Phase 0b |
| Remote runner | 🔜 Stub | Phase 0c |
| Bundle assembly plugin | ❌ Pending | Core ADR 0085 deliverable |
| Deploy profile schema | ❌ Pending | Needed for multi-backend support |
| Bundle-ID entry points | ❌ Pending | Requires bundle assembly first |

---

## Acceptance Signals

ADR 0085 is successfully adopted when:

1. [x] Runner contract is workspace-aware (stage, run, capabilities, cleanup)
2. [ ] Bundle assembly plugin creates immutable bundles
3. [ ] Deploy profile schema exists and is validated
4. [ ] Deploy entry points consume `--bundle <bundle_id>`
5. [ ] Bundle lifecycle is documented
6. [ ] Secrets join only at bundle assembly (not in generated/)
