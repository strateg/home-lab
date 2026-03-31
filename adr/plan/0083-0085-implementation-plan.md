## Summary of All 16 Analysis Documents

### **ADR 0083 Analysis Files** (10 files)

---

#### **1. IMPLEMENTATION-PLAN.md**
- **Path:** `adr/0083-analysis/IMPLEMENTATION-PLAN.md`
- **Size:** 285 lines
- **Core Content:** Defines 8 phases (0-6 + 5a) for implementing the Unified Node Initialization Contract: environment setup, schema definition, MikroTik/Proxmox/Orange Pi bootstrap implementation, orchestration, assemble stage, and documentation.
- **Cross-references:** ADR 0084 (Phase 0), ADR 0080 (Waves A-H), ADR 0072 (secrets), ADR 0074 (generators), ADR 0057 (MikroTik reference)
- **Status Note:** DEFERRED - Correctly states "not the active implementation sequence. Active priority is ADR 0085 first, ADR 0084 second, and ADR 0083 only if unified node initialization is still justified after that foundation is in place."
- **Problems Found:**
  - ✅ NONE CRITICAL — Plan is well-structured with clear phases and dependencies
  - Task 3.0 added for Proxmox day-1 leakage audit (good addition)
  - 18-25 working days estimated with parallel work noted

---

#### **2. GAP-ANALYSIS.md**
- **Path:** `adr/0083-analysis/GAP-ANALYSIS.md`
- **Size:** 348 lines
- **Core Content:** Comprehensive gap analysis comparing AS-IS fragmented initialization to TO-BE unified contract. Identifies 9 gap items (G1-G9): schema definition, MikroTik/Proxmox/Orange Pi bootstrap coverage, orchestrator requirements, existing device migration, contract drift detection.
- **Cross-references:** ADR 0057, 0072, 0074, 0080; references to PLUGIN-BOUNDARY-ANALYSIS.md, FMEA.md, SECRETS-DATAFLOW.md, STATE-MODEL.md, TEST-MATRIX.md, CUTOVER-IMPACT.md
- **Status Note:** Correctly deferred with same wording as IMPLEMENTATION-PLAN.md
- **Key Updates Documented:** Critical review improvements table (2026-03-30) including D16-D18 additions (Proxmox pre-validation, existing device migration, contract drift)
- **Problems Found:**
  - ✅ NO ISSUES - Well-documented gaps with clear action items and risk summary

---

#### **3. CUTOVER-CHECKLIST.md**
- **Path:** `adr/0083-analysis/CUTOVER-CHECKLIST.md`
- **Size:** 172 lines
- **Core Content:** Pre-cutover gates and post-cutover verification checklist organized by subsystem: schema, MikroTik, Proxmox, Orange Pi, manifest, orchestration, assemble stage. Includes cutover execution steps, rollback plan, and sign-off table.
- **Cross-references:** ADR 0080 Wave F (for assemble stage)
- **Status Note:** "This checklist is dormant until ADR 0085 and ADR 0084 are accepted and implemented."
- **Problems Found:**
  - ⚠️ INCOMPLETE SIGN-OFF: Sign-off table has empty Name/Date/Signature fields (not a functional problem, just placeholder)
  - ✅ References are correct and sequencing (0085→0084→0083) is properly noted as blocking

---

#### **4. CUTOVER-IMPACT.md**
- **Path:** `adr/0083-analysis/CUTOVER-IMPACT.md`
- **Size:** 393 lines
- **Core Content:** Maps impacts across Taskfiles, scripts, documentation, CI, .gitignore. Describes existing device migration pattern (D17) with import vs bootstrap decision tree. Details operator workflow migration from manual to automated. Includes migration timeline, rollback triggers, and phase cutover checklists.
- **Cross-references:** ADR 0084 (environment check), ADR 0080 (Wave F for assemble), implicit references to deploy domain
- **Status Note:** Correctly positioned as deferred
- **Problems Found:**
  - ✅ NO ISSUES - Very comprehensive impact analysis
  - Migration guidance is clear and well-documented
  - Rollback triggers are practical

---

#### **5. FMEA.md** (Failure Mode and Effects Analysis)
- **Path:** `adr/0083-analysis/FMEA.md`
- **Size:** 267 lines
- **Core Content:** Failure-mode analysis for 5 mechanisms (MikroTik netinstall, Proxmox unattended, Orange Pi cloud-init, LXC terraform-managed, generic Ansible). Per-mechanism failure points, recovery procedures, and retry strategies. Includes critical D16 requirement: Proxmox answer.toml pre-validation with E9710-E9715 error codes.
- **Cross-references:** References D16 (Proxmox validation), D17 (existing devices), D18 (contract drift), D6 (state machine), ADR 0083 D7 (bootstrap boundary)
- **Status Note:** Correctly deferred with updated Proxmox validation section
- **Problems Found:**
  - ✅ EXCELLENT - D16 mandatory validation is well-specified with concrete error codes
  - Retry strategies are realistic (MikroTik linear backoff 15s, Proxmox 30s, Orange Pi 20s)
  - All mechanisms have defined recovery paths

---

#### **6. STATE-MODEL.md**
- **Path:** `adr/0083-analysis/STATE-MODEL.md`
- **Size:** 327 lines
- **Core Content:** Formal state machine (5 states: pending/bootstrapping/initialized/verified/failed). State file schema for `.work/native/bootstrap/INITIALIZATION-STATE.yaml` with concurrency model, file locking, atomic writes, and edge cases. Safety guard for `verified→pending` transition requiring `--confirm-reset`. Includes drift detection (D18) with `contract_hash`.
- **Cross-references:** D17 (import), D18 (drift), STATE-MODEL.md sections
- **Status Note:** Correctly positioned for post-0085/0084 implementation
- **Problems Found:**
  - ✅ WELL-DESIGNED - File locking, atomic writes, and state transitions are formally specified
  - Edge cases (manifest regen, drift, stale locks, concurrent ops) are all addressed
  - Platform-aware locking (fcntl for Unix, msvcrt for Windows) is correct

---

#### **7. TEST-MATRIX.md**
- **Path:** `adr/0083-analysis/TEST-MATRIX.md`
- **Size:** 267 lines
- **Core Content:** 82+ test cases across 8 categories (environment, schema, validators, generators, assemblers, orchestrator, handover, hardware E2E). CI-mock vs hardware distinction. Release-blocking gates: Environment→Schema→Validator→Generator→Assembler→Orchestrator→Handover→Hardware→Documentation.
- **Cross-references:** ADR 0084 (environment tests), references all components
- **Status Note:** Correctly positioned
- **Problems Found:**
  - ✅ COMPREHENSIVE - Test matrix covers all subsystems
  - Hardware E2E tests (T-E01, T-E06) are release-blocking; others advisory (good risk management)
  - CI markers for skipping hardware tests are defined

---

#### **8. SECRETS-DATAFLOW.md**
- **Path:** `adr/0083-analysis/SECRETS-DATAFLOW.md`
- **Size:** 223 lines
- **Core Content:** Secret lifecycle from encrypted source (SOPS+age) → pipeline (secret-free generated/) → assemble (secret injection to .work/native/) → deploy. Per-mechanism secret fields documented (MikroTik terraform_password, Proxmox root_password + API token, Orange Pi SSH keys, LXC implicit terraform-managed, Ansible passwords). Assemble stage plugin pseudocode. Security invariants: I1 (generated/ secret-free), I2 (secrets in .work/native/ only), I3 (SOPS+age only), I4 (cleanup/non-persistence).
- **Cross-references:** ADR 0072, ADR 0083 D7, ADR 0057 D8 (supersedes Ansible Vault), base.assembler.bootstrap_secrets
- **Status Note:** Correctly positioned
- **Problems Found:**
  - ✅ EXCELLENT SECURITY MODEL - Clear data flow, secret field registry, and cleanup requirements
  - Supersedes ADR 0057 D8 Ansible Vault with SOPS+age (good evolution)
  - Physical media cleanup reminder is practical

---

#### **9. PLUGIN-BOUNDARY-ANALYSIS.md**
- **Path:** `adr/0083-analysis/PLUGIN-BOUNDARY-ANALYSIS.md`
- **Size:** 178 lines
- **Core Content:** Plugin boundary analysis proving ADR 0083 plugins respect 4-level model (Global→Class→Object→Instance). 6 plugins analyzed: `base.validator.initialization_contract` (global), `base.generator.initialization_manifest` (global), `base.assembler.bootstrap_secrets` (global), object-level bootstrap generators for MikroTik/Proxmox/Orange Pi. Key distinction: plugins may iterate object/instance data generically but NOT reference hardcoded identifiers.
- **Cross-references:** ADR 0078 (object-level pattern), ADR 0074 (generator architecture)
- **Status Note:** Correctly positioned; stated as COMPLETED in GAP-ANALYSIS.md
- **Problems Found:**
  - ✅ NO ISSUES - Boundary analysis is clear and rigorous
  - Precedent citations (ansible_inventory, effective_json, terraform generators) are valid

---

#### **10. MIKROTIK-IAC-PATTERN.md**
- **Path:** `adr/0083-analysis/MIKROTIK-IAC-PATTERN.md`
- **Size:** 668 lines
- **Core Content:** Complete MikroTik IaC pattern: netinstall (day-0) → OpenTofu/Terraform (day-1 topology) → Ansible (day-1+ operations). Repository structure, bootstrap template, Terraform config, Ansible playbooks, object ownership matrix, handover verification checks, backup strategy, secrets management, Taskfile integration, and ADR 0083 integration examples.
- **Cross-references:** ADR 0057, ADR 0072, ADR 0083, terraform-routeros provider, community.routeros Ansible collection
- **Status Note:** Reference implementation for ADR 0083 Phase 2
- **Problems Found:**
  - ✅ NO ISSUES - Comprehensive reference pattern
  - Bootstrap script example is minimal (~25 lines, target <50)
  - Object ownership matrix clearly separates Terraform vs Ansible responsibilities

---

### **ADR 0084 Analysis Files** (3 files)

---

#### **11. IMPLEMENTATION-PLAN.md** (ADR 0084)
- **Path:** `adr/0084-analysis/IMPLEMENTATION-PLAN.md`
- **Size:** 179 lines
- **Core Content:** Three phases: 0a (runner contract alignment), 0b (Docker runner—planned), 0c (remote Linux runner—planned). Phase 0a targets workspace-aware `DeployRunner` contract, alignment of `NativeRunner`/`WSLRunner`, and refactoring `service_chain_evidence.py`.
- **Cross-references:** ADR 0083, ADR 0085
- **Status Note:** Phase 0a marked as "In Progress" (🔄)
- **Problems Found:**
  - ⚠️ INCONSISTENCY: Container link between ADRs might be clearer. Test matrix (T-R01..T-R12) is well-defined but implementation tasks (0a.1-0a.6) lack specific file paths for some outputs
  - ✅ Generally good structure; Docker/Remote phases properly deferred with clear trigger conditions

---

#### **12. GAP-ANALYSIS.md** (ADR 0084)
- **Path:** `adr/0084-analysis/GAP-ANALYSIS.md`
- **Size:** 145 lines
- **Core Content:** Gap analysis for runner abstraction: current state (dev workflows cross-platform but deploy execution is mixed), target state (Linux-backed deploy plane with workspace-aware runner). 7 gap items: runner abstraction (wrong shape), deploy execution assumptions, `service_chain_evidence.py` refactoring, ADR 0083 integration, Docker/Remote stubs, operator documentation. Acceptance signals clearly defined.
- **Cross-references:** ADR 0083, ADR 0085
- **Status Note:** Correctly positioned; Gap items align with Implementation Plan phases
- **Problems Found:**
  - ✅ NO ISSUES - Gap analysis is clear and actionable
  - Risks identified (WSL networking, bundle/workspace mismatch, remote staging drift) are realistic

---

#### **13. CUTOVER-CHECKLIST.md** (ADR 0084)
- **Path:** `adr/0084-analysis/CUTOVER-CHECKLIST.md`
- **Size:** 65 lines
- **Core Content:** Phase 0a pre-cutover gates (runner contract, NativeRunner/WSLRunner alignment, tests, refactoring). Phase 0b/0c future gates (Docker/Remote runners). Documentation and validation checks.
- **Cross-references:** None explicit
- **Status Note:** None
- **Problems Found:**
  - ⚠️ INCOMPLETE CHECKBOXES: Most Phase 0a items are unchecked ([ ] rather than [x]), suggesting this is a template rather than current status
  - ✅ Generally appropriate but very terse; could cross-reference the more detailed IMPLEMENTATION-PLAN.md

---

### **ADR 0085 Analysis Files** (3 files)

---

#### **14. IMPLEMENTATION-PLAN.md** (ADR 0085)
- **Path:** `adr/0085-analysis/IMPLEMENTATION-PLAN.md`
- **Size:** 32 lines
- **Core Content:** Very high-level 3-phase plan: Phase 1 (contract definition for deploy bundle/profile), Phase 2 (runner evolution), Phase 3 (deploy tooling integration). Acceptance criteria focus on bundle documentation, runner contract, and ADR alignment.
- **Cross-references:** ADR 0083, ADR 0084
- **Status Note:** "This is the primary deploy-domain implementation track."
- **Problems Found:**
  - ⚠️ TOO VAGUE - This is essentially a roadmap outline, not a detailed plan. Lacks specific tasks, timelines, deliverables
  - ⚠️ SEQUENCING CLAIM: States "primary track" but offers minimal detail compared to 0083's 285-line plan
  - Suggests ADR 0085 is the highest priority but lacks substance to back that up

---

#### **15. GAP-ANALYSIS.md** (ADR 0085)
- **Path:** `adr/0085-analysis/GAP-ANALYSIS.md`
- **Size:** 40 lines
- **Core Content:** Minimal gap analysis: current state (generated artifacts used implicitly), target state (immutable deploy bundle + workspace-aware runner). 5 key gaps listed (no canonical bundle layout, no deploy profile contract, no workspace staging contract, no capability negotiation, ADR 0083 wording reflects local-path assumptions). 3 risks identified.
- **Cross-references:** None explicit
- **Status Note:** None
- **Problems Found:**
  - ⚠️ TOO BRIEF - Doesn't define what's needed to close gaps
  - ⚠️ NO ACTION ITEMS - Unlike 0083 and 0084 gap analyses, this doesn't list "Action Required" columns

---

#### **16. CUTOVER-CHECKLIST.md** (ADR 0085)
- **Path:** `adr/0085-analysis/CUTOVER-CHECKLIST.md`
- **Size:** 11 lines
- **Core Content:** 11-item checklist (all unchecked) for approving ADR 0085: ADR approval, alignment of 0083/0084, bundle/profile/deploy-state documentation, runner model, legacy assumption removal.
- **Cross-references:** ADR 0083, ADR 0084
- **Status Note:** None
- **Problems Found:**
  - ⚠️ MINIMAL/TEMPLATE-ONLY - This is essentially a skeleton with no tasks or owner assignments
  - No acceptance tests or evidence criteria defined

---

## **Cross-Document Analysis**

### **Sequencing (0085 → 0084 → 0083) Reflection:**

| ADR | Stated Priority | Implementation Status | Detail Level |
|-----|-----------------|----------------------|--------------|
| 0085 | PRIMARY | Minimal (3-phase outline) | 32 lines (PLAN), 40 lines (GAP), 11 lines (CHECKLIST) |
| 0084 | SECONDARY | Moderate (Phase 0a in progress) | 179 lines (PLAN), 145 lines (GAP), 65 lines (CHECKLIST) |
| 0083 | CONDITIONAL (deferred) | Comprehensive (8-phase detailed) | 285 lines (PLAN), 348 lines (GAP), 172 lines (CHECKLIST) + 8 supporting docs |

**Problem Found:** ⚠️ **INVERSE DETAIL RELATIONSHIP** — The stated primary ADR (0085) has **minimal documentation**, while the conditional/deferred ADR (0083) has **extensive, well-structured analysis**. This creates confusion about actual priority vs. declared priority.

---

### **Duplicate/Redundant Sections:**

| Section | ADR 0083 | ADR 0084 | ADR 0085 | Notes |
|---------|----------|----------|----------|-------|
| Sequencing note | ✅ Present (clear) | ✅ Present | ✅ Present | All three consistently declare 0085→0084→0083 ordering |
| Runner/workspace discussion | ❌ None | ✅ Extensive | ✅ Mentioned | 0084 assumes 0085 context; 0083 doesn't discuss runner workspace model |
| Deployment profile | ❌ None | Implicit in 0084 Gap G4 | ✅ Mentioned (but not defined) | Gap: No project deploy profile schema exists |
| State file location | ✅ `.work/native/bootstrap/` | ❌ Not addressed | ⚠️ Vague "deploy-state root" | Potential conflict: 0083 uses `.work/native/bootstrap/`, but 0085 mentions separate "deploy-state root" |

**Problem Found:** ⚠️ **STATE FILE LOCATION AMBIGUITY** — ADR 0083 places runtime state in `.work/native/bootstrap/INITIALIZATION-STATE.yaml`, but ADR 0085 GAP-ANALYSIS mentions a separate "mutable deploy-state root." These may conflict if not clarified.

---

### **Implementation Plan Consistency:**

| Aspect | ADR 0083 | ADR 0084 | ADR 0085 |
|--------|----------|----------|----------|
| Phases | 8 (0-6 + 5a) | 3 (0a, 0b, 0c) | 3 (1, 2, 3) |
| Timeline | 18-25 working days | 2+2+3 days (phases planned) | Undefined |
| Dependencies | Clear (ADR 0084→Phase 0, ADR 0080 Waves A-H) | Clear (0083 Phase 5 expects workspace context) | Implicit (bundles, profiles, runner contract not yet specified) |
| Test gates | 82+ test cases (TEST-MATRIX.md) | 12 runner tests (IMPLEMENTATION-PLAN.md) | 0 (not defined in 0085 analysis docs) |
| Release criteria | Comprehensive (environment→schema→validator→generator→assembler→orchestrator→handover→hardware→docs) | Phase 0a gates (runner contract, tests, refactoring) | Minimal (just ADR approvals + documentation) |

**Problem Found:** ⚠️ **ZERO TEST MATRIX FOR ADR 0085** — While 0083 defines 82+ test cases and 0084 defines 12, ADR 0085 has no test matrix. This suggests 0085 is not yet sufficiently specified.

---

### **Cutover Checklist Dependencies:**

| ADR | Blocks Implementation | Blocked By |
|-----|----------------------|-----------|
| **0085** | ADR 0084 runner contract, ADR 0083 alignment | ⚠️ None (owns bundle/profile definitions) |
| **0084** | ADR 0083 Phase 0-1 (environment/schema need Linux-backed runner) | ADR 0085 bundle/profile definitions missing |
| **0083** | Full initialization system | ✅ ADR 0084 (Phase 0), ADR 0080 Waves A-H (completed) |

**Problem Found:** ⚠️ **CIRCULAR DEPENDENCY RISK** — ADR 0085 is supposed to define bundle/workspace contract, but ADR 0083 and 0084 checklists assume this is already defined. The 0085 analysis docs are too vague to unblock 0084/0083 implementation.

---

### **Cross-Reference Correctness:**

| Reference | Accuracy |
|-----------|----------|
| 0083 → ADR 0084 Phase 0 | ✅ Correct (Phase 0.1 references environment check) |
| 0083 → ADR 0057 (MikroTik reference) | ✅ Correct (MIKROTIK-IAC-PATTERN.md cites 0057) |
| 0083 → ADR 0072 (secrets) | ✅ Correct (SECRETS-DATAFLOW.md cites SOPS+age) |
| 0083 → ADR 0080 (plugin bus) | ✅ Correct (Phase 1 depends on Wave H completed) |
| 0084 → ADR 0083 | ✅ Correct (Phase 0a aligns runner for 0083 use) |
| 0084 → ADR 0085 | ✅ Correct (runner workspace model defined in 0085) |
| 0085 → ADR 0083 | ⚠️ Implicit only (not explicit in 0085 analysis docs) |
| 0085 → ADR 0084 | ✅ Correct (bundle/profile→runner workspace) |

---

### **Inconsistencies and Problems Summary:**

| Issue ID | Severity | Description | File(s) Affected | Recommendation |
|----------|----------|-------------|------------------|----|
| I1 | **HIGH** | ADR 0085 analysis docs are too vague; implementation plan is 3 phases with no tasks | IMPLEMENTATION-PLAN.md, GAP-ANALYSIS.md, CUTOVER-CHECKLIST.md (0085) | Expand 0085 analysis with concrete tasks, timelines, test matrix, and bundle/profile schema definition |
| I2 | **HIGH** | State file location ambiguity: 0083 uses `.work/native/bootstrap/`, 0085 mentions separate "deploy-state root" | STATE-MODEL.md (0083), GAP-ANALYSIS.md (0085) | Clarify in 0085 whether separate deploy-state root supersedes or complements 0083's state location |
| I3 | **MEDIUM** | Inverse detail relationship: declared primary ADR (0085) has minimal docs, deferred ADR (0083) has extensive docs | All three ADRs | Update 0085 docs to match 0083/0084 detail level, OR reconsider priority declaration |
| I4 | **MEDIUM** | ADR 0084 Phase 0a refactoring task (service_chain_evidence.py) lacks specific acceptance criteria | IMPLEMENTATION-PLAN.md (0084) | Add explicit before/after code patterns and test coverage targets |
| I5 | **MEDIUM** | ADR 0085 cutover checklist is only 11 lines with no owner/date/evidence criteria | CUTOVER-CHECKLIST.md (0085) | Expand with actual gate descriptions, evidence requirements, and stakeholder sign-offs |
| I6 | **LOW** | ADR 0083 cutover checklist has empty sign-off table | CUTOVER-CHECKLIST.md (0083) | Add names/dates if this is intended for tracking (or remove if just a template) |
| I7 | **LOW** | No test matrix defined for ADR 0085 | All 0085 analysis docs | Create test matrix for bundle/profile/deploy-state contracts (parallel to 0083's TEST-MATRIX.md) |

---

## **Key Findings**

### ✅ **What Works Well:**

1. **ADR 0083 Analysis is Comprehensive:** 10 supporting documents (1,870+ lines total) with well-structured IMPLEMENTATION-PLAN, GAP-ANALYSIS, FMEA, STATE-MODEL, TEST-MATRIX covering all failure modes, security, concurrency, and testing
2. **Correct Sequencing Declaration:** All three ADRs consistently state the 0085→0084→0083 priority order
3. **Security Model is Solid:** SECRETS-DATAFLOW.md clearly separates generated/ (secret-free) from .work/native/ (secret-bearing) with explicit cleanup requirements
4. **Test Coverage Defined:** ADR 0083 has 82+ test cases with release-blocking gates; ADR 0084 has 12 runner tests
5. **Failure Mode Analysis:** FMEA.md is thorough with per-mechanism retry strategies, recovery procedures, and D16 Proxmox pre-validation requirement

### ⚠️ **What Needs Improvement:**

1. **ADR 0085 is Under-Specified:** Analysis docs are 3 pages (83 lines total) with no concrete tasks, no test matrix, no bundle schema definition—too vague to unblock 0084/0083
2. **State File Location Ambiguity:** ADR 0083 uses `.work/native/bootstrap/`, but ADR 0085 GAP mentions separate "deploy-state root"—conflict not resolved
3. **Circular Dependency Risk:** ADR 0085 should define bundle/workspace contract, but ADR 0084/0083 implementation already assumes it exists
4. **Inverse Detail Relationship:** Declared primary ADR (0085) has minimal documentation; conditional/deferred ADR (0083) is the most detailed
5. **ADR 0084 Phase 0a Status Unclear:** Tests and tasks marked unchecked; unclear if "In Progress" means started or planned

### 🎯 **Critical Gaps:**

1. **No Deploy Bundle Schema:** ADR 0085 should define bundle layout, metadata, and immutability guarantees—MISSING
2. **No Project Deploy Profile Schema:** ADR 0085 mentions "project-scoped deploy profile" but doesn't define it—MISSING
3. **No Test Matrix for ADR 0085:** While 0083/0084 have comprehensive test matrices, 0085 has none—MISSING
4. **No Clear Workspace-Aware Runner Contract:** ADR 0084 describes what needs to change but 0085 should define the target contract—UNDERSPECIFIED

---

## **Recommendations**

1. **Prioritize ADR 0085 Detail:** Expand 0085 analysis docs to at least match 0084's detail level (5+ pages). Define bundle schema, profile contract, test matrix, and implementation tasks.
2. **Clarify State File Location:** Create a unified state/runtime directory model document that reconciles ADR 0083's `.work/native/bootstrap/` with ADR 0085's "deploy-state root."
3. **Add ADR 0085 Test Matrix:** Define parallel test structure to 0083's TEST-MATRIX.md covering bundle generation, profile validation, runner capability negotiation.
4. **Explicit Blocking Dependencies:** Create a timeline diagram showing which tasks in 0084/0083 depend on 0085 contract definitions completing.
5. **Update ADR 0084 Phase 0a Status:** Mark completed items [x], provide specific file/line references for ongoing tasks, and clarify sprint/timeline.
