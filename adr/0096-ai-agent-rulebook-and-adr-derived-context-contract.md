# ADR 0096: AI Agent Rulebook and ADR-Derived Context Contract

**Status:** Proposed  
**Date:** 2026-04-10  
**Depends on:** ADR 0062, ADR 0063, ADR 0065, ADR 0066, ADR 0075, ADR 0076, ADR 0077, ADR 0080, ADR 0081, ADR 0086, ADR 0088, ADR 0094, ADR 0095

---

## Context

The repository has a large and mature ADR corpus. This is a strength for correctness, but it creates a cognitive-load problem for both humans and AI coding agents:

- too many authoritative sources must be read before routine changes;
- `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md` overlap but are not a single canonical contract;
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

Agent-specific instruction files (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, and future equivalents) MUST be treated as adapters/bootloaders. They may summarize and route, but they MUST NOT become divergent sources of architectural truth.

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

### D3. Context Loading Tiers

The rule system uses three tiers:

1. **Always-load boot rules**: small set of non-negotiable repo invariants.
2. **Scoped rule packs**: loaded only when a task touches matching files or domains.
3. **ADR deep read**: used only when a rule is ambiguous, a new architectural decision is needed, or the requested change modifies the rule contract itself.

### D4. Claude Code Consumption

`CLAUDE.md` SHOULD be updated to explicitly point to `docs/ai/AGENT-RULEBOOK.md` and `docs/ai/ADR-RULE-MAP.yaml`.

Claude Code SHOULD:

- load the universal rulebook before code or topology changes;
- use scoped rule packs based on touched paths;
- avoid duplicating the full rulebook inline in `CLAUDE.md`;
- treat `docs/ai/ADR-RULE-MAP.yaml` as the compact implementation decision index.

### D5. Validation Direction

Initial rollout is documentation-first. A follow-up validation gate SHOULD verify:

- all `source_adr` IDs exist in `adr/REGISTER.md`;
- all referenced rule pack files exist;
- rule IDs are unique;
- each rule has at least one trigger and one validation mechanism;
- `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md` route to the universal rulebook.

The proposed future task name is:

`task validate:agent-rules`

### D6. Non-Goals

This ADR does not:

- replace ADRs;
- remove `contract.md`;
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

- Keep ADRs as final authority.
- Keep `docs/ai/ADR-RULE-MAP.yaml` small and source-linked.
- Add validation before treating rule registry as enforceable.
- Use scoped rule packs instead of one large prompt.

---

## Rollout Plan

1. Add initial `docs/ai/` rulebook, registry, and scoped rule packs.
2. Update `adr/REGISTER.md`.
3. Update `AGENTS.md` and `CLAUDE.md` to reference the universal rulebook.
4. Add a future validation task and schema if rulebook drift becomes recurring.
5. Optionally add an MCP resource/export later for agent-native retrieval.

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
- Claude Code instructions reference the universal rulebook as the canonical source.

---

## References

- Docs: `docs/ai/AGENT-RULEBOOK.md`
- Docs: `docs/ai/ADR-RULE-MAP.yaml`
- Docs: `AGENTS.md`
- Docs: `CLAUDE.md`
- Docs: `.github/copilot-instructions.md`
