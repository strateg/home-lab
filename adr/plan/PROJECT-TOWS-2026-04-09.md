# Project TOWS Matrix

**Date:** 2026-04-09
**Purpose:** Convert project-wide SWOT into concrete strategic actions
**Companion:** `adr/plan/PROJECT-SWOT-2026-04-09.md`

---

## Executive Summary

The project already has strong architectural and validation assets. The most effective next moves are not broad new feature additions; they are focused actions that convert those assets into external proof, lower operational drag, and close the remaining deploy-domain gap.

---

## TOWS Matrix

### SO Strategies
Use strengths to exploit opportunities.

| ID | Strategy | Why it fits |
|---|---|---|
| SO1 | Run a real external project-repo pilot using the implemented framework/project split, lock verification, and bootstrap tasks | Uses S2, S3, S4 to realize O1 with evidence instead of theory |
| SO2 | Elevate `product:*` and readiness evidence into the main operator interface for non-developer workflows | Uses S5, S6, S7 to capture O2 and O4 |
| SO3 | Publish a narrow “blessed extension path” for project/object plugins using ADR 0078/0082 boundaries | Uses S1, S2, S4 to realize O3 without weakening core runtime |
| SO4 | Use ADR 0094 auditability and trust boundaries to trial AI advisory in one low-risk artifact family | Uses S1, S7 to capture O5 safely |

### ST Strategies
Use strengths to reduce or neutralize threats.

| ID | Strategy | Why it fits |
|---|---|---|
| ST1 | Convert architecture-complete vs hardware-proven into separate readiness signals in reports and manuals | Uses S7 to counter T2 |
| ST2 | Add scheduled backend and hardware smoke routines on top of existing strict/runtime gates | Uses S3 and S5 to counter T3 |
| ST3 | Treat task aliases, ADR status alignment, and `framework.lock` freshness as first-class governance checks | Uses S3 and S7 to counter T4 |
| ST4 | Make active authoritative paths explicit in repository docs and validation so historical/legacy trees cannot silently distort conclusions | Uses S1, S2, S7 to counter T5 |

### WO Strategies
Use opportunities to address weaknesses.

| ID | Strategy | Why it fits |
|---|---|---|
| WO1 | Use the external project-repo pilot to reduce maintainer guesswork and expose the minimum viable operator/consumer docs | Uses O1 to reduce W1 and W6 |
| WO2 | Use operator-productization work to simplify wrapper ownership and remove duplicate mental models | Uses O2 to reduce W5 |
| WO3 | Use ecosystem expansion intentionally through one reference external module/plugin package before broadening the model | Uses O3 to reduce W6 without uncontrolled growth |
| WO4 | Use AI advisory metrics to learn where governance/documentation overhead is highest in generation workflows | Uses O5 to illuminate W1 and W5 |

### WT Strategies
Minimize weaknesses to avoid threats.

| ID | Strategy | Why it fits |
|---|---|---|
| WT1 | Resolve ADR 0083 explicitly: either finish the contract on real hardware or narrow it further and mark the deferred scope clearly | Reduces W2 before it amplifies T2 and T3 |
| WT2 | Consolidate active authority docs for maintainers and operators into fewer living documents | Reduces W1 before it turns into T1 and T5 |
| WT3 | Introduce a lightweight “change bundle” rule: code changes that affect runtime boundaries must include lock refresh, docs sync, and targeted validation | Reduces W3 before it turns into T4 |
| WT4 | Formalize warning governance and metadata thresholds so advisory noise does not become background static | Reduces W4 before it turns into T1 and T5 |

---

## Prioritized Actions

### Priority 1

1. Execute one external consumer-repo pilot against the framework artifact/submodule model.
2. Resolve ADR 0083 status through either implementation closure or explicit narrowing.
3. Split readiness reporting into at least two states:
   - framework/runtime readiness
   - hardware/deploy readiness

### Priority 2

1. Produce a short maintainer authority pack:
   - current architecture map
   - active operational entrypoints
   - required validation gates for common change types
2. Add low-cost governance checks for:
   - missing top-level task entrypoints
   - stale `framework.lock`
   - ADR/register drift

### Priority 3

1. Define warning escalation policy for recurring diagnostics and metadata quality gaps.
2. Trial AI advisory mode in one bounded artifact family with success metrics.
3. Validate one real extension path through an external or project-scoped plugin/module package.

---

## Decision Guidance

If capacity is limited, the best sequence is:

1. External pilot
2. ADR 0083 decision
3. Maintainer-document consolidation
4. Backend/hardware smoke discipline

This order gives the highest information value while reducing the two main project risks:

- overconfidence in architectural completeness
- rising maintenance cost from governance complexity
