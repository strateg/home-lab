# Plugin Model SWOT Analysis (Revised)

**Date:** 2026-05-31
**Status:** Complete
**Method:** SPC (Strict Process Compliance) 7-Step Protocol
**Scope:** v5 Plugin Architecture (ADR 0063, 0086, 0097)
**Previous Analysis:** 2026-05-29

---

## Executive Summary

This document presents a revised SWOT analysis of the v5 plugin model architecture, conducted 2 days after the initial analysis. Significant progress has been made on the development plan, with all 4 phases now complete.

**Key Changes from Baseline (2026-05-29):**
- Subinterpreter coverage: 87.1% → **97.6%** (+10.5%)
- config_schema coverage: 55% → **100%** (+45%)
- Development phases: 0/4 → **4/4 complete**
- Kernel modules extracted: 0 → **8**

**New Concerns:**
- Dependency depth: 6 → **19** (3× target limit)
- Flaky tests: 8 TUC tests showing intermittent failures

**Overall Position:**
- Internal balance: **+10** (was +2)
- External balance: **-1** (was 0)
- Total: **+9** (was +2)

---

## 1. Current State Reference

```
Plugin Model v5 (2026-05-31)
├── Fleet: 85 base plugins
├── Stages: 6 (DISCOVER→COMPILE→VALIDATE→GENERATE→ASSEMBLE→BUILD)
├── Phases: 6 per stage (INIT→PRE→RUN→POST→VERIFY→FINALIZE)
├── Execution: 97.6% subinterpreter, 2.4% missing mode
├── Kernel: ~5,777 LOC (8 extracted modules)
├── Architecture: Microkernel + Actor-style dataflow
├── Runtime: Python 3.14+ required (3.11+ fallback)
├── Tests: 1,585 passing, 78.12% coverage
└── Development Plan: Phases 1-4 COMPLETE
```

### Plugin Distribution

| Family | Count | Percentage |
|--------|-------|------------|
| Validators (JSON) | 44 | 51.8% |
| Compilers | 12 | 14.1% |
| Generators | 8 | 9.4% |
| Builders | 7 | 8.2% |
| Assemblers | 6 | 7.1% |
| Validators (YAML) | 4 | 4.7% |
| Discoverers | 4 | 4.7% |

---

## 2. SWOT Matrix

### Strengths (18 items, +4 from baseline)

| ID | Strength | Category | Impact |
|----|----------|----------|--------|
| S1 | 97.6% plugins subinterpreter-ready | Performance | Critical |
| S2 | Deterministic execution order | Reliability | Critical |
| S3 | 6-stage × 6-phase granularity | Extensibility | High |
| S4 | Explicit dependency graph (depends_on) | Maintainability | High |
| S5 | Contract-driven data exchange (produces/consumes) | Architecture | Critical |
| S6 | Actor-style fault isolation (snapshot/envelope) | Reliability | Critical |
| S7 | JSON Schema config validation | Reliability | Medium |
| S8 | Plugin attribution in diagnostics | Debuggability | Medium |
| S9 | Declarative YAML manifests | Developer Experience | High |
| S10 | 100% config_schema coverage | Quality | High |
| S11 | Deterministic discovery order | Reproducibility | Critical |
| S12 | Cycle detection at load time | Reliability | High |
| S13 | Event plane for loose coupling | Flexibility | Medium |
| S14 | 8 extracted kernel modules | Maintainability | High |
| S15 | All 4 development phases complete | Maturity | High |
| S16 | InputViewSpec implemented | Performance | Medium |
| S17 | 78.12% test coverage | Quality | High |
| S18 | 1,585 passing tests | Reliability | Critical |

### Weaknesses (8 items, -4 from baseline)

| ID | Weakness | Category | Risk |
|----|----------|----------|------|
| W1 | Registry complexity (2,455 LOC) | Maintainability | High |
| W2 | Max dependency depth = 19 | Architecture | Critical |
| W3 | instance_rows has 37 dependents | Coupling | High |
| W4 | plugin_base.py monolith (1,272 LOC) | Maintainability | Medium |
| W5 | Python 3.14+ version barrier | Adoption | High |
| W6 | 2 plugins missing execution_mode | Contract Gap | Low |
| W7 | 8 flaky TUC tests | Test Reliability | Medium |
| W8 | 14 DeprecationWarnings | Technical Debt | Low |

### Opportunities (8 items, -2 from baseline - implemented)

| ID | Opportunity | Category | Potential |
|----|-------------|----------|-----------|
| O1 | Event plane enables streaming/async | Architecture Evolution | Medium |
| O2 | 1:N framework→project scaling (ADR 0081) | Scalability | High |
| O3 | Declarative validator consolidation | Simplification | Medium |
| O4 | stage_local scope for memory efficiency | Resource Optimization | Low |
| O5 | Capability-based feature gating | Conditional Execution | Medium |
| O6 | Shift-left CI validation (architectural tests) | Quality Assurance | High |
| O7 | Checkpoint plugins for depth reduction | Architecture | High |
| O8 | StageExecutor extraction | Maintainability | Medium |

### Threats (9 items, -1 from baseline)

| ID | Threat | Category | Severity |
|----|--------|----------|----------|
| T1 | Python 3.14 release timeline uncertainty | Dependency Risk | High |
| T2 | Potential subinterpreter API changes | API Stability | Medium |
| T3 | jsonschema library breaking changes | Dependency Risk | Low |
| T4 | Plugin count growth pressure (85 → ?) | Scalability Pressure | Medium |
| T5 | Manifest schema evolution challenges | Contract Stability | Medium |
| T6 | Cross-project plugin ID collisions | Namespace Risk | Medium |
| T7 | Error catalog maintenance burden | Documentation Debt | Low |
| T8 | Dependency depth growth trend | Architecture Decay | High |
| T9 | Flaky test normalization | Quality Culture | Medium |

---

## 3. Quantitative Balance

| Quadrant | Count | Weight | Net Score |
|----------|-------|--------|-----------|
| Strengths | 18 | +1 each | +18 |
| Weaknesses | 8 | -1 each | -8 |
| Opportunities | 8 | +1 each | +8 |
| Threats | 9 | -1 each | -9 |
| **INTERNAL BALANCE** | — | — | **+10** |
| **EXTERNAL BALANCE** | — | — | **-1** |
| **TOTAL POSITION** | — | — | **+9** |

### Comparison with Baseline

| Metric | 2026-05-29 | 2026-05-31 | Delta |
|--------|------------|------------|-------|
| Strengths | 14 | 18 | +4 |
| Weaknesses | 12 | 8 | -4 |
| Opportunities | 10 | 8 | -2 |
| Threats | 10 | 9 | -1 |
| Internal Balance | +2 | +10 | +8 |
| External Balance | 0 | -1 | -1 |
| Total | +2 | +9 | +7 |

---

## 4. Critical Issues

### Issue 1: Dependency Depth Regression (W2)

**Severity:** Critical
**Current:** 19 hops (target ≤6)
**Root Cause:** New builder chain (soho_readiness → readiness_reports → generator_readiness_evidence)

**Longest Path:**
```
base.builder.release_manifest (depth 0)
  → base.builder.soho_readiness_package
    → base.builder.readiness_reports
      → base.builder.generator_readiness_evidence
        → base.builder.artifact_family_summary
          → base.builder.sbom
            → base.builder.bundle
              → base.assembler.manifest
                → ... (11 more levels)
                  → base.compiler.annotation_resolver (depth 18)
```

**Recommended Action:**
1. Raise soft limit to 20 (immediate)
2. Add depth regression test
3. Evaluate checkpoint plugins (Phase 6)

### Issue 2: Flaky TUC Tests (W7)

**Severity:** Medium
**Affected:** TUC0002, TUC0003, TUC0004 (8 tests)
**Root Cause:** Race conditions in parallel test execution

**Recommended Action:**
1. Fix determinism issues (partially done: 9ff71237)
2. Isolate test artifacts per-run
3. Add synchronization where needed

---

## 5. Closed Items (from Baseline)

| Previous ID | Item | Resolution |
|-------------|------|------------|
| W2 | 12.9% plugins sequential | Reduced to 2.4% |
| W5 | `when` field unused | Implemented |
| W6 | compiled_json_owner underused | Documented |
| W7 | 45% lack config_schema | 100% coverage achieved |
| W11 | 11 plugins cannot parallelize | Reduced to 2 |
| O1 | `when` field activation | Implemented |
| O5 | input_view snapshot optimization | Implemented |
| O7 | migration_mode | Implemented |
| O10 | Auto-generated plugin docs | Implemented |
| T2 | GIL contention fallback | Mitigated (97.6% ready) |
| T8 | Timeout tuning | Mitigated |

---

## 6. Next Phase Roadmap

### Phase 5: Consolidation (~17h)

| Task | Priority | Effort |
|------|----------|--------|
| Fix 8 flaky TUC tests | HIGH | 8h |
| Add depth regression test | HIGH | 4h |
| Fix DeprecationWarnings | LOW | 2h |
| Add missing execution_mode | LOW | 1h |
| Document instance_rows | MEDIUM | 2h |

### Phase 6: Architecture Refinement (~76h)

| Task | Priority | Effort |
|------|----------|--------|
| Extract StageExecutor | MEDIUM | 16h |
| Extract PluginExecutor | MEDIUM | 12h |
| Decompose plugin_base.py | LOW | 24h |
| Checkpoint plugins | MEDIUM | 16h |
| Depth reduction evaluation | LOW | 8h |

---

## 7. Constraints (Non-Negotiable)

| ID | Constraint | Status |
|----|------------|--------|
| C1 | Stage affinity (kind → stage) | Compliant |
| C2 | Deterministic execution order | Compliant |
| C3 | No circular dependencies | Compliant |
| C4 | Unique plugin IDs | Compliant |
| C5 | Workers don't mutate pipeline state | Compliant |
| C6 | Commit-only visibility | Compliant |
| C7 | depends_on required for subscribe | Compliant |
| C8 | Discovery order | Compliant |

---

## 8. References

- ADR 0063: Plugin Microkernel
- ADR 0086: Flatten Plugin Hierarchy
- ADR 0097: Actor-Style Execution
- Previous SWOT: `docs/analysis/PLUGIN-MODEL-SWOT-ANALYSIS.md`
- Development Plan: `docs/analysis/PLUGIN-SYSTEM-DEVELOPMENT-PLAN.md`

---

*Document generated via SPC 7-Step Protocol. All findings traceable to source ADRs and implementation code.*
