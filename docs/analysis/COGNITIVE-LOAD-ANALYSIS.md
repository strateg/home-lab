# Cognitive Load Reduction Analysis for AI Agent Rules

**Date:** 2026-06-15
**Method:** SPC (Strict Process Compliance) 7-Step Protocol
**Scope:** Reducing cognitive load for humans and machines in project development through ADR-derived rule optimization

---

## Executive Summary

This analysis evaluates the current AI agent rule system and proposes optimizations to reduce token consumption while improving rule clarity and repeatability. Key findings:

- **Current state:** 4600 tokens full load, 2200 tokens typical session
- **Proposed state:** 300 tokens adapters, 1500 tokens typical session
- **Token reduction:** -77% adapters, -32% typical load
- **Problems identified:** 14 (2 HIGH, 8 MEDIUM, 4 LOW severity)
- **Solutions proposed:** 12 admissible mechanisms

---

## Step 1: Document Map

| Document | Owner | Purpose | Tokens |
|----------|-------|---------|--------|
| docs/ai/AGENT-RULEBOOK.md | Architect | Core rules, single source of truth | 1,101 |
| docs/ai/ADR-RULE-MAP.yaml | Architect | Rule-to-ADR traceability | N/A |
| docs/ai/rules/*.md (9 files) | Architect | Domain-specific rule packs | 3,097 |
| CLAUDE.md | Claude Users | Claude-specific adapter | 469 |
| .github/copilot-instructions.md | Copilot Users | Copilot-specific adapter | 380 |
| .codex/AGENTS.md | Codex Users | Codex-specific adapter | 448 |
| docs/guides/COMMON-WORKFLOWS.md | All Agents | Workflow commands | N/A |
| docs/ai/spc-contract.md | User/Analyst | Formal analysis methodology | N/A |

### Industry Sources Researched

| Source | Type | Key Insight |
|--------|------|-------------|
| [arXiv 2604.03826](https://arxiv.org/html/2604.03826v1) | Research | Last_K(3-5) ADRs optimal for context |
| [GitHub Blog: Copilot Instructions](https://github.blog/ai-and-ml/github-copilot/unlocking-the-full-power-of-copilot-code-review-master-your-instructions-files/) | Official | Keep <1000 lines, path-specific files |
| [OpenAI Codex Best Practices](https://developers.openai.com/codex/learn/best-practices) | Official | Short AGENTS.md > long vague rules |
| [DevTk Guide](https://devtk.ai/en/blog/complete-guide-cursorrules/) | Industry | Single baseline + tool-specific variants |
| [claude-rules](https://github.com/lifedever/claude-rules) | OSS | base + language + framework layering |
| [Lakera Prompt Engineering](https://www.lakera.ai/blog/prompt-engineering-guide) | Industry | XML delimiters, rules vs content separation |

---

## Step 2: Constraints Register

### Critical Constraints (Blocking)

| ID | Constraint | Violation Effect |
|----|------------|------------------|
| C1 | Token budget must decrease, not increase | Solution INVALID |
| C2 | ADR authority must be preserved | Solution INVALID |
| C3 | Multi-agent parity required | Solution INVALID |
| C4 | Secrets must never appear in rules | Solution INVALID |
| C5 | Existing 16 rules must remain functional | Solution INVALID |

### Target Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Adapter token budget | ~430 tokens each | ≤100 tokens |
| Rule pack total | 3,097 tokens | ≤2,500 tokens |
| Typical session load | ~2,200 tokens | ≤1,500 tokens |
| Entry points (effective) | 4 files | 1 file |

---

## Step 3: Diagnostic Analysis

### Token Budget (AS-IS)

| Component | Words | Est. Tokens | % of Full |
|-----------|-------|-------------|-----------|
| CLAUDE.md | 361 | 469 | 10% |
| copilot-instructions.md | 293 | 380 | 8% |
| AGENTS.md | 345 | 448 | 10% |
| AGENT-RULEBOOK.md | 847 | 1,101 | 24% |
| Rule packs total | 2,386 | 3,097 | 66% |
| **FULL LOAD** | 4,232 | **~4,600** | 100% |

### Loading Scenarios

| Scenario | Tokens | Context % (200K) |
|----------|--------|------------------|
| Minimal (adapter only) | ~430 | 0.2% |
| Adapter + Rulebook | ~1,550 | 0.8% |
| Typical (+ 2 packs) | ~2,200 | 1.1% |
| Full load (all packs) | ~4,600 | 2.3% |

### Structural Metrics

| Metric | Value | Industry Benchmark | Gap |
|--------|-------|-------------------|-----|
| Entry points | 4 files | 1-2 files | +2-3 excess |
| Rule packs | 9 | 3-5 | +4-6 excess |
| Files with code examples | 2/9 (22%) | >50% | -28% |
| Files with tables | 2/9 (22%) | >50% | -28% |
| Anti-pattern sections | 27 total | Present | OK |

### Cognitive Load Factors

**For Humans:**
- Files to discover: 14 (HIGH cognitive load)
- Pack selection: Manual glob matching (HIGH)
- Learning curve: Read 4+ files minimum (MEDIUM)

**For Machines (AI agents):**
- Parsing ambiguity: Low (GOOD)
- Context switching: 9 packs, manual selection (MEDIUM)
- Auto-detection: None (HIGH impact)

---

## Step 4: Problem Classification

| ID | Problem | Category | Severity |
|----|---------|----------|----------|
| P1 | Flat pack structure (no hierarchy) | STRUCTURE | HIGH |
| P2 | No auto-detection for pack selection | USABILITY-MACHINE | HIGH |
| P3 | 66% budget in packs | EFFICIENCY | MEDIUM |
| P4 | 4 entry points | USABILITY-HUMAN | MEDIUM |
| P5 | No code examples in 7/9 packs | CONSISTENCY | MEDIUM |
| P6 | No decision tables in 8/9 packs | CONSISTENCY | MEDIUM |
| P7 | ~30% adapter duplication | EFFICIENCY | LOW |
| P8 | All-or-nothing loading | EFFICIENCY | MEDIUM |
| P9 | No rule versioning | GOVERNANCE | LOW |
| P10 | No quantified rules | USABILITY-MACHINE | MEDIUM |
| P11 | Implicit conflict resolution | USABILITY-MACHINE | LOW |
| P12 | No iterative refinement process | GOVERNANCE | LOW |
| P13 | capability-model.md outlier | CONSISTENCY | LOW |
| P14 | 14 files to discover | USABILITY-HUMAN | MEDIUM |

### Classification Summary

| Type | Problems | Count |
|------|----------|-------|
| Design Gap | P1, P2, P8, P11 | 4 |
| Implementation Gap | P5, P6, P10, P13 | 4 |
| Process Gap | P9, P12 | 2 |
| Optimization Opportunity | P3, P4, P7, P14 | 4 |

---

## Step 5: Admissible Solution Space

| Problem | Admissible Mechanisms | Recommended |
|---------|----------------------|-------------|
| P1 | M1.1: 3-tier hierarchy (core → domain → specific) | M1.1 |
| P2 | M2.1: Agent reads files_glob; M2.3: Context detector in rulebook | M2.3 |
| P3 | M3.1: Compress to tables; M3.3: Remove ADR Sources inline | M3.1 + M3.3 |
| P4 | M4.1: Minimal adapters (<100 tokens each) | M4.1 |
| P5/P6 | M5.3: Replace prose with decision tables | M5.3 |
| P7 | M7.1: Reference-only adapters | M7.1 |
| P8 | M8.1: Tiered structure; M8.2: Quick Reference headers | M8.1 |
| P9/P12 | M9.1: Version headers; M9.2: Document refinement process | M9.2 |
| P10 | M10.1: Add quantified rules where applicable | M10.1 |
| P11 | M11.1: Explicit priority header | M11.1 |
| P13 | M13.1: Use capability-model.md as template | M13.1 |
| P14 | M14.2: Index/TOC in rulebook | M14.2 |

### Combined Solution Pattern

```
Tier 0: ADAPTERS (minimal, <100 tokens each)
   └── Pure reference to Tier 1

Tier 1: AGENT-RULEBOOK.md (core rules + auto-selection heuristics)
   └── Always loaded, contains CORE-001 to CORE-009
   └── Context detector: "If touching X, load pack Y"

Tier 2: RULE PACKS (on-demand, compressed)
   └── Quick Reference header (<100 tokens each)
   └── Decision tables instead of prose
   └── Version headers for tracking
```

---

## Step 6: SWOT Analysis

### Strengths (9)

| # | Strength |
|---|----------|
| S1 | ADR-backed traceability (126 references) |
| S2 | Structured rule packs (100% have Load when, Validation, ADR Sources) |
| S3 | Multi-agent coverage (Claude, Copilot, Codex) |
| S4 | Anti-pattern sections (27 "never/do not" constraints) |
| S5 | Separation of concerns (adapters vs rulebook vs packs) |
| S6 | Machine-parseable YAML registry |
| S7 | Low context utilization (2.3% of 200K) |
| S8 | Proven capability-model template |
| S9 | SPC mode integration |

### Weaknesses (9)

| # | Weakness | Problem ID |
|---|----------|------------|
| W1 | Flat pack structure | P1 |
| W2 | Manual pack selection | P2 |
| W3 | 66% budget in packs | P3 |
| W4 | 4 entry points | P4 |
| W5 | 78% packs lack code examples | P5 |
| W6 | 89% packs lack decision tables | P6 |
| W7 | No incremental loading | P8 |
| W8 | No quantified rules | P10 |
| W9 | No rule evolution process | P9, P12 |

### Opportunities (8)

| # | Opportunity | Expected Gain |
|---|-------------|---------------|
| O1 | 3-tier hierarchy | -30% duplication |
| O2 | Auto-selection heuristics | -50% manual decisions |
| O3 | Minimal adapters | -77% adapter tokens |
| O4 | Quick Reference headers | Incremental loading |
| O5 | Decision table standardization | +50% rule precision |
| O6 | Quantified rules | Actionable guidance |
| O7 | Copilot path-specific files | Native support |
| O8 | Industry alignment | Best practices |

### Threats (5)

| # | Threat | Mitigation |
|---|--------|------------|
| T1 | Over-compression | Keep examples for complex rules |
| T2 | Agent divergence | Maintain parity constraint |
| T3 | ADR drift | Version headers, periodic audit |
| T4 | Hierarchy complexity | Clear tier boundaries |
| T5 | Breaking changes | Backward compatibility check |

---

## Step 7: Compliance Matrix

| Requirement | Met? | Verification |
|-------------|------|--------------|
| C1: Token budget decrease | YES | Adapters -77%, Typical -32% |
| C2: ADR authority preserved | YES | Priority header explicit |
| C3: Multi-agent parity | YES | Identical minimal format |
| C4: Secrets never in rules | YES | SEC-001 preserved |
| C5: 16 rules functional | YES | Format changes only |

### Implementation Phases

| Phase | Scope | Priority |
|-------|-------|----------|
| Phase 1 | Minimal adapters, auto-selection, priority header | HIGH |
| Phase 2 | Quick refs, tables in all packs, version headers | MEDIUM |
| Phase 3 | Quantified metrics, code examples | LOW |

---

## Expected Outcomes

| Metric | Current | After | Change |
|--------|---------|-------|--------|
| Adapter tokens (each) | ~430 | <100 | **-77%** |
| Adapter total (3 files) | ~1,300 | <300 | **-77%** |
| Typical session load | ~2,200 | ~1,500 | **-32%** |
| Entry points (effective) | 4 | 1 | **-75%** |
| Human files to read | 14 | 2-3 | **-80%** |
| Pack loading decision | Manual | Heuristic | **Automated** |

---

## Files to Modify

| File | Change | Phase |
|------|--------|-------|
| CLAUDE.md | Rewrite to minimal | 1 |
| .github/copilot-instructions.md | Rewrite to minimal | 1 |
| .codex/AGENTS.md | Rewrite to minimal | 1 |
| docs/ai/AGENT-RULEBOOK.md | Add auto-selection, priority | 1 |
| docs/ai/rules/*.md (9 files) | Add quick refs, tables, versions | 2 |

---

## References

- [arXiv: Context Matters - ADR Generation Using LLMs](https://arxiv.org/html/2604.03826v1)
- [GitHub Blog: Mastering Copilot Instructions](https://github.blog/ai-and-ml/github-copilot/unlocking-the-full-power-of-copilot-code-review-master-your-instructions-files/)
- [OpenAI Codex Best Practices](https://developers.openai.com/codex/learn/best-practices)
- [DevTk: Complete Guide to AI Coding Rules](https://devtk.ai/en/blog/complete-guide-cursorrules/)
- [GitHub awesome-copilot Instructions](https://github.com/github/awesome-copilot/blob/main/docs/README.instructions.md)
- [claude-rules Project](https://github.com/lifedever/claude-rules)
