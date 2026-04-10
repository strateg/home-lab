# ADR 0096 SWOT Analysis

**Date:** 2026-04-10
**Analyst:** SPC Protocol Analysis
**Subject:** AI Agent Rulebook and ADR-Derived Context Contract

---

## Executive Summary

ADR 0096 establishes a universal AI agent rulebook system that compresses ADR-derived rules into a compact, machine-readable format. This SWOT analysis evaluates the decision's strategic position and provides recommendations for strengthening the implementation.

---

## SWOT Matrix

### Strengths (Internal Positive)

| # | Strength | Impact | Evidence |
|---|----------|--------|----------|
| S1 | **Token efficiency** | High | Rulebook (~7,500 tokens) is 8-10x smaller than ADR corpus (~60,000+ tokens) |
| S2 | **ADR traceability** | High | Every rule has `source_adr` linking to authoritative decisions |
| S3 | **Multi-agent compatibility** | High | YAML + Markdown formats usable by Claude, Codex, Copilot, Cursor, MCP |
| S4 | **Tiered loading** | Medium | Always-load (8 CORE rules) + scoped rule packs reduces cognitive load |
| S5 | **Clear adapter model** | Medium | AGENTS.md, CLAUDE.md, copilot-instructions.md are bootloaders, not truth sources |
| S6 | **Domain coverage** | High | 8 rule packs cover all major domains (plugin, topology, deploy, generator, secrets, ADR, testing, TUC) |
| S7 | **Decision heuristics** | Medium | AGENT-RULEBOOK.md provides actionable change-type guides |
| S8 | **SPC separation** | Medium | SPC protocol is independent tool in docs/ai/spc-contract.md |

---

### Weaknesses (Internal Negative)

| # | Weakness | Impact | Mitigation Status |
|---|----------|--------|-------------------|
| W1 | **No validation tooling** | High | `task validate:agent-rules` is future/unimplemented |
| W2 | **No JSON schema** | Medium | ADR-RULE-MAP.yaml has no formal schema for validation |
| W3 | **Manual sync required** | Medium | Adapter files require manual audit for divergence |
| W4 | **No changelog/versioning** | Low | Schema evolution mechanism not defined |
| W5 | **Large dependency graph** | Low | 29 ADRs referenced (13 direct + 16 transitive) |
| W6 | **Qualitative risk controls** | Low | Risk Controls now have metrics but thresholds are aspirational |

---

### Opportunities (External Positive)

| # | Opportunity | Potential Impact | Feasibility |
|---|-------------|------------------|-------------|
| O1 | **MCP resource export** | High | Enable agent-native retrieval of rules via MCP protocol |
| O2 | **Automated rule generation** | High | Generate rules from ADR structured sections |
| O3 | **IDE integration** | Medium | Provide rulebook as VSCode/Cursor extension context |
| O4 | **Rule coverage reporting** | Medium | Generate coverage reports: which ADRs have rules, which don't |
| O5 | **Agent feedback loop** | Medium | Collect agent compliance metrics to improve rules |
| O6 | **Cross-repo reusability** | Low | Extract framework-agnostic rules for other projects |

---

### Threats (External Negative)

| # | Threat | Risk Level | Mitigation |
|---|--------|------------|------------|
| T1 | **Rulebook drift** | High | Validation task (W1) + source_adr traceability |
| T2 | **ADR corpus growth** | Medium | Scoped rule packs + tiered loading |
| T3 | **Agent capability variance** | Medium | YAML/Markdown universal formats |
| T4 | **Over-compression** | Medium | ADR deep read tier for ambiguous cases |
| T5 | **Maintenance burden** | Low | Clear ownership: ADR author maintains rules |
| T6 | **Security/secret exposure** | Low | SEC-001 rule + secrets.md rule pack |

---

## TOWS Strategy Matrix

### SO Strategies (Strengths + Opportunities)

| Strategy | Actions |
|----------|---------|
| **Leverage traceability for MCP** | Use source_adr links to build MCP resource export with ADR cross-references (S2 + O1) |
| **Scale tiered loading to IDE** | Extend scoped rule pack concept to IDE context providers (S4 + O3) |

### WO Strategies (Weaknesses + Opportunities)

| Strategy | Actions |
|----------|---------|
| **Build validation via automation** | Implement `task validate:agent-rules` that also generates coverage reports (W1 + O4) |
| **Add JSON schema from O2** | Create schema that enables both validation and rule generation (W2 + O2) |

### ST Strategies (Strengths + Threats)

| Strategy | Actions |
|----------|---------|
| **Use traceability to detect drift** | Automated check: source_adr must exist in REGISTER.md (S2 vs T1) |
| **Maintain ADR authority** | Explicit rule: ADR wins if conflict with compressed rule (S2 vs T4) |

### WT Strategies (Weaknesses + Threats)

| Strategy | Actions |
|----------|---------|
| **Prioritize validation tooling** | W1 is highest priority because it mitigates T1 directly |
| **Define schema evolution** | Add changelog mechanism before ADR corpus growth causes schema issues (W4 vs T2) |

---

## Prioritized Recommendations

| Priority | Recommendation | Addresses | Effort |
|----------|----------------|-----------|--------|
| 1 | Implement `task validate:agent-rules` | W1, T1 | Medium |
| 2 | Create JSON schema for ADR-RULE-MAP.yaml | W2 | Low |
| 3 | Add MCP resource export | O1 | Medium |
| 4 | Create rule coverage report | O4 | Low |
| 5 | Define schema changelog mechanism | W4, T2 | Low |
| 6 | Add adapter sync CI check | W3 | Low |

---

## Metrics Dashboard (Current State)

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Rules with valid source_adr | 100% | 100% | PASS |
| Rulebook token ratio | < 10% of ADR corpus | ~12% | PASS |
| Always-load rules | < 20 | 8 | PASS |
| Total rules | < 50 | 17 | PASS |
| Validation task implemented | Yes | No | FAIL |
| Adapters reference rulebook | All | All | PASS |
| Acceptance criteria met | All 5 | All 5 | PASS |

---

## Conclusion

ADR 0096 is a well-designed decision with strong fundamentals (token efficiency, traceability, multi-agent support). The primary weakness is the lack of validation tooling, which creates drift risk. The recommended path forward is:

1. **Immediate:** Implement validation task to close the enforcement gap
2. **Short-term:** Add JSON schema and coverage reporting
3. **Medium-term:** Explore MCP integration for agent-native retrieval

The SWOT analysis confirms the ADR is ready for **Accepted** status with the understanding that validation tooling is a follow-up work item.
