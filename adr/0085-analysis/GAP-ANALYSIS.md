# ADR 0085: Gap Analysis

## Goal

Define the gap between the current deploy-time filesystem assumptions and the target deploy bundle + runner workspace contract.

---

## Current State

| Aspect | Status | Issue |
|--------|--------|-------|
| Generated artifacts | Available | Used both for inspection and implicitly for execution |
| Runtime execution roots | Ad hoc | `.work/native/...` is local-path-centric |
| Deploy profile | ❌ Missing | No project-scoped operator/backend settings contract |
| Deploy bundle | ❌ Missing | No immutable execution input boundary |
| Runner abstraction | ⚠️ Partial | `run()` exists, workspace staging contract does not |
| Capability negotiation | ❌ Missing | Backends do not report capabilities |
| Remote/container backends | 🔜 Planned | No bundle/workspace contract to support them |
| Mutable state root | ⚠️ Ambiguous | ADR 0083 uses `.work/native/bootstrap/`; no deploy-state contract defined |
| Secret join point | ⚠️ Informal | No formal assembly step between generated/ and execution |

## Target State

| Aspect | Target |
|--------|--------|
| Execution input | Immutable deploy bundle in `.work/deploy/bundles/<bundle_id>/` |
| Backend settings | Project-scoped deploy profile (`projects/<project>/deploy/deploy-profile.yaml`) |
| Runtime state | Mutable deploy-state root (`.work/deploy-state/<project>/`) |
| Runner model | Workspace-aware, capability-reporting |
| Secret materialization | Bundle assembly is the sole secret join point |

---

## Gap Items

### G1: No canonical deploy bundle layout

**Current:** Generated artifacts in `generated/<project>/` are used directly by deploy tooling. No intermediate bundle concept exists.

**Target:** Immutable deploy bundle with `manifest.yaml`, `artifacts/<node_id>/`, `metadata.yaml` at `.work/deploy/bundles/<bundle_id>/`.

**Action Required:**
1. Define bundle directory layout in `docs/contracts/DEPLOY-BUNDLE.md`
2. Create JSON Schemas for `manifest.yaml` and `metadata.yaml`
3. Implement bundle assembly entry point
4. Make `bundle_id` deterministic for given topology + secret inputs

### G2: No project-scoped deploy profile contract

**Current:** Operator settings (runner backend, WSL distro, toolchain paths, staging policy) are either hard-coded or implicit in script arguments.

**Target:** Declarative `deploy-profile.yaml` with JSON Schema validation.

**Action Required:**
1. Create `schemas/deploy-profile.schema.json`
2. Create sample profile at `projects/home-lab/deploy/deploy-profile.yaml`
3. Update deploy tooling to load and validate profile before execution

### G3: No workspace staging contract in `DeployRunner`

**Current:** `DeployRunner.run()` is process-centric. Bundles are not staged into backend-specific workspaces.

**Target:** Runner contract includes `stage_bundle()`, `run()` (in workspace), `capabilities()`, `cleanup_workspace()`.

**Action Required:** Co-owned with ADR 0084 Phase 0a. Define contract requirements here; implement in ADR 0084.

### G4: No explicit capability negotiation for backends

**Current:** If a backend lacks a required capability (e.g., interactive confirmation, host-network access), failure is silent or confusing.

**Target:** `capabilities()` returns a feature map; deploy tooling validates required capabilities before execution.

**Action Required:**
1. Define capability keys (e.g., `interactive`, `host_network`, `path_translation`, `persistent_workspace`)
2. Add capability validation to deploy entry points

### G5: ADR 0083 wording still reflects local-path execution assumptions

**Current:** ADR 0083 `STATE-MODEL.md` uses `.work/native/bootstrap/INITIALIZATION-STATE.yaml` and edge cases reference `.work/native/` as the assembled artifacts root.

**Target:** All state and runtime data under `.work/deploy-state/<project>/`. No architectural reference to `.work/native/`.

**Action Required:**
1. Update `adr/0083-analysis/STATE-MODEL.md` to use `.work/deploy-state/<project>/`
2. Update all edge-case descriptions to reference deploy bundle and deploy-state roots
3. Verify all ADR 0083 analysis docs are terminologically consistent

### G6: No formal assembly step between generated/ and execution

**Current:** There is no code that combines generated templates with decrypted secrets into an immutable bundle. ADR 0083 describes `base.assembler.bootstrap_secrets` conceptually, but it depends on the bundle contract defined here.

**Target:** `assemble-bundle.py` (or pipeline-integrated assembly step) produces deploy bundles with secret injection.

**Action Required:**
1. Implement assembly entry point (Phase 2 of IMPLEMENTATION-PLAN)
2. Enforce immutability of assembled bundles
3. Validate generated/ remains secret-free after assembly

### G7: Mutable state root ambiguity

**Current:** Multiple conventions coexist:
- ADR 0083 STATE-MODEL: `.work/native/bootstrap/INITIALIZATION-STATE.yaml`
- ADR 0085 D6: `.work/deploy-state/<project>/nodes/<node_id>.yaml`
- ADR 0085 D6: `.work/deploy-state/<project>/logs/<run_id>.jsonl`

**Target:** Unified mutable deploy-state root: `.work/deploy-state/<project>/`. No architectural use of `.work/native/bootstrap/` for state management.

**Action Required:**
1. Document deploy-state layout in `docs/contracts/DEPLOY-STATE.md`
2. Update ADR 0083 STATE-MODEL.md to align
3. Ensure `.gitignore` covers `.work/deploy-state/`

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Bundle model adds complexity | Medium | Medium | Keep bundle layout minimal and deterministic |
| Backend staging semantics diverge | Medium | High | Define runner contract before implementing backends |
| Secret sprawl across roots | Low | High | Make bundle assembly the only secret join point |
| Adoption stalls due to abstract definitions | Medium | Medium | Create concrete sample bundle early (Phase 1) |
| ADR 0083/0084 drift from 0085 definitions | Medium | High | Harmonize all three ADRs in the same commit |

---

## Implementation Progress

| Component | Status | Notes |
|-----------|--------|-------|
| Deploy bundle layout | ❌ Not started | Phase 1 |
| Bundle schemas | ❌ Not started | Phase 1 |
| Deploy profile schema | ❌ Not started | Phase 1 |
| Deploy-state root layout | ❌ Not started | Phase 1 |
| Bundle assembly | ❌ Not started | Phase 2 |
| Runner evolution | 🔄 In progress | ADR 0084 Phase 0a |
| Deploy tooling integration | ❌ Not started | Phase 4 |
| ADR 0083 alignment | 🔄 In progress | STATE-MODEL.md update |
| ADR 0084 alignment | ✅ Done | Wording aligned |

---

## Acceptance Signals

ADR 0085 is successfully adopted when:

1. [ ] Deploy bundle layout is documented and schema-validated
2. [ ] Deploy profile contract is documented and schema-validated
3. [ ] Mutable deploy-state root is documented
4. [ ] Bundle assembly produces immutable bundles from generated + secrets
5. [ ] Runner contract is workspace-aware (co-owned with ADR 0084)
6. [ ] Deploy entry points consume explicit `--bundle <bundle_id>`
7. [ ] All three ADRs (0083, 0084, 0085) are terminologically consistent
8. [ ] No active deploy code references `.work/native/` as architectural contract
