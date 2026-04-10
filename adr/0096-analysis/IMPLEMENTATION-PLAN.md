# ADR 0096 Implementation Plan

**Date:** 2026-04-10
**Scope:** ADR0096 rulebook hardening after repeat analysis
**Mode:** SPC Step 6 approved implementation plan

---

## Objective

Bring ADR0096 analysis and implementation artifacts into alignment with the current repository state:

- validation tooling and JSON schema already exist;
- rulebook metrics must reflect measured repository data;
- all active agent adapters must route to the universal rulebook;
- stale strict 4-level plugin-boundary language must not remain in Codex-local adapters;
- validator and tests must catch adapter drift.

---

## Wave 1 - Analysis And ADR Refresh

| Task | Files | Acceptance |
|---|---|---|
| Refresh SWOT with current facts | `adr/0096-analysis/SWOT-ANALYSIS.md` | No stale claims that validator/schema/task are missing |
| Add implementation plan | `adr/0096-analysis/IMPLEMENTATION-PLAN.md` | Plan captures waves, file scope, gates, and acceptance criteria |
| Update ADR0096 validation state | `adr/0096-ai-agent-rulebook-and-adr-derived-context-contract.md` | D5 and rollout wording reflect implemented validation gate |
| Update ADR governance rule-pack validation text | `docs/ai/rules/adr-governance.md` | Rule pack no longer describes `validate:agent-rules` as future-only |

---

## Wave 2 - Adapter Alignment

| Task | Files | Acceptance |
|---|---|---|
| Convert Codex bootloader to rulebook adapter | `.codex/AGENTS.md` | References `docs/ai/AGENT-RULEBOOK.md` and `docs/ai/ADR-RULE-MAP.yaml` |
| Convert Tech Lead role file to rulebook overlay | `.codex/rules/tech-lead-architect.md` | Preserves role-specific review behavior without becoming separate architectural truth |
| Remove stale plugin ACL semantics | `.codex/AGENTS.md`, `.codex/rules/tech-lead-architect.md` | No old strict 4-level plugin-boundary enforcement text remains |

---

## Wave 3 - Validation Hardening

| Task | Files | Acceptance |
|---|---|---|
| Extend adapter checks | `scripts/validation/validate_agent_rules.py` | Validator checks root, Claude, Copilot, and Codex-local adapters |
| Require rulebook and rule-map references | `scripts/validation/validate_agent_rules.py` | Adapter drift is reported by `task validate:agent-rules` |
| Block stale plugin boundary text | `scripts/validation/validate_agent_rules.py`, `tests/test_agent_instruction_sync.py` | Tests and validator fail on old strict 4-level plugin-boundary text |
| Strengthen adapter sync tests | `tests/test_agent_instruction_sync.py` | Tests cover universal rulebook references and stale-token exclusion |

---

## Validation Gates

| Gate | Command |
|---|---|
| Agent rule validation | `task validate:agent-rules-strict` |
| ADR consistency | `task validate:adr-consistency` |
| Adapter sync regression | `.venv/bin/python -B -m pytest -o addopts= tests/test_agent_instruction_sync.py -q -p no:cacheprovider` |

---

## Out Of Scope

- No generated artifact edits.
- No topology/model/runtime behavior changes.
- No new ADR number; ADR0096 remains the governing decision.
- No MCP export implementation in this pass.
- No full ADR-to-rule coverage report in this pass.
