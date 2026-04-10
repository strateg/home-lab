# AI Rule Pack: ADR Governance

Load when changing:

- `adr/**`
- `docs/ai/**`
- `AGENTS.md`
- `CLAUDE.md`
- `.github/copilot-instructions.md`
- architecture plans or rulebook semantics

## Rules

1. One architecture decision should have one ADR.
2. Update `adr/REGISTER.md` with new or changed ADR status.
3. Use analysis directories for large supporting work rather than bloating ADR files.
4. Keep agent-specific instruction files as adapters to the universal rulebook.
5. Do not create divergent architectural truth in `AGENTS.md`, `CLAUDE.md`, or `.github/copilot-instructions.md`.
6. When compressing ADRs into rules, preserve source ADR references.
7. If a compact rule conflicts with an ADR, the ADR wins.

## Validation

- `task validate:adr-consistency`
- future `task validate:agent-rules`

## ADR Sources

- ADR0080
- ADR0095
- ADR0096

Template reference: `adr/0000-template.md`
