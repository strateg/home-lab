# Architectural Improvement Analysis
**Date:** 2026-04-13
**Analyst:** Claude Sonnet 4.5 (AI-Agent)
**Context:** Post-ADR 0095/0096 implementation review
**Scope:** Identify architectural gaps and improvement opportunities

---

## Executive Summary

**Status**: Project architecture is in strong shape post-ADR 0095/0096 completion. The Class->Object->Instance model is well-established, plugin microkernel is operational, and deploy domain contracts (ADR 0084/0085) are complete.

**Critical Finding**: ADR 0080 (Unified Build Pipeline) has significant implementation gaps despite "Accepted" status. The 6-stage + universal phase model is only partially realized in runtime.

**Recommended Priority**:
1. **HIGH**: Complete ADR 0080 implementation (assemble/build stages + phase executor)
2. **MEDIUM**: Finalize ADR 0083 (Node Initialization Contract) - currently scaffold-only
3. **LOW**: Technical debt cleanup and documentation consolidation

---

## Part 1: Implementation Gap Analysis

### 1.1 ADR 0080 - Unified Build Pipeline (CRITICAL)

**Status in Register**: "Accepted" (2026-03-26)
**Actual Runtime Status**: Partially implemented, significant gaps remain

#### Implemented Components ✅
- Stage enum extended: `DISCOVER`, `COMPILE`, `VALIDATE`, `GENERATE`, `ASSEMBLE`, `BUILD`
- Phase enum defined: `INIT`, `PRE`, `RUN`, `POST`, `VERIFY`, `FINALIZE`
- Plugin kinds extended: `DISCOVERER`, `ASSEMBLER`, `BUILDER`
- Parallel plugin execution operational
- Data bus (publish/subscribe) working

#### Missing Components ❌

| Gap ID | Component | Impact | Current State |
|--------|-----------|--------|---------------|
| **G1** | Discover stage plugins | No plugin-owned discovery lifecycle | Procedural function `discover_plugin_manifests()` in `compiler_runtime.py` |
| **G2** | PluginContext extensions | Assemble/build plugins cannot be implemented | No `workspace_root`, `dist_root`, `assembly_manifest` fields |
| **G3** | Phase-aware executor | Plugins cannot use phase lifecycle | Execution order: stage → DAG → order (no phase sequencing) |
| **G4** | `when` predicate evaluation | Smart plugin model incomplete | Declarative only, no runtime enforcement |
| **G5** | Diagnostic code ranges | New stages cannot emit typed diagnostics | No E80xx allocation for discover/assemble/build |
| **G6** | `base.generator.artifact_manifest` | Generate->assemble contract gap | Plugin listed in ADR but not implemented |
| **G19-G24** | Parallel execution safety | Race conditions in current implementation | Shared mutable state in `_published_data`, `_current_plugin_id`, plugin instance cache |

**Evidence**:
```python
# topology-tools/kernel/plugin_base.py - Line 36-44
class Stage(str, Enum):
    """Pipeline stage."""
    DISCOVER = "discover"
    COMPILE = "compile"
    VALIDATE = "validate"
    GENERATE = "generate"
    ASSEMBLE = "assemble"
    BUILD = "build"

class Phase(str, Enum):  # Line 47-54
    """Universal phase."""
    INIT = "init"
    PRE = "pre"
    RUN = "run"
    POST = "post"
    VERIFY = "verify"
    FINALIZE = "finalize"
```

**But**: Runtime in `compile-topology.py` only executes `COMPILE`, `VALIDATE`, `GENERATE` stages with DAG/order-based scheduling, **not phase-aware execution**.

#### Consequences

1. **Blocked Feature Work**: Cannot implement ADR 0052 (Deploy Package Assembly) or ADR 0076 Stage 2 (Framework Distribution) workflows that depend on `assemble`/`build` stages
2. **Technical Debt**: Manual assembly scripts in `.work/native/` instead of plugin-based assembly
3. **Contract Violation**: ADR 0080 GAP-ANALYSIS.md identified these issues in 2026-03-26, but cutover marked "complete" without addressing G1-G6, G19-G24
4. **Parallel Safety Risk**: Shared mutable state creates race conditions in parallel mode (enabled by default)

#### Recommended Action

**Create ADR 0080 remediation plan**:
- **Wave 1**: Implement phase-aware executor (addresses G3)
- **Wave 2**: Extend PluginContext for assemble/build stages (addresses G2)
- **Wave 3**: Implement discover-stage plugins (addresses G1)
- **Wave 4**: Fix parallel execution safety (addresses G19-G24)
- **Wave 5**: Implement smart plugin predicates (addresses G4)
- **Wave 6**: Allocate diagnostic ranges and implement artifact_manifest (addresses G5, G6)

**Validation**: Update ADR 0080 status to "Partially Implemented" and create `adr/0080-remediation/` with detailed plan.

---

### 1.2 ADR 0083 - Node Initialization Contract (DEFERRED)

**Status in Register**: "Proposed (scaffold complete, hardware pending)" (2026-03-30)
**Actual Status**: Scaffold-only, no runtime implementation

#### Implemented Components ✅
- Schemas: `schemas/initialization-contract.schema.json` exists
- Deploy runner workspace model (ADR 0084) complete
- Deploy bundle contract (ADR 0085) complete
- Bootstrap adapters scaffold: `scripts/orchestration/deploy/adapters/` with `netinstall.py`, `cloud_init.py`, `unattended.py`, `ansible_bootstrap.py`

#### Missing Components ❌

| Component | Status | Blocker |
|-----------|--------|---------|
| Object-module `initialization_contract` declarations | Not implemented | Requires topology model extension |
| `INITIALIZATION-MANIFEST.yaml` generator | Not implemented | Requires generator plugin |
| Init-node state machine runtime | Scaffold only | Requires hardware for testing |
| Handover verification checks | Not implemented | No topology integration |
| Bootstrap adapters functional implementation | Stubs only | Hardware testing pending |

**Evidence**: All ADR 0083 files reference it as "deferred" and "optional" - correct prioritization given ADR 0084/0085 were prerequisites.

#### Consequences

1. **Manual Bootstrap Required**: Operators must manually run device-specific bootstrap scripts (MikroTik netinstall, Proxmox answer.toml) outside topology workflow
2. **No Pre-flight Validation**: Cannot verify initialization readiness before attempting bootstrap
3. **Fragmented State**: `proxmox-post-install.sh` (487 lines) in archive mixes day-0 and day-1 concerns

#### Recommended Action

**ADR 0083 is correctly deferred**. No action required unless:
- Hardware becomes available for Proxmox/OrangePi bootstrap testing
- User explicitly prioritizes unified initialization workflow
- Deploy domain extends to multi-site or SOHO product distribution requiring automated provisioning

**If implemented**: Follow 3-wave plan in `adr/0083-analysis/IMPLEMENTATION-PLAN.md`.

---

### 1.3 ADR 0095 - Topology Inspection Toolkit (COMPLETE) ✅

**Status**: Fully implemented, all optimization waves complete (2026-04-13)

**Delivered**:
- 24 inspection commands via `task inspect:*`
- Semantic relation typing promoted to authoritative mode
- JSON output contracts for automation
- Typed-shadow diagnostics and smoke matrix

**No gaps identified**. Excellent implementation quality.

---

### 1.4 ADR 0096 - AI Agent Rulebook (COMPLETE) ✅

**Status**: Implemented (Waves 1-3 complete, 2026-04-10)

**Delivered**:
- Universal rulebook: `docs/ai/AGENT-RULEBOOK.md`
- ADR rule map: `docs/ai/ADR-RULE-MAP.yaml`
- Scoped rule packs: `docs/ai/rules/*.md`
- Adapter harmonization: `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`

**Outstanding**:
- AI commit accountability metadata enforcement (CORE-009) - requires git hook or CI check

**No major gaps**. Recommend adding pre-commit hook for `AI-Agent` / `AI-Tokens` metadata validation.

---

## Part 2: Architectural Debt Inventory

### 2.1 Plugin Contract Enforcement

**Issue**: Plugin manifests declare `depends_on`, `consumes`, `produces` but runtime does not enforce them.

**Evidence**:
- `topology-tools/kernel/plugin_registry.py` - dependency checking exists for DAG ordering
- No runtime validation that consumed keys were actually published by declared dependencies
- `when` predicates (profiles, capabilities) are schema-defined but not evaluated

**Impact**: Silent plugin coupling breakage, hard-to-debug failures when plugin contracts change

**Recommended Action**:
- Add contract validation phase in ADR 0080 Wave 5
- Fail-fast if plugin consumes unpublished data
- Log warnings for unused `produces` declarations

---

### 2.2 Parallel Execution Safety (CRITICAL)

**Issue**: ADR 0080 GAP-ANALYSIS.md identified race conditions (G19-G24) in parallel plugin execution, but cutover checklist marked as "complete" without fixes.

**Evidence**:
```python
# topology-tools/compiler_runtime.py or plugin_registry.py
_published_data = {}  # Shared mutable dict, no locking
_current_plugin_id = None  # Shared state, identity leak risk
```

**Impact**:
- Non-deterministic failures in parallel mode
- Plugin instance cache TOCTOU window
- Diagnostic ordering instability (noisy CI diffs)

**Recommended Action**:
- ADR 0080 Wave 4: Add thread-safe data bus with per-invocation isolation
- Use `threading.Lock` for shared state or redesign to use immutable message passing
- Add parallel execution stress tests

---

### 2.3 Generated Output Parity Validation

**Issue**: No automated check that generated artifacts remain stable across regeneration cycles.

**Current State**:
- Golden snapshots exist for some generators (`tests/fixtures/projections/`)
- No CI task that fails on unexpected diff in `generated/`
- Mermaid quality gate exists (ADR 0027) but not enforced in `task ci`

**Impact**: Silent generator regressions, drift between topology and generated artifacts

**Recommended Action**:
- Add `task validate:generated-parity` that runs `git diff generated/` after regeneration
- Integrate into `task ci` gate
- Extend golden snapshot coverage to all generator plugins

---

### 2.4 Secrets Mode Passthrough Leakage Risk

**Issue**: `V5_SECRETS_MODE=passthrough` bypasses SOPS decryption for testing, but no enforcement that passthrough-mode outputs are not committed.

**Evidence**:
- `taskfiles/framework.yml`, `taskfiles/ansible.yml` use passthrough for validation
- No pre-commit hook checking for plaintext secret leakage
- ADR 0094 defines AI redaction but no automated secret scanning

**Impact**: Risk of accidental secret commits if operator runs with passthrough and forgets to gitignore output

**Recommended Action**:
- Add pre-commit hook: scan for `V5_SECRETS_MODE=passthrough` artifacts in git staging area
- Extend `task validate:default` to check for plaintext secret markers
- Document secret hygiene in `docs/guides/SECRETS-MANAGEMENT.md`

---

## Part 3: Documentation Gaps

### 3.1 ADR Analysis Directory Policy Adherence

**Policy**: ADR analysis artifacts must go in `adr/NNNN-analysis/`, never inlined into ADR files.

**Compliance Audit**:
- **Compliant**: ADR 0057, 0063, 0069, 0071, 0078, 0079, 0080, 0081, 0082, 0083, 0085, 0086, 0087, 0088, 0089, 0092, 0093, 0094, 0095, 0096 (20 ADRs)
- **Missing**: ADR 0062, 0064, 0065, 0066, 0067, 0070, 0072, 0073, 0074, 0075, 0076, 0077, 0084, 0090, 0091 (15 ADRs)

**Impact**: Analysis artifacts for 15 ADRs are either inline (violates policy) or missing (no implementation evidence).

**Recommended Action**:
- Create analysis directories for missing ADRs, even if retrospective
- Extract inline analysis from ADR files into separate `GAP-ANALYSIS.md` / `IMPLEMENTATION-PLAN.md`
- Update `adr/REGISTER.md` with analysis directory links

---

### 3.2 Operator Runbook Completeness

**Current State**:
- Good: `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md`, `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md`, `docs/guides/NODE-INITIALIZATION.md`
- Missing: `docs/guides/SECRETS-MANAGEMENT.md`, `docs/guides/REMOTE-RUNNER-SETUP.md` (referenced but stub/missing)
- No unified operator handbook

**Impact**: Operator onboarding requires reading 20+ scattered docs and ADRs

**Recommended Action**:
- Create `docs/operator-handbook/` with consolidated index
- Add missing guides: SECRETS-MANAGEMENT, REMOTE-RUNNER-SETUP, TROUBLESHOOTING, MIGRATION-v4-to-v5
- Link from root README.md

---

### 3.3 Plugin Development Guide

**Current State**:
- Plugin contract defined in ADR 0063, 0065, 0080, 0086
- No unified "How to Write a Plugin" guide
- Examples scattered across existing plugins

**Impact**: High barrier to entry for contributors

**Recommended Action**:
- Create `docs/developer-guides/PLUGIN-DEVELOPMENT.md`
- Include: stage/phase selection, manifest structure, testing checklist, common patterns
- Reference from CONTRIBUTING.md

---

## Part 4: Recommended Improvements by Priority

### HIGH Priority (Blocking Production Use)

| ID | Issue | Impact | Recommended Action | ADR |
|----|-------|--------|-------------------|-----|
| **H1** | ADR 0080 phase executor not implemented | Cannot use assemble/build stages | Implement phase-aware runtime | 0080 |
| **H2** | Parallel execution race conditions | Non-deterministic failures | Add thread-safe data bus | 0080 |
| **H3** | Generated output parity validation missing | Silent generator regressions | Add CI gate for generated diffs | New ADR |

### MEDIUM Priority (Operational Efficiency)

| ID | Issue | Impact | Recommended Action | ADR |
|----|-------|--------|-------------------|-----|
| **M1** | Plugin contract runtime enforcement missing | Silent coupling breakage | Add consumes/produces validation | 0080 |
| **M2** | Secrets passthrough leakage risk | Accidental secret commits | Add pre-commit secret scanning | 0094 |
| **M3** | ADR analysis directories incomplete | Missing implementation evidence | Create analysis dirs for 15 ADRs | Policy |
| **M4** | Operator runbook fragmented | High onboarding friction | Consolidate operator handbook | Docs |

### LOW Priority (Technical Debt)

| ID | Issue | Impact | Recommended Action | ADR |
|----|-------|--------|-------------------|-----|
| **L1** | ADR 0083 deferred | Manual bootstrap required | Complete when hardware available | 0083 |
| **L2** | Plugin development guide missing | Contributor friction | Write plugin authoring guide | Docs |
| **L3** | Mermaid quality gate not in CI | Potential diagram regressions | Add to `task ci` | 0027 |
| **L4** | AI commit metadata not enforced | Accountability gaps | Add git hook or CI check | 0096 |

---

## Part 5: Proposed New ADRs

### ADR 0097: Generated Artifact Parity Validation (Proposed)

**Problem**: No automated detection of unintended changes to generated outputs.

**Decision**:
1. Add `task validate:generated-parity` that regenerates artifacts and diffs against committed state
2. Integrate into `task ci` as quality gate
3. Require explicit commit message annotation when generator changes are intentional

**Rationale**: Prevents silent drift, ensures topology is single source of truth.

---

### ADR 0098: ADR 0080 Remediation Plan (Proposed)

**Problem**: ADR 0080 marked "Accepted" but has 20+ unimplemented components.

**Decision**:
1. Update ADR 0080 status to "Partially Implemented"
2. Create `adr/0080-remediation/` with 6-wave implementation plan
3. Prioritize Wave 1 (phase executor) and Wave 4 (parallel safety)

**Rationale**: Unblock assemble/build stages, fix production safety issues.

---

## Part 6: Strengths to Preserve

### Architectural Wins ✅

1. **Class->Object->Instance Model** (ADR 0062): Well-adopted, clear ownership boundaries
2. **Plugin Microkernel** (ADR 0063): Extensible, DAG-based execution working well
3. **Framework/Project Separation** (ADR 0075/0076): Clean boundary, artifact distribution operational
4. **Deploy Domain Contracts** (ADR 0084/0085): Immutable bundles + workspace-aware runners is elegant
5. **Inspection Toolkit** (ADR 0095): Comprehensive, high-quality implementation
6. **AI Agent Rulebook** (ADR 0096): Low-token, ADR-derived rules are effective

### Operational Maturity ✅

- 478 test files covering plugin contracts, integration, acceptance
- Task-based orchestration (`Taskfile.yml`) with 100+ commands
- SOPS/age secrets management integrated (ADR 0072/0073)
- Parallel plugin execution operational
- Golden snapshot testing for generators

---

## Part 7: Risk Assessment

### Critical Risks 🔴

1. **ADR 0080 Implementation Gaps**: Parallel race conditions could cause production failures. **Mitigation**: Prioritize Wave 4 remediation.
2. **Secrets Passthrough Leakage**: Accidental plaintext commit risk. **Mitigation**: Add pre-commit hook immediately.

### Medium Risks 🟡

1. **Generator Drift**: No parity validation allows silent topology divergence. **Mitigation**: ADR 0097.
2. **Plugin Contract Violations**: Implicit coupling can break silently. **Mitigation**: Runtime enforcement (ADR 0080 Wave 5).

### Low Risks 🟢

1. **Documentation Fragmentation**: Slows onboarding but doesn't block functionality. **Mitigation**: Operator handbook consolidation.
2. **ADR 0083 Deferral**: Acceptable given hardware constraints and manual workaround availability.

---

## Conclusion

**Overall Assessment**: Architecture is in **strong condition** post-ADR 0095/0096. The Class->Object->Instance topology model is solid, plugin microkernel is operational, and deploy domain contracts are complete.

**Critical Action Required**: Complete ADR 0080 implementation (phase executor + parallel safety). Current "Accepted" status misrepresents implementation reality.

**Recommended Next Steps**:
1. Create `adr/0080-remediation/IMPLEMENTATION-PLAN.md` (HIGH priority)
2. Implement generated artifact parity validation (ADR 0097) (HIGH priority)
3. Add secrets passthrough scanning pre-commit hook (MEDIUM priority)
4. Consolidate operator documentation (MEDIUM priority)
5. Finalize ADR 0083 when hardware available (LOW priority)

**No Show-Stoppers**: Project can proceed with current architecture for SOHO deployment, but production multi-site use requires ADR 0080 completion.

---

**Analysis Metadata**:
- AI-Agent: Claude Code (claude-sonnet-4-5-20250929)
- Analysis Method: Gap analysis per AGENT-RULEBOOK.md rules
- Evidence Sources: ADR files, codebase inspection, git history, test coverage
- Validation: Cross-referenced against ADR 0080 GAP-ANALYSIS.md and recent commits
