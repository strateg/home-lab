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

### 2. ADR Acceptance Criteria Format

Adopt Gherkin-style acceptance criteria for **new and key ADRs** (optional adoption model):

**REQUIRED:** New ADRs with behavioral acceptance criteria
**RECOMMENDED:** Key architectural ADRs (0062, 0080, 0088, 0106, 0108)
**OPTIONAL:** Legacy ADRs, simple decision ADRs

Example Gherkin-style executable acceptance criteria:

```markdown
## Acceptance Criteria

### AC1: Capability query replaces string matching
```gherkin
Given an instance with class_ref "router/mikrotik-chateau-ax"
When the generator queries has_capability("cap.os.routeros")
Then it returns True
And no string matching on object_ref is performed
```

### AC2: Missing capability emits diagnostic
```gherkin
Given an instance without required capability "cap.bootstrap.netinstall"
When the initialization plugin executes
Then diagnostic E8020 is emitted with severity "error"
```
```

### 2b. EARS Requirement Templates

For formal, unambiguous requirements use **EARS (Easy Approach to Requirements Syntax)** patterns. EARS reduces AI clarification cycles by making triggers, conditions, and responses explicit.

| Pattern | Template | Example |
|---------|----------|---------|
| **Ubiquitous** | The [system] shall [action] | The compiler shall emit E8020 for missing capabilities |
| **Event-Driven** | When [trigger], the [system] shall [action] | When a plugin declares `execution_mode: subinterpreter`, the kernel shall isolate its state |
| **State-Driven** | While [state], the [system] shall [action] | While in strict mode, the agent shall refuse unvalidated changes |
| **Optional** | Where [condition], the [system] shall [action] | Where `host_ref` is set, the compiler shall resolve `@on:host.*` markers |
| **Complex** | If [condition] then [action], otherwise [alternative] | If capability is missing, emit E8021; otherwise proceed with generation |
| **Unwanted** | The [system] shall not [action] | The generator shall not use string matching on object_ref |

**Usage Guidelines:**
- EARS for **formal requirements** in ADRs (Decision section)
- Gherkin for **behavioral acceptance criteria** (testable scenarios)
- Both formats are optional; use when precision matters

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

### 6. JSON Schema for Capabilities

Create `schemas/capability.schema.json`:

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

### 7. Validation Tasks

```yaml
# taskfiles/spec.yml
tasks:
  validate:
    desc: Validate all specification contracts
    cmds:
      - task spec:schemas
      - task spec:frontmatter
      - task spec:adr-coverage
      - task spec:token-budgets

  schemas:
    desc: Validate YAML against JSON schemas
    cmds:
      - "{{.PYTHON}} scripts/validate-schemas.py"

  adr-coverage:
    desc: Check test-to-ADR traceability
    cmds:
      - "{{.PYTHON}} scripts/adr-test-coverage.py"

  token-budgets:
    desc: Verify rule packs within token limits
    cmds:
      - "{{.PYTHON}} scripts/check-token-budgets.py"
```

### 8. Specification Effectiveness Metrics

Track specification quality with measurable metrics:

```yaml
specification_metrics:
  # Token efficiency
  token_efficiency:
    description: "Rule pack token consumption"
    soft_target: 500
    maximum: 800
    measurement: "tiktoken cl100k_base encoding"
    validation: "scripts/check-token-budgets.py"

  # Specification coverage
  specification_coverage:
    description: "Percentage of plugins with governing ADR"
    target: ">90%"
    measurement: "Count plugins with ADR reference / total plugins"
    validation: "scripts/adr-plugin-coverage.py"

  # Agent success rate
  agent_success_rate:
    description: "AI agent tasks completing without clarification requests"
    target: ">80%"
    measurement: "Manual tracking in development sessions"
    tracking: "ADR analysis documents"

  # Test traceability
  test_traceability:
    description: "Tests with explicit ADR marker"
    target: ">70% for priority 1-2 tests"
    measurement: "grep -r '# ADR:' tests/ | wc -l"
    validation: "scripts/adr-test-coverage.py --threshold 70"

  # Schema coverage
  schema_coverage:
    description: "Core YAML structures with JSON Schema validation"
    target: ">80%"
    measurement: "schemas/*.schema.json coverage"
    validation: "scripts/schema-coverage.py"

  # Rule pack freshness
  rule_pack_freshness:
    description: "Rule packs updated within last 90 days"
    target: ">80%"
    measurement: "git log --since='90 days ago' docs/ai/rules/"
```

**Metrics Dashboard:** Implement via `task spec:metrics` for CI visibility.

## Consequences

### Positive

1. **Formal traceability**: ADR → Rule → Schema → Test chain is explicit
2. **AI efficiency**: llms.txt + frontmatter enable optimal context loading
3. **Executable specs**: Gherkin criteria can be automated with pytest-bdd
4. **Schema validation**: Structural errors caught before runtime
5. **Token predictability**: Rule packs have declared budgets

### Negative

1. **Migration effort**: 5 key ADRs need acceptance criteria conversion (reduced scope)
2. **Maintenance overhead**: More artifacts to keep synchronized
3. **Learning curve**: Gherkin syntax is optional, reducing barrier

### Neutral

1. **Tooling**: May require pytest-bdd or similar for full BDD
2. **CI time**: Additional validation steps increase pipeline duration

## Alternatives Considered

### 1. Keep Current ADR-Only Approach

Rejected: Lacks formal acceptance criteria and test traceability.

### 2. Full IEEE 29148 Compliance

Rejected: Overkill for infrastructure project; ADRs are sufficient for decisions.

### 3. OpenAPI-Style Specification

Rejected: Designed for APIs, not infrastructure topology.

## Implementation Plan

| Phase | Scope | Effort |
|-------|-------|--------|
| P1 | Create llms.txt + llms-full.txt, add frontmatter to rule packs | 3h |
| P2 | Add ADR markers to key tests (~50 files) | 1h |
| P3 | Create capability JSON Schema | 2h |
| P4 | Convert 5 key ADRs to Gherkin + EARS | 5h |
| P5 | Add spec validation tasks + CI workflow | 4h |
| P6 | Document specification contract | 2h |
| P7 | Implement specification metrics dashboard | 1h |

**Total: ~18 hours**

### Key ADRs for Gherkin Conversion (P4)

1. **ADR 0062** — Modular topology architecture (foundational)
2. **ADR 0080** — Unified build pipeline (plugin runtime)
3. **ADR 0088** — Semantic keyword registry (data model)
4. **ADR 0106** — Capability-driven plugins (recent, active)
5. **ADR 0108** — This ADR (self-documenting)

## References

- [Thoughtworks: Spec-Driven Development 2025](https://www.thoughtworks.com/insights/blog/spec-driven-development)
- [ISO/IEC/IEEE 29148:2018](https://www.reqview.com/doc/iso-iec-ieee-29148-templates/)
- [llms.txt Specification](https://llmstxt.org/)
- [Cucumber BDD](https://cucumber.io/docs/bdd/)
- ADR 0088: Capability Catalog Structure
- ADR 0106: Capability-Driven Plugin Architecture

## SPC Analysis Complete

**Date:** 2026-06-19
**Mode:** Strict Process Compliance (SPC)

### Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D1: Token budget | 800 (soft 500) | Accommodates complex domains |
| D2: Test marker scope | Key tests (~50) | Effort reduction 4h→1h |
| D3: Gherkin adoption | Optional | Gradual, low barrier |
| D4: ADR conversion | 5 key ADRs | Effort reduction 8h→4h |

### Revised Metrics

| Metric | Original | Revised | Final |
|--------|----------|---------|-------|
| Total effort | 22h | 15h | 18h |
| Test files to mark | 248 | ~50 | ~50 |
| ADRs to convert | 10 | 5 | 5 |
| Token budget | 500 | 800 (soft 500) | 800 (soft 500) |

### Industry Enhancements Added

| Enhancement | Source | Value |
|-------------|--------|-------|
| EARS templates | GitHub Spec Kit 2026 | Unambiguous requirements syntax |
| Specification metrics | Confident AI framework | Measurable effectiveness |
| llms-full.txt | llmstxt.org standard | Deep context for AI agents |
| CI workflow | Industry SDD practices | Automated validation |
