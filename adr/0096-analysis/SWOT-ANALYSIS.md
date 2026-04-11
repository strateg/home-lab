# ADR 0096 SWOT Analysis

**Date:** 2026-04-10
**Analyst:** SPC Protocol Analysis
**Subject:** AI Agent Rulebook and ADR-Derived Context Contract
**Revision:** Updated after validation/schema/adapter hardening pass

---

## Executive Summary

ADR 0096 establishes a universal AI agent rulebook system that compresses ADR-derived repository rules into a compact, source-linked, machine-readable contract. The current implementation state is stronger than the initial SWOT baseline: the agent-rules validator, JSON schema, task wiring, and strict validation mode now exist and pass.

The main residual risk is no longer the absence of validation tooling. The active risk is adapter drift across all agent-specific entrypoints, especially non-primary adapters such as `.codex/AGENTS.md` and `.codex/rules/tech-lead-architect.md`.

---

## Current Evidence Snapshot

| Metric | Current Evidence |
|---|---:|
| Rule packs | 8 |
| Rules | 16 |
| Always-load CORE rules | 8 |
| Scoped rules | 8 |
| Direct ADR dependencies | 13 |
| Transitive ADR dependencies | 16 |
| Rulebook bundle size | 3,053 words / 25,261 bytes |
| ADR corpus size | 108,062 words / 904,449 bytes |
| Rulebook / ADR corpus ratio | 2.83% by words / 2.79% by bytes |
| `validate_agent_rules.py` | Present |
| `schemas/adr-rule-map.schema.json` | Present |
| `validate:agent-rules` task | Present |
| `validate:agent-rules-strict` task | Present |

---

## SWOT Matrix

### Strengths (Internal Positive)

| # | Strength | Impact | Evidence |
|---|---|---|---|
| S1 | Compact ADR-derived context | High | Rulebook bundle is 2.83% of the ADR corpus by words and 2.79% by bytes |
| S2 | ADR traceability | High | Registry rules and rule packs use `source_adr`; validator checks ADR IDs against `adr/REGISTER.md` |
| S3 | Machine-readable contract | High | `docs/ai/ADR-RULE-MAP.yaml` plus `schemas/adr-rule-map.schema.json` |
| S4 | Validation gate exists | High | `scripts/validation/validate_agent_rules.py` and `task validate:agent-rules*` are wired |
| S5 | Tiered loading model | Medium | Always-load CORE rules plus scoped rule packs by domain |
| S6 | Multi-agent adapter model | Medium | Root `AGENTS.md`, `CLAUDE.md`, and Copilot instructions route to universal rulebook |
| S7 | Domain coverage | High | 8 rule packs cover plugin runtime, topology, deploy, generators, secrets, ADR governance, testing/CI, and TUC |
| S8 | SPC separation | Medium | `docs/ai/spc-contract.md` remains a separate process contract |

---

### Weaknesses (Internal Negative)

| # | Weakness | Impact | Current Mitigation Status |
|---|---|---|---|
| W1 | Adapter drift surface is broader than primary adapters | High | Primary adapters are covered; Codex-local adapters require explicit validator/test coverage |
| W2 | Rule coverage is structural, not semantic | Medium | Validator checks schema, IDs, files, references, and adapter routing; it does not prove every ADR nuance is captured |
| W3 | Schema evolution remains governance-heavy | Medium | `adr/0096-analysis/SCHEMA-VERSION-POLICY.md` defines the epoch contract, but disciplined same-change-set updates are still required |
| W4 | Rule coverage reporting is diagnostic-only, not gating | Medium | `task validate:agent-rule-coverage` emits reverse coverage views, but no closure gate depends on them |
| W5 | Scoped loading still depends on agent behavior | Medium | Registry maps `files_glob`, but agents must still load packs correctly unless tooling enforces it |
| W6 | Dependency graph is broad | Low | ADR0096 references 29 ADRs total: 13 direct and 16 transitive |

---

### Opportunities (External Positive)

| # | Opportunity | Potential Impact | Feasibility |
|---|---|---|---|
| O1 | Extend MCP registration automation beyond Codex | Medium | The stdio server exists and Codex already has a setup helper; remaining wrappers can target Claude/Cursor/Copilot flows |
| O2 | Coverage-driven drift telemetry | High | Reverse coverage reports can be trended or compared across revisions |
| O3 | IDE/Copilot/Cursor context integration | Medium | Scoped rule packs can be loaded by path/domain match |
| O4 | Agent compliance telemetry | Medium | Validation outputs can become diagnostics for recurring adapter/rule drift |
| O5 | Cross-repo bootstrap pattern | Low | The rulebook model can be reused, but project-specific ADR content must remain local |

---

### Threats (External Negative)

| # | Threat | Risk Level | Current Mitigation |
|---|---|---|---|
| T1 | Adapter-specific drift | High | Expand adapter checks beyond root/Claude/Copilot entrypoints |
| T2 | ADR corpus growth | Medium | Tiered loading and rule packs reduce startup load; reverse coverage diagnostics now expose rulebook footprint |
| T3 | Over-compression | Medium | ADRs remain final authority; ADR deep read tier exists |
| T4 | Agent capability variance | Medium | Markdown/YAML formats are broadly consumable; behavior still varies by agent |
| T5 | Validation dependency availability | Low | `jsonschema` is declared in project dependencies; validator warns if unavailable |
| T6 | Security/secret exposure in AI workflows | Low | SEC-001 and secrets rule pack require redaction and encrypted/placeholder handling |

---

## TOWS Strategy Matrix

| Strategy Type | Strategy | Actions |
|---|---|---|
| SO | Use validation-backed traceability for MCP | Serve the exported rulebook catalog, rule map, and rule packs with ADR cross-references over the stdio server |
| SO | Use tiered rule packs for IDE context | Load scoped packs by changed path and rule map `files_glob` |
| WO | Close adapter drift gap | Validate all active adapter files, including `.codex/*`, for universal rulebook routing |
| WO | Operationalize ADR coverage reporting | Track reverse coverage diagnostics across revisions and use them to detect drift |
| ST | Preserve ADR authority under compression | Keep ADR deep-read tier and conflict rule in governance pack |
| ST | Detect stale plugin boundary language | Guard adapters against old strict 4-level plugin boundary text superseded by ADR0086 |
| WT | Enforce schema evolution discipline | Keep policy, schema, validator, and canonical rule map updated in the same change set |

---

## Prioritized Recommendations

| Priority | Recommendation | Addresses | Effort | Status |
|---|---|---|---|---|
| 1 | Expand adapter validation to include `.codex/AGENTS.md` and `.codex/rules/tech-lead-architect.md` | W1, T1 | Low | Targeted for this hardening pass |
| 2 | Remove stale strict 4-level plugin-boundary wording from Codex-local adapters | W1, T1 | Low | Targeted for this hardening pass |
| 3 | Update adapter sync tests to require universal rulebook routing and block stale plugin ACL text | W1, T1 | Low | Targeted for this hardening pass |
| 4 | Refresh ADR0096 wording from future validation direction to current implemented validation gate | W2 | Low | Targeted for this hardening pass |
| 5 | Extend registration automation beyond the Codex helper | O1 | Medium | Future work |

---

## Metrics Dashboard

| Metric | Target | Current | Status |
|---|---:|---:|---|
| Rules with valid `source_adr` | 100% | 100% | PASS |
| Rulebook size ratio | < 10% of ADR corpus | 2.83% words / 2.79% bytes | PASS |
| Always-load rules | < 20 | 8 | PASS |
| Total rules | < 50 | 16 | PASS |
| Rule packs | >= 8 core packs | 8 | PASS |
| JSON schema exists | Yes | Yes | PASS |
| Validation task implemented | Yes | Yes | PASS |
| Strict validation task implemented | Yes | Yes | PASS |
| ADR-to-rule coverage diagnostics | Yes | Yes | PASS |
| Adapter drift coverage | Active adapters covered | Root, Claude, Copilot, and Codex-local adapters covered | PASS |

---

## Conclusion

ADR 0096 is structurally sound and now has implemented validation/schema support plus reverse ADR-to-rule coverage diagnostics. Adapter drift hardening is complete for the active adapter set.

The next strategic improvement after this hardening pass is optional expansion of MCP registration helpers beyond Codex, with coverage diagnostics and schema policy available for ongoing drift review.
