# ADR 0103 SPC Analysis

**Date:** 2026-06-07
**Revised:** 2026-06-18 (Step 7 complete, SWOT analysis)
**Mode:** Strict Process Compliance (SPC)
**Outcome:** ADR 0103 Revised + SWOT Analysis + Amendments D9-D12

---

## Executive Summary

Original ADR 0103 proposed a `base.validator.device_reconciler` plugin in the validate stage to compute instance status by querying live devices. SPC analysis identified **critical architectural violations**:

1. **Stage affinity violation** — reconciliation ≠ validation
2. **Determinism violation** — live queries break reproducibility
3. **CI incompatibility** — CI cannot reach production devices
4. **Contract error** — referenced non-existent plugin

**Resolution:** Dual-mode architecture (Combination B+C):
- Pipeline mode: Terraform state reconciler (deterministic, build stage)
- CLI mode: Live device reconciler (on-demand, separate tool)

---

## SPC Steps Completed

| Step | Name | Status |
|------|------|--------|
| 0 | Read First | ✅ Completed |
| 1 | Document Map | ✅ 12 documents mapped |
| 2 | Constraints Register | ✅ 15 constraints identified |
| 3 | Diagnostic Analysis | ✅ Quantitative analysis |
| 4 | Problem Classification | ✅ 10 problems classified |
| 5 | Admissible Solution Space | ✅ 6 combinations evaluated |
| 6 | Model Rebuild | ✅ ADR 0103 revised + D9-D12 |
| 7 | Validation & Compliance | ✅ Completed (2026-06-18) |

---

## Key Findings

### Problems Identified

| ID | Problem | Classification | Severity |
|----|---------|----------------|----------|
| P1 | Static `status` field becomes stale | Data Model Gap | High |
| P2 | ADR 0103 references non-existent plugin | Contract Error | **Blocking** |
| P3 | Device queries in validate stage | Stage Affinity Violation | High |
| P4 | Live queries break determinism | Architectural Violation | **Critical** |
| P5 | CI cannot reach devices | Environment Constraint | **Critical** |
| P6 | Credentials undefined for reconciler | Security Gap | Medium |
| P7 | State source ambiguity | Semantic Ambiguity | Medium |
| P8 | 151 files require migration | Migration Scope | Medium |

### Critical Constraints

| # | Constraint | Source | Status |
|---|------------|--------|--------|
| C3 | Valid plugin references | ADR 0080 | Original **violated** |
| C4 | Deterministic outputs | ADR 0074 | Original **violated** |
| C11 | CI device access | Infrastructure | Original **violated** |

### Solution Decision

**Approved:** Combination B+C

| Component | Mechanism |
|-----------|-----------|
| Pipeline reconciliation | Terraform state parser (deterministic) |
| Live reconciliation | Separate CLI tool (on-demand) |
| Status field | Remove from all instances |
| Credential handling | SOPS/age integration |

---

## Changes Made

### ADR 0103 Revisions

| Section | Original | Revised |
|---------|----------|---------|
| D2 plugin ID | `base.validator.device_reconciler` | `base.builder.terraform_state_reconciler` |
| D2 stage | `validate` | `build` |
| D2 consumes | `base.compile.instance_index` | `base.compiler.instance_rows_prepare` |
| Architecture | Single-mode (live only) | Dual-mode (state + live) |
| CI support | Would fail | Supported |

### New Sections Added

- **Architectural Constraints** — explicit constraint acknowledgment
- **D2.1/D2.2** — dual-mode architecture
- **D4** — state source precedence
- **D6** — CI/production mode selection
- **D7** — credential integration
- **Compliance Matrix** — constraint satisfaction proof

---

## Files Modified

| File | Change |
|------|--------|
| `adr/0103-runtime-reconciliation-status-replaces-static-instance-status.md` | Revised |
| `adr/0103-analysis/ORIGINAL-ADR-0103.md` | Created (backup) |
| `adr/0103-analysis/SPC-ANALYSIS.md` | Created (this file) |

---

## 2026-06-18 Update: SWOT Analysis & Amendments

### New Decisions Added

| Decision | Title | Purpose |
|----------|-------|---------|
| D9 | Reconciliation Report Schema | Formal JSON schema for pipeline output |
| D10 | Diagnostic Code Allocation | E83xx range for reconciliation errors |
| D11 | Convention-Based Resource Discovery | Auto-match instance → TF resource |
| D12 | State Source Expansion Roadmap | Coverage improvement phases |

### SWOT Analysis Results

Full analysis: `adr/0103-analysis/SWOT-ANALYSIS.md`

| Category | Summary |
|----------|---------|
| Strengths | Dual-mode architecture; Wave 3 complete; SOPS reuse |
| Weaknesses | 15% tfstate coverage; no Proxmox state |
| Opportunities | Proxmox TF; Docker snapshots; Ansible facts |
| Threats | State staleness; TF version changes |

### Implementation Status

| Wave | Status | Notes |
|------|--------|-------|
| Phase 0 | Pending | Pre-flight verification |
| Wave 1 | Pending | TF State plugin (17h) |
| Wave 2 | Pending | CLI command (17h) |
| Wave 3 | ✅ **Complete** | 151 status fields removed |
| Wave 4 | Future | Coverage expansion (24h) |

---

## Completed

- ✅ Step 7: Validation & Compliance
- ✅ SWOT Analysis
- ✅ Amendments D9-D12 applied
- ✅ Wave 3 migration (151 files)

## Remaining

- Implementation: Phase 0, Wave 1, Wave 2
- ✅ E83xx codes allocated in error-catalog.yaml
- Report schema file creation (Phase 0 task 0.3)
