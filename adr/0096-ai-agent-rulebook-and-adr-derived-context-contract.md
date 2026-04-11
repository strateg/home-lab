# ADR 0096: AI Agent Rulebook and ADR-Derived Context Contract

**Status:** Implemented (Waves 1-3 complete, see `adr/0096-analysis/STATUS-REPORT.md`)
**Date:** 2026-04-10
**Implementation Completion:** 2026-04-10
**Depends on (direct):** ADR 0062, ADR 0063, ADR 0065, ADR 0066, ADR 0075, ADR 0076, ADR 0077, ADR 0080, ADR 0081, ADR 0086, ADR 0088, ADR 0094, ADR 0095
**Depends on (transitive via rule packs):** ADR 0067, ADR 0068, ADR 0069, ADR 0070, ADR 0071, ADR 0078, ADR 0079, ADR 0083, ADR 0084, ADR 0085, ADR 0087, ADR 0089, ADR 0090, ADR 0091, ADR 0092, ADR 0093

---

## Context

The repository has a large and mature ADR corpus. This is a strength for correctness, but it creates a cognitive-load problem for both humans and AI coding agents:

- too many authoritative sources must be read before routine changes;
- `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, and Codex-local adapters overlap but are not a single canonical contract;
- agent context windows are consumed by repeated architectural background;
- repeated implementation tasks require the same project-specific rules, but those rules are not available as a compact machine-readable decision layer;
- different AI agents may consume different instruction files, which risks inconsistent behavior.

The project needs a universal, agent-neutral rule layer derived from ADR decisions. Claude Code is a primary consumer, but the contract must also be usable by Codex, GitHub Copilot, Cursor-like agents, and future MCP/resource-based agents.

---

## Problem Statement

Create a compact and repeatable rule system that:

1. reduces token load at agent startup;
2. gives agents an accurate implementation map for common change types;
3. preserves ADR authority without forcing agents to reread the full ADR corpus every turn;
4. separates always-load rules from scoped, on-demand rule packs;
5. remains auditable against ADR sources;
6. avoids making Claude-specific files the only source of truth.

---

## Decision

Adopt a universal AI agent rulebook contract under `docs/ai/`.

### D1. Canonical Rulebook Location

The canonical agent rule layer lives in:

- `docs/ai/AGENT-RULEBOOK.md` — human-readable compact rulebook;
- `docs/ai/ADR-RULE-MAP.yaml` — machine-readable rule registry;
- `docs/ai/rules/*.md` — scoped rule packs by domain.

Agent-specific instruction files (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/AGENTS.md`, `.codex/rules/*.md`, and future equivalents) MUST be treated as adapters/bootloaders. They may summarize and route, but they MUST NOT become divergent sources of architectural truth.

### D2. Rule Shape

Each rule SHOULD have:

- stable `id`;
- `scope`;
- `trigger`;
- `must`;
- `never`;
- `validate`;
- `source_adr`;
- optional `files_glob`;
- optional `rule_pack`.

The machine-readable registry is the authoritative compact contract for automated checks and future generation.
It also owns the active adapter registry and required boot references used by validation, so adapter inventory does not drift into validator-local constants.
Schema evolution for this registry is governed by `adr/0096-analysis/SCHEMA-VERSION-POLICY.md`.

### D3. Context Loading Tiers

The rule system uses three tiers:

1. **Always-load boot rules**: small set of non-negotiable repo invariants.
2. **Scoped rule packs**: loaded only when a task touches matching files or domains.
3. **ADR deep read**: used only when a rule is ambiguous, a new architectural decision is needed, or the requested change modifies the rule contract itself.

### D4. Agent Adapter Consumption

`CLAUDE.md` SHOULD be updated to explicitly point to `docs/ai/AGENT-RULEBOOK.md` and `docs/ai/ADR-RULE-MAP.yaml`.

Agent-specific adapters SHOULD:

- load the universal rulebook before code or topology changes;
- use scoped rule packs based on touched paths;
- avoid duplicating the full rulebook inline in adapter files;
- treat role-specific files as overlays, not sources of architectural truth;
- treat `docs/ai/ADR-RULE-MAP.yaml` as the compact implementation decision index.

### D5. Validation Direction

Initial rollout was documentation-first. The validation gate is now implemented and SHOULD verify:

- all `source_adr` IDs exist in `adr/REGISTER.md`;
- all referenced rule pack files exist;
- rule IDs are unique;
- each rule has at least one trigger and one validation mechanism;
- adapter inventory is declared in `docs/ai/ADR-RULE-MAP.yaml`;
- active adapter files route to the universal rulebook and rule map;
- adapter files do not preserve stale plugin-boundary semantics superseded by ADR0086.

The validation tasks are:

- `task validate:agent-rules`
- `task validate:agent-rules-strict`
- `task validate:agent-rule-coverage` (diagnostic reverse coverage report; non-gating)
- `task validate:agent-rule-mcp-export` (diagnostic MCP-style resource catalog export; non-gating)
- `task validate:agent-rule-mcp-server` (diagnostic stdio server smoke-check; non-gating)

### D6. Non-Goals

This ADR does not:

- replace ADRs;
- remove `docs/ai/spc-contract.md` (SPC protocol remains a separate analysis tool);
- require all agents to support MCP;
- make AI-generated changes authoritative without validation;
- introduce autonomous AI promotion;
- change production runtime behavior.

---

## Consequences

### Positive

- Lower startup token usage for AI agents.
- More repeatable implementation behavior across Claude Code, Codex, Copilot, and future agents.
- Clearer distinction between canonical rules and historical ADR background.
- Better onboarding for human maintainers.
- Future validation/generation possible from a structured rule registry.

### Negative / Trade-offs

- Rulebook can drift from ADRs unless validated.
- Over-compression can lose nuance from full ADRs.
- Maintaining adapter files adds one more governance surface.
- Scoped rule loading requires agent discipline or tooling support.

### Risk Controls

| Risk | Control | Metric / Threshold |
|------|---------|-------------------|
| Rulebook drift from ADRs | Keep ADRs as final authority; source_adr traceability | 100% of rules have valid source_adr |
| Token bloat | Keep rulebook compact; use scoped rule packs | Rulebook < 10% of ADR corpus token count |
| Registry complexity | Keep ADR-RULE-MAP.yaml small and source-linked | < 20 always-load rules; < 50 total rules |
| Unenforced rules | Enforce validation task before closure | `task validate:agent-rules` passes |
| Adapter divergence | Regular sync audit | All adapters reference universal rulebook |

---

## Rollout Plan

1. Add initial `docs/ai/` rulebook, registry, and scoped rule packs.
2. Update `adr/REGISTER.md`.
3. Update `AGENTS.md` and `CLAUDE.md` to reference the universal rulebook.
4. Add validation task and schema for rulebook drift detection.
5. Align Codex-local adapters with the universal rulebook contract.
6. Optionally add an MCP resource/export later for agent-native retrieval.

---

## Acceptance Criteria

- `docs/ai/AGENT-RULEBOOK.md` exists and is usable as a compact agent boot context.
- `docs/ai/ADR-RULE-MAP.yaml` exists and maps rules to ADR sources.
- At least the core rule packs exist:
  - `plugin-runtime.md`
  - `topology-model.md`
  - `deploy-domain.md`
  - `generator-artifacts.md`
  - `secrets.md`
  - `adr-governance.md`
  - `testing-ci.md`
  - `acceptance-tuc.md`
- `adr/REGISTER.md` contains ADR 0096.
- Claude Code, Codex-local, and Copilot instructions reference the universal rulebook as the canonical source.

---

## References

- Docs: `docs/ai/AGENT-RULEBOOK.md`
- Docs: `docs/ai/ADR-RULE-MAP.yaml`
- Docs: `docs/ai/spc-contract.md` (SPC protocol — separate analysis tool)
- Docs: `docs/ai/rules/*.md` (scoped rule packs)
- Adapters: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/AGENTS.md`, `.codex/rules/*.md`
- Analysis: `adr/0096-analysis/` (SWOT, implementation plan, gap analysis)
