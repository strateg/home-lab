# Plugin Model SWOT Analysis and Development Roadmap

**Date:** 2026-05-29
**Status:** Complete
**Method:** SPC (Strict Process Compliance) 7-Step Protocol
**Scope:** v5 Plugin Architecture (ADR 0063, 0086, 0097)

---

## Executive Summary

This document presents a comprehensive SWOT analysis of the v5 plugin model architecture, conducted using the formal SPC methodology. The analysis identifies 14 strengths, 12 weaknesses, 10 opportunities, and 10 threats, with 24 strategic directions mapped to a prioritized development roadmap.

**Key Findings:**
- Internal balance: **+2** (strengths outweigh weaknesses)
- External balance: **0** (opportunities equal threats)
- Overall position: **Marginally positive**
- Subinterpreter readiness: **87.1%** (74/85 plugins)

---

## 1. Current State Reference

```
Plugin Model v5 (2026-05-29)
├── Fleet: 85 base plugins
├── Stages: 6 (DISCOVER→COMPILE→VALIDATE→GENERATE→ASSEMBLE→BUILD)
├── Phases: 6 per stage (INIT→PRE→RUN→POST→VERIFY→FINALIZE)
├── Execution: 87.1% subinterpreter, 12.9% main_interpreter
├── Kernel: ~4,242 LOC
├── Architecture: Microkernel + Actor-style dataflow
└── Runtime: Python 3.14+ required (3.11+ fallback)
```

### Plugin Distribution

| Family | Count | Percentage |
|--------|-------|------------|
| Validators | 48 | 56.5% |
| Compilers | 12 | 14.1% |
| Generators | 8 | 9.4% |
| Builders | 7 | 8.2% |
| Assemblers | 6 | 7.1% |
| Discoverers | 4 | 4.7% |

---

## 2. SWOT Matrix

### Strengths (Internal Positive)

| ID | Strength | Category | Impact |
|----|----------|----------|--------|
| S1 | 87.1% plugins subinterpreter-ready | Performance | High |
| S2 | Deterministic execution order | Reliability | Critical |
| S3 | 6-stage × 6-phase granularity | Extensibility | High |
| S4 | Explicit dependency graph (depends_on) | Maintainability | High |
| S5 | Contract-driven data exchange (produces/consumes) | Architecture | Critical |
| S6 | Actor-style fault isolation (snapshot/envelope) | Reliability | Critical |
| S7 | JSON Schema config validation | Reliability | Medium |
| S8 | Plugin attribution in diagnostics | Debuggability | Medium |
| S9 | Declarative YAML manifests | Developer Experience | High |
| S10 | 10 architectural patterns implemented | Maturity | High |
| S11 | Deterministic discovery order | Reproducibility | Critical |
| S12 | Cycle detection at load time | Reliability | High |
| S13 | Event plane for loose coupling | Flexibility | Medium |
| S14 | Stage-local data invalidation | Resource Management | Medium |

### Weaknesses (Internal Negative)

| ID | Weakness | Category | Risk |
|----|----------|----------|------|
| W1 | Registry complexity (2,860 LOC) | Maintainability | High |
| W2 | 12.9% plugins sequential (main_interpreter) | Performance | Medium |
| W3 | Max dependency depth = 6 | Performance | Medium |
| W4 | instance_rows has 35 dependents (bottleneck) | Coupling | High |
| W5 | `when` field unused (0% in base) | Feature Debt | Low |
| W6 | compiled_json_owner underused (1 plugin) | Contract Clarity | Low |
| W7 | 45% plugins lack config_schema | Reliability Gap | Medium |
| W8 | jsonschema dependency optional | Reliability Gap | Low |
| W9 | Python 3.14+ version barrier | Adoption | High |
| W10 | 4,242 LOC kernel maintenance | Maintenance Burden | Medium |
| W11 | 11 plugins cannot parallelize | Throughput Limit | Medium |
| W12 | Max fan-in = 9 (release_manifest) | Integration Complexity | Low |

### Opportunities (External Positive)

| ID | Opportunity | Category | Potential |
|----|-------------|----------|-----------|
| O1 | `when` field ready for profile-based execution | Feature Enablement | High |
| O2 | Event plane enables streaming/async | Architecture Evolution | Medium |
| O3 | 1:N framework→project scaling (ADR 0081) | Scalability | High |
| O4 | Declarative validator consolidation | Simplification | Medium |
| O5 | input_view snapshot optimization (ADR 0097) | Performance | Medium |
| O6 | stage_local scope for memory efficiency | Resource Optimization | Low |
| O7 | migration_mode for gradual generator migration | Migration Tooling | Medium |
| O8 | Capability-based feature gating | Conditional Execution | Medium |
| O9 | Shift-left CI validation (architectural tests) | Quality Assurance | High |
| O10 | Auto-generated plugin documentation | Developer Experience | Medium |

### Threats (External Negative)

| ID | Threat | Category | Severity |
|----|--------|----------|----------|
| T1 | Python 3.14 release timeline uncertainty | Dependency Risk | High |
| T2 | GIL contention on Python <3.14 fallback | Performance Degradation | Medium |
| T3 | Potential subinterpreter API changes | API Stability | Medium |
| T4 | jsonschema library breaking changes | Dependency Risk | Low |
| T5 | Plugin count growth pressure (85 → ?) | Scalability Pressure | Medium |
| T6 | Manifest schema evolution challenges | Contract Stability | Medium |
| T7 | Cross-project plugin ID collisions | Namespace Risk | Medium |
| T8 | Timeout tuning complexity | Operational | Low |
| T9 | Error catalog maintenance burden | Documentation Debt | Low |
| T10 | Test coverage maintenance at scale | Quality Assurance | Medium |

---

## 3. Strategic Directions

### 3.1 SO Strategies (Leverage Strengths + Opportunities)

| ID | Strategy | Priority | Effort | Risk |
|----|----------|----------|--------|------|
| SO1 | Enable multi-project parallel execution | HIGH | Medium | Low |
| SO2 | Activate profile-based conditional execution via `when` | MEDIUM | Low | Medium |
| SO3 | Implement input_view for snapshot optimization | LOW | High | High |
| SO4 | Auto-generate plugin documentation from manifests | MEDIUM | Low | Low |
| SO5 | Leverage event plane for async cross-plugin communication | LOW | Medium | Medium |
| SO6 | Enforce plugin placement via CI (already implemented) | DONE | — | — |

### 3.2 WO Strategies (Overcome Weaknesses via Opportunities)

| ID | Strategy | Priority | Effort | Risk |
|----|----------|----------|--------|------|
| WO1 | Decompose plugin_registry.py into submodules | MEDIUM | High | Medium |
| WO2 | Activate `when` field for conditional execution | MEDIUM | Low | Low |
| WO3 | Require config_schema for all new plugins (CI lint) | HIGH | Low | Low |
| WO4 | Further decompose high-dependency plugins | LOW | High | Medium |
| WO5 | Migrate remaining main_interpreter plugins | LOW | High | High |
| WO6 | Document compiled_json_owner usage pattern | LOW | Low | Low |

### 3.3 ST Strategies (Use Strengths to Counter Threats)

| ID | Strategy | Priority | Effort | Risk |
|----|----------|----------|--------|------|
| ST1 | Preserve envelope semantics on ThreadPool fallback | DONE | — | — |
| ST2 | Add parity tests for plugin additions | HIGH | Medium | Low |
| ST3 | Pin jsonschema version | MEDIUM | Low | Low |
| ST4 | Establish namespace conventions for project plugins | HIGH | Low | Low |
| ST5 | Auto-generate error catalog from diagnostics | MEDIUM | Medium | Low |
| ST6 | Add pre-commit dependency graph validation | HIGH | Low | Low |

### 3.4 WT Strategies (Minimize Weaknesses and Avoid Threats)

| ID | Strategy | Priority | Effort | Risk |
|----|----------|----------|--------|------|
| WT1 | Maintain dual-mode execution (3.14/fallback) | DONE | — | — |
| WT2 | Define incremental test coverage requirements | MEDIUM | Low | Low |
| WT3 | Add architectural lint for max dependency depth | MEDIUM | Low | Low |
| WT4 | Prioritize bottleneck plugin migration to subinterpreter | LOW | High | High |
| WT5 | Conduct architectural review of high fan-in plugins | LOW | Medium | Low |
| WT6 | Make jsonschema a required dependency | LOW | Low | Low |

---

## 4. Prioritized Development Roadmap

### Phase 1: Quick Wins (1-2 weeks)

**Goal:** Low-effort, high-impact improvements

| # | Task | Strategy | Effort | Files to Change |
|---|------|----------|--------|-----------------|
| 1.1 | Add CI lint requiring config_schema for new plugins | WO3 | 2h | `.github/workflows/`, `scripts/validation/` |
| 1.2 | Add pre-commit hook for dependency cycle detection | ST6 | 2h | `.pre-commit-config.yaml` |
| 1.3 | Establish plugin namespace conventions documentation | ST4 | 4h | `docs/guides/PLUGIN-NAMESPACE-CONVENTIONS.md` |
| 1.4 | Pin jsonschema version in requirements | ST3 | 1h | `requirements.txt`, `pyproject.toml` |
| 1.5 | Add architectural lint for dependency depth > 6 | WT3 | 4h | `scripts/validation/lint_plugin_depth.py` |

**Acceptance Criteria:**
- [ ] All new plugins require config_schema (CI enforced)
- [ ] Pre-commit blocks circular dependencies
- [ ] Namespace conventions documented
- [ ] jsonschema pinned to stable version
- [ ] Dependency depth lint runs in CI

### Phase 2: Quality Improvements (2-4 weeks)

**Goal:** Strengthen reliability and developer experience

| # | Task | Strategy | Effort | Files to Change |
|---|------|----------|--------|-----------------|
| 2.1 | Add parity tests for plugin additions | ST2 | 8h | `tests/plugin_integration/test_parity.py` |
| 2.2 | Auto-generate plugin documentation from manifests | SO4 | 16h | `scripts/docs/generate_plugin_docs.py` |
| 2.3 | Auto-generate error catalog from plugin diagnostics | ST5 | 8h | `scripts/docs/generate_error_catalog.py` |
| 2.4 | Define test coverage requirements per module | WT2 | 4h | `docs/guides/PLUGIN-TEST-REQUIREMENTS.md` |
| 2.5 | Activate `when` field with profile support | SO2, WO2 | 16h | `kernel/plugin_registry.py` |

**Acceptance Criteria:**
- [ ] Parity tests catch regressions on plugin changes
- [ ] Plugin docs auto-generated and published
- [ ] Error catalog generated from source
- [ ] Test coverage policy documented
- [ ] `when` field functional with profiles

### Phase 3: Architecture Improvements (1-2 months)

**Goal:** Reduce complexity and improve scalability

| # | Task | Strategy | Effort | Files to Change |
|---|------|----------|--------|-----------------|
| 3.1 | Decompose plugin_registry.py into submodules | WO1 | 40h | `kernel/registry/`, `kernel/scheduler/` |
| 3.2 | Enable multi-project parallel execution | SO1 | 24h | `compile-topology.py`, `kernel/` |
| 3.3 | Review and document high fan-in plugins | WT5 | 8h | `docs/architecture/PLUGIN-DEPENDENCY-REVIEW.md` |
| 3.4 | Document compiled_json_owner pattern | WO6 | 4h | `docs/guides/PLUGIN-AUTHORING_GUIDE.md` |

**Acceptance Criteria:**
- [ ] plugin_registry.py split into <500 LOC modules
- [ ] Multi-project execution tested
- [ ] High fan-in plugins documented with rationale
- [ ] Ownership pattern documented

### Phase 4: Performance Optimization (2-3 months)

**Goal:** Maximize parallelism and efficiency

| # | Task | Strategy | Effort | Files to Change |
|---|------|----------|--------|-----------------|
| 4.1 | Analyze and migrate remaining main_interpreter plugins | WO5, WT4 | 40h | Multiple plugin files |
| 4.2 | Implement input_view for snapshot size reduction | SO3 | 40h | `kernel/plugin_base.py`, `kernel/plugin_registry.py` |
| 4.3 | Further decompose instance_rows if beneficial | WO4 | 24h | `plugins/compilers/instance_rows_*.py` |
| 4.4 | Implement event plane async patterns | SO5 | 24h | `kernel/plugin_base.py`, example plugins |

**Acceptance Criteria:**
- [ ] >95% plugins in subinterpreter mode
- [ ] input_view reduces snapshot size by >30%
- [ ] Dependency depth reduced where possible
- [ ] Event plane patterns documented with examples

---

## 5. Risk Mitigation Plan

### High-Risk Items

| Risk | Mitigation | Owner | Timeline |
|------|------------|-------|----------|
| T1: Python 3.14 timeline | Maintain ThreadPool fallback; monitor Python release schedule | Architecture | Ongoing |
| W9: Version barrier | Document minimum requirements; provide migration guide | Documentation | Phase 1 |
| W1: Registry complexity | Incremental decomposition with parity tests | Architecture | Phase 3 |

### Conditional Strategies (Require Further Analysis)

| Strategy | Condition | Analysis Required |
|----------|-----------|-------------------|
| WO4 (instance_rows decomposition) | Dependency analysis shows benefit | Profile current execution times |
| WO5 (main_interpreter migration) | Plugin semantics allow isolation | Audit each plugin for mutable state |
| WT4 (bottleneck migration) | Same as WO5 | Same as WO5 |

---

## 6. Success Metrics

### Phase 1 Metrics
- [ ] 100% new plugins have config_schema
- [ ] 0 circular dependencies in CI
- [ ] Namespace conventions adopted

### Phase 2 Metrics
- [ ] Plugin documentation coverage: 100%
- [ ] Error catalog entries: auto-generated
- [ ] `when` field tests: passing

### Phase 3 Metrics
- [ ] plugin_registry.py: <500 LOC per module
- [ ] Multi-project execution: functional

### Phase 4 Metrics
- [ ] Subinterpreter coverage: >95%
- [ ] Snapshot size reduction: >30%

---

## 7. Constraints (Non-Negotiable)

The following constraints from ADR 0063, 0086, and 0097 MUST NOT be violated:

| ID | Constraint | Consequence if Violated |
|----|------------|------------------------|
| C1 | Stage affinity (kind → stage) | Plugin rejected |
| C2 | Deterministic execution order | Non-reproducible builds |
| C3 | No circular dependencies | Pipeline fail-fast |
| C4 | Unique plugin IDs | Manifest load error |
| C5 | Workers don't mutate pipeline state | Data corruption |
| C6 | Commit-only visibility | Partial state leaks |
| C7 | depends_on required for subscribe | PluginDataExchangeError |
| C11 | Discovery order: framework→class→object→project | Non-deterministic resolution |

---

## 8. References

- ADR 0063: Plugin Microkernel (`adr/0063-plugin-microkernel-for-compiler-validators-generators.md`)
- ADR 0086: Flatten Plugin Hierarchy (`adr/0086-flatten-plugin-hierarchy-and-reduce-granularity.md`)
- ADR 0097: Actor-Style Execution (`adr/0097-subinterpreter-parallel-plugin-execution.md`)
- Plugin Authoring Guide: `docs/PLUGIN_AUTHORING_GUIDE.md`
- Plugin Execution Modes: `docs/guides/PLUGIN-EXECUTION-MODES.md`
- Plugin Envelope Model: `docs/guides/PLUGIN-ENVELOPE-MODEL.md`

---

## Appendix A: Full SWOT Quantification

| Quadrant | Count | Weight | Net Score |
|----------|-------|--------|-----------|
| Strengths | 14 | +1 each | +14 |
| Weaknesses | 12 | -1 each | -12 |
| Opportunities | 10 | +1 each | +10 |
| Threats | 10 | -1 each | -10 |
| **INTERNAL BALANCE** | — | — | **+2** |
| **EXTERNAL BALANCE** | — | — | **0** |
| **TOTAL POSITION** | — | — | **+2** |

---

## Appendix B: Strategy Admissibility Summary

| Strategy Type | Total | Admissible | Conditional | Implemented |
|---------------|-------|------------|-------------|-------------|
| SO (Maxi-Maxi) | 6 | 5 | 0 | 1 |
| WO (Mini-Maxi) | 6 | 4 | 2 | 0 |
| ST (Maxi-Mini) | 6 | 4 | 0 | 2 |
| WT (Mini-Mini) | 6 | 4 | 2 | 2 |
| **TOTAL** | **24** | **17** | **4** | **5** |

---

*Document generated via SPC 7-Step Protocol. All findings traceable to source ADRs and implementation code.*
