---
"@pack": adr-governance
"@version": 1.0
"@tokens": ~525
"@adr": [0080, 0095, 0096]
---

# AI Rule Pack: ADR Governance

## Quick Reference

| Rule | Key Point |
|------|-----------|
| One decision = one ADR | Never split or merge arbitrarily |
| REGISTER.md | Index only: update the ADR's table row (Status/Date/Supersedes) when it changes. Never append narrative, decisions, or dated work-log entries there - those belong in the ADR's own `adr/NNNN-analysis/` directory |
| Adapters | Reference rulebook only, no divergent content |
| Conflicts | ADR wins over compact rules |
| AI commits | Include `AI-Agent` and `AI-Tokens` metadata |

## Load When

- `adr/**`, `docs/ai/**`
- `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`
- Architecture plans or rulebook semantics

## ADR Workflow

| Step | Action | Artifact |
|------|--------|----------|
| 1 | Create ADR | `adr/NNNN-short-title.md` |
| 2 | Update register row | `adr/REGISTER.md` (table row only - Status/Date/Supersedes, not narrative) |
| 3 | Analysis (if large) | `adr/NNNN-analysis/` directory |
| 4 | Update rules | `docs/ai/rules/*.md` if affected |
| 5 | Validate | `task validate:adr-consistency` |

## Rule Priority

| Level | Source | Authority |
|-------|--------|-----------|
| 1 | ADRs | Final authority |
| 2 | AGENT-RULEBOOK.md | Derived from ADRs |
| 3 | Rule packs | Domain extensions |
| 4 | Adapters | Hints only |

## Iterative Refinement Process

Add or update rules when:

| Trigger | Action |
|---------|--------|
| New ADR accepted | Add to relevant pack `source_adr` |
| ADR superseded | Update rule pack, mark old rules |
| AI repeats same mistake | Add specific rule to prevent |
| Validation drift | Sync rule pack with ADR intent |

## Review Checklist

| Check | Command |
|-------|---------|
| ADR consistency | `task validate:adr-consistency` |
| Agent rules | `task validate:agent-rules` |
| Strict mode | `task validate:agent-rules-strict` |
| Coverage | `task validate:agent-rule-coverage` |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Divergent adapters | Creates multiple truths | Reference rulebook only |
| Bloated ADR files | Hard to maintain | Use analysis directories |
| Missing AI metadata | Breaks accountability | Add AI-Agent, AI-Tokens |
| Rule without source_adr | Untraceable | Link to ADRs |
| Dated narrative appended to REGISTER.md | Turns the ADR index into an unbounded work log (ADR 0118/0119 accumulated 1,000+ lines this way before being moved out, 2026-09-30) | Table row update only; narrative goes in `adr/NNNN-analysis/` |

## Validation

```bash
task validate:adr-consistency
task validate:agent-rules
task validate:agent-rules-strict
```

Template: `adr/0000-template.md`
