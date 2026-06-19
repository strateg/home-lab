# SWOT Analysis: ADR 0106 + ADR 0104 Integration

**Date:** 2026-06-18
**Updated:** 2026-06-18 (publish/subscribe design)
**Mode:** SPC (Strict Process Compliance)
**Scope:** Capability-Driven Plugin Architecture + Ansible Role Generation

---

## Executive Summary

ADR 0106 (Capability-Driven Plugin Architecture) and ADR 0104 (Ansible Role Generation) form a synergistic pair where capabilities drive Ansible role assignment. Analysis identified:

1. **Critical integration gap** (P1): derived capabilities not accessible to downstream
2. **Code duplication**: `capability_compiler.py` and `effective_model_compiler.py` both derive capabilities independently

**Solution:** Consolidate derivation in `capability_compiler`, use `publish/subscribe` pattern (consistent with project architecture) for `effective_model_compiler` to consume derived capabilities.

---

## SWOT Matrix

### Strengths (Internal, Positive)

| ID | Strength | Evidence | Leverage Strategy |
|----|----------|----------|-------------------|
| S1 | Sound architectural design | ADR 0106 D1-D8 well-defined | Use existing design, fix implementation |
| S2 | Complete capability helpers | 8 functions in capability_helpers.py | M2.A: Use `get_all_capabilities()` |
| S3 | Working reference implementation | wireguard_gateway role works | Pattern for new roles |
| S4 | Comprehensive capability catalog | 188+ capabilities defined | Extend, don't recreate |
| S5 | Plugin manifest system | Stage affinity enforced | M1.A uses existing infrastructure |
| S6 | Strict error model | E8020, E8021 defined | Quality gates exist |
| S7 | ALL-IN approach | No legacy fallbacks needed | Clean implementation path |

### Weaknesses (Internal, Negative)

| ID | Weakness | Impact | Resolution |
|----|----------|--------|------------|
| W1 | Derived caps not accessible to downstream | **BLOCKING** - generators blind | Subscribe in effective_model_compiler |
| W1b | Capability derivation duplicated in 2 compilers | High - inconsistency risk | Consolidate in capability_compiler |
| W2 | Projection ignores derived_capabilities | Critical - Ansible can't see caps | M2.A: Use helper function |
| W3 | Only 14% role coverage (1/7) | High - limited Ansible generation | M4.B, M5.A, M6.A: Implement roles |
| W4 | Missing cap.role.linux_host | Medium - common role unavailable | M10.A/B: Add to catalog |
| W5 | No CI validation for Ansible | Medium - quality gap | M9.A: Add syntax-check |
| W6 | Taskfile workflow incomplete | Medium - manual steps needed | M8.A: Implement tasks |

### Opportunities (External, Positive)

| ID | Opportunity | Potential | Capture Strategy |
|----|-------------|-----------|------------------|
| O1 | Single fix enables cascade | P1 fix unlocks P2, P3, P7 | Prioritize Phase 1 |
| O2 | Capability-driven multi-role | One instance → multiple roles | Expand CAPABILITY_ROLE_MAP |
| O3 | Auto-derived operations roles | cap.role.* from cap.os.* | Add derivation rules |
| O4 | Template-based scaling | New roles = new templates only | Maintain projection pattern |
| O5 | DevOps maturity | CI/CD integration | M8.A + M9.A |
| O6 | Cross-project reuse | Framework pattern reusable | Document patterns |

### Threats (External, Negative)

| ID | Threat | Likelihood | Impact | Mitigation |
|----|--------|------------|--------|------------|
| T1 | Breaking compiled.json structure | 50% | High | Diff test before/after (C13) |
| T2 | Generator regression | 30% | High | Full test suite (C14) |
| T3 | Capability namespace explosion | 20% | Medium | Strict governance |
| T4 | Template maintenance burden | 40% | Medium | Keep templates minimal |
| T5 | Performance regression | 10% | Low | Compile-time only (C15) |
| T6 | Role logic complexity | 30% | Medium | Keep roles static (C10) |

---

## Strategic Analysis

### SO Strategies (Strengths → Opportunities)

| Strategy | Description |
|----------|-------------|
| SO1 | Use S2 (helpers) to capture O1 (cascade fix) via M2.A |
| SO2 | Use S3 (wireguard pattern) to capture O4 (template scaling) |
| SO3 | Use S4 (catalog) to capture O3 (auto-derived roles) |

### WO Strategies (Weaknesses → Opportunities)

| Strategy | Description |
|----------|-------------|
| WO1 | Fix W1 (persist caps) to unlock O1 (cascade) |
| WO2 | Fix W3 (coverage) to capture O2 (multi-role) |
| WO3 | Fix W6 (taskfile) to capture O5 (DevOps) |

### ST Strategies (Strengths → Threats)

| Strategy | Description |
|----------|-------------|
| ST1 | Use S6 (strict errors) to mitigate T2 (regression) |
| ST2 | Use S7 (ALL-IN) to mitigate T3 (namespace explosion) |
| ST3 | Use S5 (manifest) to mitigate T5 (performance) |

### WT Strategies (Weaknesses → Threats)

| Strategy | Description |
|----------|-------------|
| WT1 | Fix W1 before T1 manifests (diff test) |
| WT2 | Fix W5 (CI) to catch T2 (regression) early |
| WT3 | Fix W4 (linux_host) to prevent T4 (template burden) |

---

## Problem-Solution Matrix

| Problem | Root Cause | Solution | Effort | Phase |
|---------|------------|----------|--------|-------|
| P1 (Blocking) | No subscribe in effective_model | Subscribe to derived_capabilities | 1h | 1 |
| P1b (High) | Derivation duplicated | Consolidate in capability_compiler | 2h | 1 |
| P2 (Critical) | Missing integration | M2.A: Use get_all_capabilities() | 1h | 1 |
| P3 (Critical) | Caused by P1 | Solved by P1 fix | 0h | 1 |
| P4 (High) | Missing coverage | M4.B: Implement incrementally | 1h | 2 |
| P5 (High) | Missing assets | M5.A: Create templates | 7h | 3 |
| P6 (High) | Missing assets | M6.A: Create builders | 3h | 3 |
| P7 (Critical) | Caused by P1 | Solved by P1 fix | 0h | 1 |
| P8 (Medium) | Missing automation | M8.A: Implement taskfile | 2h | 5 |
| P9 (Medium) | Missing automation | M9.A: CI syntax-check | 2h | 5 |
| P10 (Medium) | Missing coverage | M10.A+B: Catalog + derivation | 2h | 2 |

---

## Risk-Adjusted Implementation Priority

| Priority | Phase | Problems | Risk | Mitigation |
|----------|-------|----------|------|------------|
| 1 (Critical) | Phase 1 | P1, P2, P3, P7 | Medium | Diff test, test suite |
| 2 (High) | Phase 2 | P4, P10 | Low | Catalog validation |
| 3 (High) | Phase 3 | P5, P6 | Medium | Template review |
| 4 (Medium) | Phase 4 | Generator integration | Medium | Integration tests |
| 5 (Medium) | Phase 5 | P8, P9 | Low | CI validation |

---

## Quantified Impact

### Before Fix (AS-IS)

| Metric | Value |
|--------|-------|
| Derived capabilities visible to generators | 0% |
| CAPABILITY_ROLE_MAP utilization | 14% (1/7) |
| Ansible roles generatable | 1 (wireguard_gateway) |
| CI validation coverage | 0% |

### After Fix (TO-BE)

| Metric | Value | Delta |
|--------|-------|-------|
| Derived capabilities visible to generators | 100% | +100% |
| CAPABILITY_ROLE_MAP utilization | 100% (7/7) | +86% |
| Ansible roles generatable | 7+ | +6 |
| CI validation coverage | 100% | +100% |

---

## Recommendations

### Immediate (Phase 1)

1. **Fix P1**: Add 3 lines to `capability_compiler.py` to merge derived_capabilities into objects
2. **Fix P2**: Replace `inst.get("enabled_capabilities")` with `get_all_capabilities(inst)`
3. **Test**: Run diff test and full test suite

### Short-term (Phase 2-3)

1. Add `cap.role.linux_host` to catalog with derivation rule
2. Create templates for docker_host, node_exporter, common roles
3. Create projection builders for new roles

### Medium-term (Phase 4-5)

1. Implement multi-role assignment in generator
2. Add Taskfile ansible:role-runtime and ansible:role-check
3. Add CI validation with ansible-playbook --syntax-check

---

## References

- ADR 0106: Capability-Driven Plugin Architecture
- ADR 0104: Ansible Role Generation from Topology
- SPC Analysis: Steps 0-5
- Integration Plan: ADR-0106-0104-INTEGRATION-PLAN.md
