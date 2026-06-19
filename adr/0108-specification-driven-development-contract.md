# ADR 0108: Specification-Driven Development Contract

## Status

Proposed

## Date

2026-06-19

## Context

The project has evolved a sophisticated ADR-based architecture documentation system with 107+ records. However, the relationship between ADRs, machine-readable specifications, executable tests, and AI agent consumption lacks formal definition.

### Current State

| Asset | Purpose | Machine-Readable |
|-------|---------|------------------|
| ADRs (107 records) | Architectural decisions (why) | Partial (REGISTER.md) |
| ADR-RULE-MAP.yaml | AI rule routing | Yes |
| Rule packs | Contextual guidance | Semi-structured |
| capability-catalog.yaml | Device capabilities | Yes |
| JSON Schemas | Structure validation | Yes (limited coverage) |
| pytest tests | Verification | Yes |

### Problems

1. **No formal specification contract**: ADRs describe decisions but lack formal acceptance criteria format
2. **Traceability gaps**: Tests don't explicitly reference governing ADRs
3. **AI token inefficiency**: Rule packs lack token budget declarations
4. **No llms.txt**: AI agents cannot discover project structure efficiently
5. **Schema coverage**: Capabilities lack JSON Schema validation

### Industry Context

Specification-Driven Development (SDD) emerged in 2025 as response to LLM-generated code quality issues:

> "SDD is a methodology where an executable, version-controlled specification - not the code - is the single source of truth." — Thoughtworks Technology Radar 2025

Key standards:
- IEEE 830 / ISO/IEC/IEEE 29148: Requirements engineering
- BDD/Gherkin: Executable specifications
- llms.txt: AI agent discoverability (Anthropic, Cloudflare, Stripe adoption)

## Decision

Establish a **Specification Contract** that formalizes relationships between:

```
ADR (Why) → Rule Map (What) → Rule Pack (How) → Schema (Structure) → Test (Verify)
```

### 1. Specification Hierarchy

```yaml
specification_contract:
  version: 1.0

  levels:
    L1_decision:
      format: ADR markdown
      location: adr/*.md
      required_sections: [Context, Decision, Consequences]

    L2_rules:
      format: YAML
      location: docs/ai/ADR-RULE-MAP.yaml
      links_to: L1_decision via source_adr

    L3_guidance:
      format: Markdown with frontmatter
      location: docs/ai/rules/*.md
      max_tokens: 800
      soft_target: 500
      note: "Prefer ≤500 tokens; allow up to 800 for complex domains (capability-model, host-placement)"
      links_to: L2_rules via rule_pack reference

    L4_structure:
      format: JSON Schema
      location: schemas/*.schema.json
      links_to: L1_decision via $comment

    L5_verification:
      format: pytest
      location: tests/**/*.py
      links_to: L1_decision via "# ADR: 0xxx" marker
```

### 2. EARS Requirement Templates (Optional)

For formal, unambiguous requirements use **EARS (Easy Approach to Requirements Syntax)** patterns. EARS reduces AI clarification cycles by making triggers, conditions, and responses explicit.

| Pattern | Template | Example |
|---------|----------|---------|
| **Ubiquitous** | The [system] shall [action] | The compiler shall emit E8020 for missing capabilities |
| **Event-Driven** | When [trigger], the [system] shall [action] | When a plugin declares `execution_mode: subinterpreter`, the kernel shall isolate its state |
| **State-Driven** | While [state], the [system] shall [action] | While in strict mode, the agent shall refuse unvalidated changes |
| **Optional** | Where [condition], the [system] shall [action] | Where `host_ref` is set, the compiler shall resolve `@on:host.*` markers |
| **Unwanted** | The [system] shall not [action] | The generator shall not use string matching on object_ref |

**Usage:** EARS for formal requirements when precision matters. Adoption is optional.

### 3. llms.txt Index File

Create `/llms.txt` for AI agent discoverability:

```markdown
# Home-Lab Infrastructure-as-Data Project

## Quick Start
- Entry point: CLAUDE.md
- Full rules: docs/ai/AGENT-RULEBOOK.md

## Architecture
- Single source of truth: topology/topology.yaml
- Pattern: Class → Object → Instance
- Generated outputs: generated/ (DO NOT EDIT)

## Key Specifications
- ADR Register: adr/REGISTER.md (107 decisions)
- Rule Map: docs/ai/ADR-RULE-MAP.yaml
- Capability Catalog: topology/class-modules/capability-catalog.yaml

## Validation
- Compile: .venv/bin/python topology-tools/compile-topology.py
- Test: python -m pytest tests -q
- Full gate: task ci:local
```

### 4. Rule Pack Frontmatter Standard

```yaml
---
@pack: capability-model
@version: 1.2
@tokens: ~450
@adr: [0088, 0106]
@schema: schemas/capability.schema.json
@validates: task validate:capabilities
---
```

### 5. Test-to-ADR Traceability

Add ADR markers to **key architectural tests** (prioritized adoption):

**Priority 1 (Required):** `tests/plugin_contract/*.py` — plugin manifest and contract tests
**Priority 2 (Required):** `tests/plugin_integration/*.py` — integration and TUC tests
**Priority 3 (Optional):** Other test files — as maintenance occurs

```python
# ADR: 0106
# Verifies: AC1 - Capability query replaces string matching
def test_has_capability_returns_true_for_routeros():
    ...
```

**Scope:** ~50 key tests initially, expanding organically.

### 6. JSON Schema for Capabilities (Phase 2 — Deferred)

Create `schemas/capability.schema.json` when schema violations occur in production:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "capability.schema.json",
  "$comment": "ADR: 0088, 0106",
  "type": "object",
  "properties": {
    "@capability": {
      "type": "string",
      "pattern": "^cap\\.[a-z]+\\.[a-z_]+$"
    },
    "title": { "type": "string" },
    "summary": { "type": "string" },
    "domain": {
      "type": "string",
      "enum": ["bootstrap", "vendor", "os", "arch", "firmware", "role", "network", "compute"]
    },
    "layer": {
      "type": "string",
      "pattern": "^L[0-7]$"
    },
    "stability": {
      "type": "string",
      "enum": ["stable", "experimental", "deprecated"]
    }
  },
  "required": ["@capability", "title", "domain", "layer"]
}
```

### 7. Validation (Simplified)

Single consolidated validation task using grep-based checks (no custom scripts):

```yaml
# taskfiles/spec.yml
tasks:
  validate:
    desc: Validate specification contracts
    cmds:
      - echo "Checking rule pack frontmatter..."
      - grep -l "@tokens:" docs/ai/rules/*.md || echo "WARN: Missing @tokens in rule packs"
      - echo "Checking test-to-ADR markers..."
      - grep -r "# ADR:" tests/plugin_contract tests/plugin_integration | wc -l
      - echo "Specification validation complete"
```

**Metrics (Phase 2):** Token budgets and coverage metrics deferred until Phase 1 proves value.

## Consequences

### Positive

1. **Formal traceability**: ADR → Rule → Test chain is explicit via markers
2. **AI efficiency**: llms.txt + frontmatter enable optimal context loading (~130 tokens/session)
3. **Token predictability**: Rule packs have declared budgets in frontmatter
4. **Minimal overhead**: grep-based validation, no custom scripts
5. **Low barrier**: 3h implementation, immediate value

### Negative

1. **Deferred features**: JSON Schema, metrics dashboard not in Phase 1
2. **Manual tracking**: Some metrics require manual observation until Phase 2

### Neutral

1. **Extensible**: Phase 2 components can be activated when triggers occur
2. **CI impact**: Minimal — grep-based validation adds <5s to pipeline

## Alternatives Considered

### 1. Keep Current ADR-Only Approach

Rejected: Lacks formal acceptance criteria and test traceability.

### 2. Full IEEE 29148 Compliance

Rejected: Overkill for infrastructure project; ADRs are sufficient for decisions.

### 3. OpenAPI-Style Specification

Rejected: Designed for APIs, not infrastructure topology.

## Implementation Plan (Optimized)

**SWOT-optimized plan focusing on high-ROI components:**

### Phase 1: Core (HIGH ROI) — 3h

| Task | Effort | ROI |
|------|--------|-----|
| Create `/llms.txt` (10-line quick start) | 30min | HIGH |
| Add `@tokens` + `@adr` frontmatter to 10 rule packs | 1h | HIGH |
| Add `# ADR:` markers to ~50 key tests | 1h | MEDIUM |
| Add `task spec:validate` (grep-based) | 30min | MEDIUM |

### Phase 2: Extended (DEFERRED) — When Needed

| Task | Trigger | ROI |
|------|---------|-----|
| JSON Schema for capabilities | Schema violations in production | MEDIUM |
| Token budget validation script | Rule packs exceed 800 tokens | MEDIUM |
| Metrics dashboard | Management reporting need | LOW |
| EARS conversion for key ADRs | Requirement ambiguity issues | LOW |

**Total Phase 1: ~3h** (was 18h, 83% reduction)

### Eliminated from Original Plan

| Item | Reason |
|------|--------|
| llms-full.txt | CLAUDE.md + llms.txt sufficient |
| Gherkin syntax | EARS covers formal requirements |
| 6 validation scripts | grep-based check sufficient |
| Metrics dashboard | Premature optimization |

## References

- [Thoughtworks: Spec-Driven Development 2025](https://www.thoughtworks.com/insights/blog/spec-driven-development)
- [ISO/IEC/IEEE 29148:2018](https://www.reqview.com/doc/iso-iec-ieee-29148-templates/)
- [llms.txt Specification](https://llmstxt.org/)
- [Cucumber BDD](https://cucumber.io/docs/bdd/)
- ADR 0088: Capability Catalog Structure
- ADR 0106: Capability-Driven Plugin Architecture

## SPC Analysis Complete

**Date:** 2026-06-19
**Mode:** Strict Process Compliance (SPC) + SWOT Optimization

### SWOT Analysis Summary

| **Strengths** | **Weaknesses** |
|---------------|----------------|
| Clear 5-level hierarchy (L1-L5) | Original 18h effort excessive |
| Token budgets defined (800/500) | Multiple validation scripts |
| Existing capability catalog | Metrics require manual tracking |

| **Opportunities** | **Threats** |
|-------------------|-------------|
| AI agent efficiency gain | Over-engineering risk |
| Test traceability automation | Maintenance burden |
| Schema validation | Scope creep |

### Optimization Decisions

| Decision | Original | Optimized | Savings |
|----------|----------|-----------|---------|
| Implementation effort | 18h | 3h | 83% |
| Validation scripts | 6 scripts | grep-based | 100% |
| llms files | 2 (txt + full) | 1 (txt only) | 50% |
| Requirement syntax | Gherkin + EARS | EARS only | 50% |

### High-ROI Components (Keep)

| Component | Tokens | Frequency | Value |
|-----------|--------|-----------|-------|
| llms.txt | ~100 | Every session | AI discoverability |
| Rule pack frontmatter | ~30/pack | Auto-selected | Token predictability |
| ADR-RULE-MAP | ~200 | On-demand | Context routing |
| Test ADR markers | 0 | grep-based | Traceability |

### Deferred Components (Phase 2)

| Component | Trigger for Activation |
|-----------|------------------------|
| JSON Schema | Schema violations in production |
| Metrics dashboard | Management reporting need |
| EARS ADR conversion | Requirement ambiguity |
| Token budget scripts | Rule packs exceed 800 tokens |
