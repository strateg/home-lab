# ADR 0081 Analysis: Framework Runtime Artifact and 1:N Project Repository Model

- Date: 2026-03-29
- Status: Complete
- ADR Status: Accepted
- Execution Plan: `adr/plan/0081-framework-artifact-first-execution-plan.md` (Active)

---

## 1. Executive Summary

ADR 0081 is **architecturally complete and substantially implemented** at the code level.
All 31 required components (scripts, modules, manifests, tests) exist and are functional.
The remaining work is **operational**: fixing a baseline blocker (P0) and executing the
phased rollout (P1–P5).

| Area | Status |
|------|--------|
| Framework artifact build tool | ✅ Complete |
| Distribution manifest (framework.yaml) | ✅ Complete — 8 inclusions, 32+ exclusions |
| Lock generation/verification | ✅ Complete — all error codes implemented |
| TRE runtime modules (11 modules) | ✅ Complete |
| TRE entry points (5 scripts) | ✅ Complete |
| Project bootstrap tools (4 scripts) | ✅ Complete |
| Development-only scripts (12+ scripts) | ✅ Complete |
| Dual-root path resolution | ✅ Complete — monorepo + standalone |
| Test coverage | ✅ 12 dedicated test files |
| Execution plan | ✅ Active — P0–P5 with dependency chain |
| Script register | ✅ Normative — TOPOLOGY-TOOLS-SCRIPT-REGISTER.md |
| **Baseline gates (P0)** | ❌ **Red — E7824 integrity drift** |
| Project plugin runtime enforcement | ⚠️ Contractual, not yet runtime-enforced |
| Package trust verification (§4.3) | ⚠️ Placeholder — phased by design |

---

## 2. Gap Analysis by ADR Section

### §1 — Repository Roles

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Framework source repo is single source of truth | ✅ | This repo layout |
| Co-located test project (`projects/home-lab/`) | ✅ | project.yaml, instances/ |
| Dev-only assets never in artifact | ✅ | framework.yaml exclusions + test_framework_distribution_boundary.py |

### §2 — Framework Runtime Artifact Contract

| Requirement | Status | Evidence |
|-------------|--------|----------|
| §2.1 Artifact includes class/object modules | ✅ | framework.yaml distribution.include |
| §2.1 Artifact includes topology-tools runtime | ✅ | framework.yaml distribution.include |
| §2.1 framework.yaml manifest in artifact | ✅ | First inclusion entry |
| §2.1 module-index.yaml in artifact | ✅ | Explicit inclusion + test |
| §2.2 Tests excluded | ✅ | exclude_globs: tests/**, acceptance-testing/** |
| §2.2 ADRs excluded | ✅ | exclude_globs: adr/** |
| §2.2 Dev docs excluded | ✅ | exclude_globs: docs/** |
| §2.2 Projects excluded | ✅ | exclude_globs: projects/** |
| §2.2 Archive excluded | ✅ | exclude_globs: archive/** |
| §2.2 Dev tooling excluded | ✅ | Taskfile, pyproject.toml, scripts/** |
| §2.2 AI config excluded | ✅ | .claude/**, .codex/**, AGENTS.md, CLAUDE.md |
| §2.2 IDE/CI excluded | ✅ | .github/**, .idea/**, .pre-commit-config.yaml |
| §2.2 Generated outputs excluded | ✅ | generated/**, build/**, dist/** |
| §2.2 Bytecode excluded | ✅ | **/__pycache__/**, *.pyc, *.pyo |
| §2.3 TRE scripts identified | ✅ | TOPOLOGY-TOOLS-SCRIPT-REGISTER.md |
| §2.3 Dev-only scripts in utils/ | ✅ | utils/ excluded via topology-tools/utils/** |
| Build tool produces artifact | ✅ | build-framework-distribution.py (ZIP+TAR.GZ+checksums) |
| Artifact content contract tests | ✅ | test_framework_distribution_boundary.py |

### §3 — Project Repository Contract

| Requirement | Status | Evidence |
|-------------|--------|----------|
| §3.1 Project layout defined | ✅ | ADR normative, bootstrap tools produce it |
| §3.2 Self-sufficiency principle | ✅ | Dual-root path resolution in compile-topology.py |
| §3.3 Project plugin root (6 families) | ⚠️ **Contractual only** | plugin_manifest_discovery.py has project_plugins_root param but no runtime validation of family affinity |
| §3.4 Plugin discovery 5-level chain | ⚠️ **Partial** | project_plugins_root supported in discovery; integration tests TBD |
| §3.5 Monorepo/standalone path resolution | ✅ | resolve_topology_path(), default_framework_manifest_path() |
| §3.6 TRE compatibility both modes | ⚠️ **Not tested E2E** | Scripts support it; rehearsal test (P2.5) not yet done |

### §4 — Dependency and Trust Contract

| Requirement | Status | Evidence |
|-------------|--------|----------|
| §4.1 Lock contract schema | ✅ | framework.lock.yaml matches spec |
| §4.2 E7822 lock missing | ✅ | verify-framework-lock.py |
| §4.2 E7823 revision mismatch | ✅ | verify-framework-lock.py |
| §4.2 E7824 integrity mismatch | ✅ (code), ❌ (baseline) | **P0 blocker: current lock is stale** |
| §4.2 E7811 version compat | ✅ | framework_lock.py semver checks |
| §4.2 E7812 schema compat | ✅ | framework_lock.py range checks |
| §4.3 E7825 signature validation | ⚠️ **Placeholder** | Phased: P3 workstream |
| §4.3 E7826 provenance attestation | ⚠️ **Placeholder** | Phased: P3 workstream |
| §4.3 E7828 SBOM check | ⚠️ **Placeholder** | Phased: P3 workstream |

### §5 — Consumption Modes

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Package artifact (primary) | ✅ | build-framework-distribution.py |
| Git submodule (secondary) | ✅ | Legacy mode, operational |
| Local path (dev-only) | ✅ | Default monorepo mode |
| §5.1 Artifact-first as canonical | ⚠️ **Not yet enforced** | Docs updated, but submodule still usable |

---

## 3. Execution Plan Assessment

The existing plan at `adr/plan/0081-framework-artifact-first-execution-plan.md` is
**well-structured** with 7 workstreams (P0–P5 including P2.5) in strict dependency order.

### Assessment per Workstream

| Workstream | Scope | Readiness | Risk |
|------------|-------|-----------|------|
| **P0: Baseline Recovery** | Lock refresh + green gates | **Ready to execute** — single command + commit | Low: mechanical task |
| **P1: Artifact Boundary** | Verify distribution spec + content tests | **Ready** — framework.yaml already correct; tests exist | Low: validation only |
| **P2: Project Plugins** | Runtime project plugin discovery | **Design ready** — contract in ADR, discovery API has param | Medium: new runtime code needed |
| **P2.5: TRE Compatibility** | Monorepo↔standalone equivalence | **Needs E2E rehearsal test** | Medium: first real standalone test |
| **P3: Package Trust** | Signature/provenance/SBOM | **Placeholder → real** | High: crypto infrastructure needed |
| **P4: Split Rehearsal** | Full artifact→project→compile flow | **Tools exist** — wiring needed | Medium: integration complexity |
| **P5: Cutover** | Docs, Phase 13 approval | **Blocked on all above** | Low: documentation + ceremony |

### Plan Strengths

1. **Clear dependency chain** — no ambiguity on what unblocks what.
2. **Gate commands defined** — each workstream has verifiable exit criteria.
3. **Definition of Done** per workstream — measurable outcomes.
4. **Risk/mitigation table** — key risks identified with responses.

### Plan Gaps Identified

1. **No time/effort estimates** — workstreams vary from 1h (P0) to multi-day (P3).
2. **P2 lacks detailed subtasks** — "implement project plugin discovery" is broad;
   needs breakdown into API changes, manifest loading, family validation, tests.
3. **P3 lacks technology choices** — which signing mechanism? cosign? GPG? Sigstore?
   This choice affects all downstream trust verification.
4. **P4 assumes deterministic output comparison** — but generated artifacts may contain
   timestamps or paths that differ between monorepo and standalone. Normalization needed.
5. **No parallel work identified** — P1 and P2 have no code dependency on each other;
   only the gate sequence is linear. P1 verification and P2 design could overlap.
6. **Missing: module-index.yaml completeness validation** — ADR 0082 analysis identified
   this as a gap; it naturally fits in P1.

---

## 4. Recommendations

### Immediate (P0)

**Priority: Critical — unblocks everything.**

Execute lock refresh and commit:

```powershell
task framework:lock-refresh
task framework:strict
task validate:v5-passthrough
```

This is a single-session task. Once green, commit the updated `framework.lock.yaml`.

### Short-Term (P1 + P2 overlap)

**Recommendation: Run P1 validation and P2 design in parallel.**

P1 is a verification workstream — the distribution spec is already correct. Running
`task framework:release-build` and inspecting the artifact is sufficient.

Meanwhile, P2 design can proceed: define the project plugin manifest schema, plan
the `plugin_manifest_discovery.py` extension, and write test specifications.

**Add to P1:** module-index.yaml completeness validation (from ADR 0082 analysis):
- CI test: all `plugins.yaml` files on disk are referenced in index
- CI test: all index entries point to existing files

### Medium-Term (P2.5 + P3)

**P2.5** is the first real proof that 1:N works. Recommendation:

1. Build artifact from current repo
2. Bootstrap a test project in `build/project-bootstrap/`
3. Run strict verify + compile in isolation
4. Compare generated outputs

**P3** needs a technology decision before implementation:
- **Recommended**: Start with content-hash integrity (already implemented)
- **Defer** crypto signing to when package distribution is operational
- Document the deferral as a Phase 13+ gate

### Long-Term (P4 + P5)

**P4 Split Rehearsal** should be automated in CI:
- GitHub Actions workflow that runs the full artifact→project→compile→generate flow
- Triggered on framework changes (topology/, topology-tools/)
- Produces machine-readable summary

**P5 Cutover** prerequisites:
- All P0–P4 gates green
- At least one successful artifact-first project bootstrap
- Documentation updated (README, runbooks)

---

## 5. Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|------------|
| R1 | P0 baseline stays red | Low | **Critical** — blocks all | Mandatory first action, mechanical fix |
| R2 | Distribution spec drift from ADR | Low | High | Content contract tests (P1) |
| R3 | Project plugin discovery breaks existing pipeline | Medium | High | Additive-only extension (P2) |
| R4 | Standalone mode produces different artifacts | Medium | High | Normalization + comparison (P4) |
| R5 | Crypto trust infrastructure delays cutover | High | Medium | Phase incrementally (P3 deferral) |
| R6 | module-index.yaml gets out of sync | Medium | Medium | Auto-generation + CI completeness check |
| R7 | Bootstrap tool generates stale templates | Low | Medium | Rehearsal test catches drift (P2.5) |

---

## 6. Verification Matrix

### Existing Tests (12 files)

| Test File | Covers |
|-----------|--------|
| test_framework_distribution_boundary.py | §2.1/§2.2 artifact contents |
| test_build_framework_distribution.py | Artifact build pipeline |
| test_framework_lock.py | §4.1 lock generation/verification |
| test_compile_framework_lock_integration.py | Lock + compile integration |
| test_framework_rollback_rehearsal.py | Lock rollback scenarios |
| test_framework_compatibility_matrix.py | Version/schema compatibility |
| test_bootstrap_project_repo.py | Project bootstrap from artifact |
| test_bootstrap_framework_repo.py | Framework repo bootstrap |
| test_extract_framework_history.py | Git history extraction |
| test_extract_framework_worktree.py | Worktree export |
| test_artifact_manifest_generator.py | Artifact manifest generation |
| test_model_lock_*.py (2) | Model lock validation |

### Tests Needed (NEW)

| Test | Workstream | Priority |
|------|-----------|----------|
| module-index.yaml bidirectional completeness | P1 | High |
| Project plugin manifest discovery | P2 | High |
| Project plugin family affinity validation | P2 | High |
| Project plugin ID conflict detection | P2 | High |
| Standalone compile equivalence | P2.5 | High |
| End-to-end artifact→project→compile rehearsal | P4 | High |
| Crypto signature verification (package mode) | P3 | Medium |
| Provenance attestation check | P3 | Medium |
| SBOM presence validation | P3 | Medium |

---

## 7. Summary

ADR 0081 is a mature, well-implemented architecture decision. The gap between
"accepted" and "fully operational" is primarily:

1. **P0 blocker** — mechanical lock refresh (hours, not days)
2. **Project plugin runtime** — API exists but needs integration (P2)
3. **Standalone rehearsal** — tools exist but need E2E wiring (P2.5/P4)
4. **Crypto trust** — intentionally deferred per §4.3 phasing

The execution plan is sound. Recommended adjustments:
- Parallel P1 verification + P2 design
- Add module-index.yaml completeness to P1
- Defer P3 crypto decisions until package distribution is operational
- Automate P4 rehearsal in CI for ongoing confidence
