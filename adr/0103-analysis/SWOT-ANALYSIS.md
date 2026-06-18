# ADR 0103 SWOT Analysis

**Date:** 2026-06-18
**Mode:** SPC (Strict Process Compliance)
**Analyst:** AI Agent (Claude Opus 4.5)

---

## Executive Summary

ADR 0103 defines a dual-mode runtime reconciliation architecture replacing static `status` fields in instance YAML files. This SWOT analysis evaluates the architecture post-revision and identifies improvement opportunities.

**Key Finding:** The architecture is sound but has known coverage limitations (~15% Terraform state coverage). Amendments D9-D12 address specification gaps.

---

## SWOT Matrix

### Strengths

| # | Strength | Evidence | Impact |
|---|----------|----------|--------|
| S1 | Dual-mode architecture satisfies both determinism (CI) and live-detection | ADR 0103 D2.1/D2.2 | Resolves constraint conflict C2 vs C9 |
| S2 | Reuses existing SOPS/age infrastructure | ADR 0103 D7 | No new secret paths required |
| S3 | Wave 3 migration complete (151 files cleaned) | Verified 2026-06-18 | Topology = intent only |
| S4 | Terraform state parsing is deterministic and fast (<1s) | ADR 0103 D2.1 | CI-compatible |
| S5 | Follows IaC patterns (Terraform, Kubernetes) | ADR 0103 Context | Familiar model for operators |
| S6 | SPC revision eliminated critical violations | SPC-ANALYSIS.md | Architecturally correct |

### Weaknesses

| # | Weakness | Evidence | Severity | Mitigation |
|---|----------|----------|----------|------------|
| W1 | Only 15% of instances have Terraform state coverage | Diagnostic analysis | High | D12 expansion roadmap |
| W2 | No Proxmox terraform.tfstate exists | File system check | High | Create Proxmox TF config |
| W3 | Docker containers lack state source for pipeline | By design | Medium | CLI-only or snapshots |
| W4 | CLI mode requires device connectivity | ADR 0103 D2.2 | Medium | Document as limitation |
| W5 | Dual-mode increases maintenance complexity | Trade-off | Low | Shared core library |
| W6 | Report schema was not formalized | Gap analysis | Medium | **Fixed by D9** |
| W7 | `managed_by` auto-discovery not specified | Gap analysis | Low | **Fixed by D11** |
| W8 | Diagnostic codes not allocated | Gap analysis | Low | **Fixed by D10 (E83xx)** |

### Opportunities

| # | Opportunity | Mechanism | Effort | Priority |
|---|-------------|-----------|--------|----------|
| O1 | Proxmox Terraform provider exists — can generate tfstate | Create TF config | High | High |
| O2 | Docker state via `docker inspect` snapshot | Capture script | Medium | Medium |
| O3 | Unified report format enables dashboards/alerting | D9 schema | Low | Medium |
| O4 | Ansible fact cache as additional state source | Fact playbook | Medium | Low |
| O5 | Plugin architecture allows third-party reconcilers | ADR 0063 | Future | Low |
| O6 | Shared core library between pipeline and CLI | Refactoring | Medium | Medium |

### Threats

| # | Threat | Probability | Impact | Mitigation |
|---|--------|-------------|--------|------------|
| T1 | Terraform state may be stale vs actual device | Medium | Medium | CLI mode for accuracy + state age reporting |
| T2 | Terraform state format changes between versions | Low | Medium | Pin TF version, schema validation |
| T3 | MikroTik REST API authentication complexity | Medium | Low | Use proven library (routeros-api) |
| T4 | Out-of-band changes invisible until CLI reconcile | Medium | Medium | Document as known limitation |
| T5 | Build stage runtime may have gaps | Medium | High | Phase 0 pre-flight verification |

---

## Problem Classification

| ID | Problem | Classification | Severity | Addressability |
|----|---------|----------------|----------|----------------|
| P1 | 15% tfstate coverage | Coverage Gap | High | Partially (requires infra work) |
| P2 | No Proxmox tfstate | Missing State Source | High | Fully (create TF config) |
| P3 | Docker no pipeline state | Design Limitation | Medium | Trade-off (accept) |
| P4 | Build stage runtime gaps | Implementation Risk | Medium | Fully (pre-flight check) |
| P5 | Dual-mode complexity | Complexity Cost | Low | Trade-off (accept) |
| P6 | State staleness | Temporal Gap | Medium | Mitigated (CLI mode) |
| P7 | managed_by undefined | Specification Gap | Low | **Fixed (D11)** |
| P8 | No MikroTik REST client | Implementation Gap | High | Fully (Wave 2) |
| P9 | No E81xx codes | Governance Gap | Low | **Fixed (D10)** |
| P10 | No report schema | Contract Gap | Medium | **Fixed (D9)** |

---

## Amendments Applied

| Amendment | Decision | Addresses |
|-----------|----------|-----------|
| A1 | D9: Reconciliation Report Schema | W6, P10 |
| A2 | D10: Diagnostic Code Allocation (E81xx) | W8, P9 |
| A3 | D11: Convention-Based Resource Discovery | W7, P7 |
| A4 | D12: State Source Expansion Roadmap | W1, W2, W3 |

---

## Implementation Effort (Revised)

| Phase | Description | Original | Revised | Delta |
|-------|-------------|----------|---------|-------|
| Phase 0 | Pre-flight | 0h | 5h | +5h |
| Wave 1 | TF State Plugin | 5h | 17h | +12h |
| Wave 2 | CLI Command | (unestimated) | 17h | +17h |
| Wave 3 | Migration | (scripted) | **Done** | 0 |
| Wave 4 | Expansion | (future) | 24h | N/A |
| **Total** | Waves 0-2 | ~5h | **39h** | +34h |

---

## Constraint Compliance

| Constraint | Criticality | Status |
|------------|-------------|--------|
| C1 Stage affinity | Critical | ✅ Met |
| C2 Determinism | Critical | ✅ Met |
| C3 CI compatibility | Critical | ✅ Met |
| C6 Plugin contracts | Critical | ✅ Met (with D9) |
| C7 Topology = intent | Critical | ✅ Met |
| C8 SOPS/age credentials | Critical | ✅ Met |

---

## Recommendations

| Priority | Recommendation | Effort | Impact |
|----------|----------------|--------|--------|
| 1 | Execute Phase 0 pre-flight | 5h | De-risks Wave 1 |
| 2 | Execute Wave 1 (Plugin) | 17h | Core functionality |
| 3 | Execute Wave 2 (CLI) | 17h | Live reconciliation |
| 4 | Create Proxmox TF config (coverage) | 8h | +30% coverage |
| 5 | Docker snapshot script (coverage) | 4h | +20% coverage |

---

## Conclusion

ADR 0103 is **architecturally sound** after SPC revision. The dual-mode approach correctly resolves the conflict between CI determinism and live drift detection.

**Strengths outweigh weaknesses.** Coverage gaps (W1-W3) are known limitations with a clear expansion roadmap (D12).

**Next steps:** Execute Phase 0 pre-flight, then proceed with Wave 1 implementation.
