# Architectural Improvement Priorities - Executive Summary

**Date:** 2026-04-13
**Source:** ARCHITECTURAL-IMPROVEMENT-ANALYSIS.md
**Status:** Actionable Recommendations

---

## Critical Findings (Immediate Action Required)

### 1. ADR 0080 Implementation Gap - CRITICAL 🔴

**Issue**: ADR 0080 marked "Accepted" but missing 20+ core components
- ❌ Phase-aware executor not implemented
- ❌ Assemble/build stages non-functional
- ❌ Parallel execution has race conditions (G19-G24)
- ❌ PluginContext missing workspace_root, dist_root fields

**Impact**:
- Cannot implement deploy package assembly (ADR 0052)
- Non-deterministic failures in parallel mode
- Framework distribution workflows blocked (ADR 0076 Stage 2)

**Action**: Create `adr/0080-remediation/IMPLEMENTATION-PLAN.md` with 6-wave plan

**Priority**: **CRITICAL** - blocks production multi-site deployment

---

### 2. Parallel Execution Race Conditions - CRITICAL 🔴

**Issue**: Shared mutable state in plugin runtime
```python
_published_data = {}  # No locking
_current_plugin_id = None  # Identity leak risk
```

**Impact**: Race conditions in default parallel mode, non-deterministic CI failures

**Action**: ADR 0080 Wave 4 - thread-safe data bus implementation

**Priority**: **CRITICAL** - production safety issue

---

### 3. Generated Artifact Parity Validation Missing - HIGH 🟡

**Issue**: No CI gate detecting unintended generator output changes

**Impact**: Silent drift between topology and generated artifacts

**Action**: New ADR 0097 - Add `task validate:generated-parity` to CI

**Priority**: **HIGH** - data integrity risk

---

## Medium Priority (Operational Efficiency)

### 4. Plugin Contract Runtime Enforcement - MEDIUM 🟡

**Issue**: `consumes`/`produces` declared but not validated at runtime

**Impact**: Silent plugin coupling breakage, hard-to-debug failures

**Action**: ADR 0080 Wave 5 - contract validation phase

**Priority**: **MEDIUM** - improves reliability

---

### 5. Secrets Passthrough Leakage Risk - MEDIUM 🟡

**Issue**: `V5_SECRETS_MODE=passthrough` bypasses SOPS, no scanning for plaintext commits

**Impact**: Risk of accidental secret exposure

**Action**: Add pre-commit hook for secret scanning

**Priority**: **MEDIUM** - security hygiene

---

### 6. ADR Analysis Directories Incomplete - MEDIUM 🟡

**Issue**: 15 ADRs missing analysis directories (violates ADR policy)

**Missing**: ADR 0062, 0064, 0065, 0066, 0067, 0070, 0072, 0073, 0074, 0075, 0076, 0077, 0084, 0090, 0091

**Action**: Create analysis dirs with retrospective GAP-ANALYSIS.md / IMPLEMENTATION-PLAN.md

**Priority**: **MEDIUM** - governance compliance

---

### 7. Operator Runbook Fragmented - MEDIUM 🟡

**Issue**: Operator docs scattered across 136 markdown files, missing guides

**Missing**: SECRETS-MANAGEMENT.md, REMOTE-RUNNER-SETUP.md (referenced but stub)

**Action**: Create `docs/operator-handbook/` with consolidated index

**Priority**: **MEDIUM** - onboarding friction

---

## Low Priority (Technical Debt)

### 8. ADR 0083 Node Initialization - LOW (Correctly Deferred) 🟢

**Status**: Scaffold complete, deferred pending hardware availability

**Action**: Implement when Proxmox/OrangePi hardware available for testing

**Priority**: **LOW** - manual workaround acceptable

---

### 9. Plugin Development Guide Missing - LOW 🟢

**Issue**: No unified "How to Write a Plugin" guide for contributors

**Action**: Create `docs/developer-guides/PLUGIN-DEVELOPMENT.md`

**Priority**: **LOW** - contributor experience

---

### 10. AI Commit Metadata Not Enforced - LOW 🟢

**Issue**: CORE-009 rule (AI-Agent + AI-Tokens metadata) has no automated enforcement

**Action**: Add git hook or CI check for commit metadata

**Priority**: **LOW** - accountability improvement

---

## Recommended ADRs

### ADR 0097: Generated Artifact Parity Validation
- Add CI gate for `git diff generated/` after regeneration
- Fail CI if unexpected changes detected
- Require explicit annotation for intentional generator changes

### ADR 0098: ADR 0080 Remediation Plan
- Update ADR 0080 status to "Partially Implemented"
- 6-wave implementation plan in `adr/0080-remediation/`
- Prioritize Wave 1 (phase executor) and Wave 4 (parallel safety)

---

## Strengths to Preserve ✅

1. **Class->Object->Instance Model** - Well-adopted, clear boundaries
2. **Plugin Microkernel** - Extensible, DAG execution working
3. **Deploy Domain Contracts** - Immutable bundles + workspace-aware runners
4. **Inspection Toolkit (ADR 0095)** - Comprehensive, high-quality
5. **AI Agent Rulebook (ADR 0096)** - Effective low-token context
6. **Test Coverage** - 478 test files, golden snapshots

---

## Action Matrix

| Priority | Issue | Recommended Action | Blocks |
|----------|-------|-------------------|--------|
| **CRITICAL** | ADR 0080 gaps | 6-wave remediation plan | Deploy assembly, framework dist |
| **CRITICAL** | Parallel race conditions | Thread-safe data bus | Production reliability |
| **HIGH** | Generated parity missing | ADR 0097 - CI gate | Data integrity |
| **MEDIUM** | Contract enforcement | Runtime validation | Plugin reliability |
| **MEDIUM** | Secrets passthrough | Pre-commit hook | Security hygiene |
| **MEDIUM** | ADR analysis dirs | Create 15 missing dirs | Governance compliance |
| **MEDIUM** | Operator runbook | Consolidate handbook | Onboarding efficiency |
| **LOW** | ADR 0083 deferred | Wait for hardware | Manual workaround OK |
| **LOW** | Plugin dev guide | Author guide | Contributor experience |
| **LOW** | AI metadata | Git hook/CI check | Accountability |

---

## Quick Start for Next Work Session

```bash
# 1. Verify current ADR 0080 implementation status
task test:plugin-contract
.venv/bin/python topology-tools/compile-topology.py --stages compile,validate,generate

# 2. Create ADR 0080 remediation directory
mkdir -p adr/0080-remediation
# Add: IMPLEMENTATION-PLAN.md, WAVE-1-PHASE-EXECUTOR.md, WAVE-4-PARALLEL-SAFETY.md

# 3. Start ADR 0097 for generated parity validation
mkdir -p adr/0097-generated-artifact-parity-validation
# Add: template from adr/0000-template.md

# 4. Add secrets passthrough pre-commit hook
# File: .git/hooks/pre-commit
# Check for V5_SECRETS_MODE=passthrough artifacts

# 5. Create missing ADR analysis directories (15 ADRs)
for adr in 0062 0064 0065 0066 0067 0070 0072 0073 0074 0075 0076 0077 0084 0090 0091; do
  mkdir -p adr/${adr}-analysis
  # Populate with retrospective GAP-ANALYSIS.md
done
```

---

## Conclusion

**Overall Health**: 8/10 - Strong architecture, well-executed v5 migration

**Critical Blocker**: ADR 0080 implementation gaps must be resolved for production use

**Safe to Proceed**: SOHO deployment can proceed with current state, but multi-site requires ADR 0080 completion

**Next Session Focus**: ADR 0080 remediation plan creation (HIGH priority)
