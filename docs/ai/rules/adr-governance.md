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
8. If `docs/ai/ADR-RULE-MAP.yaml` schema semantics change, update `adr/0096-analysis/SCHEMA-VERSION-POLICY.md` in the same change set.

## Validation

- `task validate:adr-consistency`
- `task validate:agent-rules`
- `task validate:agent-rules-strict` when adapter/rulebook drift must fail on warnings
- `task validate:agent-rule-coverage` for reverse ADR-to-rule coverage diagnostics
- `task validate:agent-rule-mcp-export` for MCP-style export catalog generation
- `task validate:agent-rule-mcp-server` for stdio MCP server smoke checks

## Rulebook Maintenance Review

Review rulebook and rule packs when:

1. New ADR is accepted that affects a rule pack domain.
2. Existing ADR is superseded or significantly updated.
3. Validation reveals drift between rule pack content and source ADRs.
4. Agent behavior suggests rules are incomplete or misleading.

Review checklist:

- [ ] Rule pack `source_adr` includes all relevant ADRs.
- [ ] Rule `source_adr` aligns with pack `source_adr` where appropriate.
- [ ] Rule pack markdown accurately summarizes ADR intent.
- [ ] `files_glob` patterns correctly trigger the rule pack.
- [ ] Adapter files still route to universal rulebook without divergence.
- [ ] `task validate:agent-rules` passes.
- [ ] `task validate:agent-rules-strict` passes (no warnings).

## ADR Sources

- ADR0080
- ADR0095
- ADR0096

Template reference: `adr/0000-template.md`
