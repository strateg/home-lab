# ADR 0085: Gap Analysis

## Goal

Track remaining gap between implemented deploy-bundle model and full target contract.

---

## Current State

| Aspect | Status | Notes |
|--------|--------|-------|
| Deploy bundle concept | ✅ Implemented | ADR 0085 contract is active in tooling |
| Bundle assembly | ✅ Implemented | `scripts/orchestration/deploy/bundle.py` + schema |
| Deploy profile | ✅ Implemented | Schema + loader + project example |
| Runner workspace-awareness | ✅ Implemented | `runner.py` has stage/run/capabilities/cleanup |
| Bundle consumption | ✅ Implemented for active flow | `service_chain_evidence.py` executes via explicit `--bundle` |
| Secret join point | ✅ Implemented | Optional injection at bundle assembly (`--inject-secrets`) |
| `generated/` remains inspectable | ✅ Preserved | Bundle execution uses `artifacts/generated` copy |

---

## Target State

| Aspect | Target | Implementation Direction |
|--------|--------|--------------------------|
| Deploy bundle | Immutable execution input | `.work/deploy/bundles/<bundle_id>/` |
| Deploy profile | Project-scoped config | `projects/<project>/deploy/deploy-profile.yaml` |
| Bundle assembly | Stable create/inspect/delete lifecycle | `deploy.bundle` API and task wrappers |
| Runner contract | Workspace-aware | Stage bundle, execute, report capabilities, cleanup |
| Entry points | Bundle-ID based | `--bundle <bundle_id>` parameter |

---

## Remaining Gap Items

### G1: ADR 0083 consumer entry points are still pending

**Current:** `service_chain_evidence.py` is migrated to bundle-ID based execution.

**Target:** Future `init-node.py` and related ADR 0083 entry points consume the same `--bundle` model.

**Action:** Complete when ADR 0083 implementation is resumed.

### G2: Runner backend reliability hardening remains

**Current:** `DockerRunner` and `RemoteLinuxRunner` are implemented and covered by runner unit tests.

**Target:** Keep backend behavior reliable across CI and operational environments.

**Action:** Continue hardening with backend-specific CI checks and optional remote integration smoke on dedicated control-node infrastructure.

---

## Implementation Progress

| Component | Status | Notes |
|-----------|--------|-------|
| Runner workspace contract | ✅ Done | `runner.py` implements stage/run/capabilities/cleanup |
| Native + WSL runners | ✅ Done | Functional implementations |
| Docker runner | ✅ Done | Implemented in `runner.py` + toolchain image + CI smoke lane |
| Remote runner | ✅ Done | Implemented in `runner.py` + expanded contract tests |
| Deploy profile schema + loader | ✅ Done | `deploy-profile.schema.json` + `profile.py` + tests |
| Bundle schema + CLI/API | ✅ Done | `deploy-bundle-manifest.schema.json` + `bundle.py` |
| Assemble-stage bundle plugin | ✅ Done | `base.assembler.deploy_bundle` |
| Bundle-ID entry point migration | ✅ Done (active flow) | `service_chain_evidence.py --bundle` |
| Bundle lifecycle docs | ✅ Done | `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md` |
| Workflow tests | ✅ Done | bundle/workflow/service-chain tests pass |

---

## State File Location (Unified)

**Canonical location:** `.work/deploy-state/<project>/`

| Root | Purpose |
|------|---------|
| `.work/deploy/bundles/<bundle_id>/` | Immutable deploy bundles |
| `.work/deploy-state/<project>/nodes/` | Mutable initialization state |
| `.work/deploy-state/<project>/logs/` | Audit logs (JSONL) |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Bundle/workspace mismatch across deferred backends | Medium | High | Keep shared runner contract and tests as backend gate |
| Secret leak during bundle creation | Low | Critical | SOPS-only injection path and checksum verification |
| Bundle retention bloat | Medium | Low | Use retention policy from deploy profile and cleanup commands |
| ADR 0083 drift from bundle contract | Medium | Medium | Require `--bundle` in ADR 0083 entry-point design |

---

## Acceptance Signals

ADR 0085 is successfully adopted when:

1. [x] Runner contract is workspace-aware (stage, run, capabilities, cleanup)
2. [x] State file location unified to `.work/deploy-state/<project>/`
3. [x] Runner tests pass (T-R01..T-R12)
4. [x] Deploy profile schema exists and is validated
5. [x] Bundle assembly creates immutable bundles
6. [x] Active deploy entry points consume `--bundle <bundle_id>`
7. [x] Bundle lifecycle is documented
8. [x] Secrets join only at bundle assembly (not in generated/)
