# GitHub Copilot Instructions

This file provides guidance when working with this repository.

## Universal AI Rulebook

Load `docs/ai/AGENT-RULEBOOK.md` as the compact ADR-derived rulebook. Use `docs/ai/ADR-RULE-MAP.yaml` to select scoped rule packs. This file is an adapter and must not diverge from the universal rulebook.

## SPC Mode (Optional)

For complex analysis, activate **Strict Process Compliance** mode with "SPC MODE" or "Работай по контракту". See `docs/ai/spc-contract.md`.

## V5 Architecture

**Infrastructure-as-Data** with **Class -> Object -> Instance** topology model.

| Component | Location |
|-----------|----------|
| Source of truth | `topology/topology.yaml`, `topology/class-modules/`, `topology/object-modules/` |
| Project instances | `projects/home-lab/topology/instances/` |
| Generated outputs | `generated/<project>/` (DO NOT EDIT) |

**Key principle:** Edit topology -> compile -> generate -> apply.

## Plugin Contract (ADR0086)

Runtime lifecycle: `discover -> compile -> validate -> generate -> assemble -> build`

Stage affinity enforced by manifest contracts (`depends_on`, `consumes`, `produces`).

See `docs/ai/rules/plugin-runtime.md` for execution modes and full rules.

## Key Rules

| Rule | Description |
|------|-------------|
| CORE-001 | Work in active root layout only |
| CORE-002 | Never edit `generated/` directly |
| CORE-003 | Preserve Class -> Object -> Instance model |
| CORE-004 | Preserve plugin stage affinity |
| CORE-006 | Keep secrets encrypted (SOPS/age) |
| CORE-007 | Update ADRs for architecture changes |

## ADR Policy

- One decision = one ADR in `adr/NNNN-short-title.md`
- Update `adr/REGISTER.md` with every change
- Large plans go in `adr/NNNN-analysis/` directories

## Quick Commands

```bash
# Compile
.venv/bin/python topology-tools/compile-topology.py

# Validate
V5_SECRETS_MODE=passthrough .venv/bin/python scripts/orchestration/lane.py validate-v5

# Test
python -m pytest tests -q
```

Full workflows: `docs/guides/COMMON-WORKFLOWS.md`

## Migration Lane Guard

- Active lane: `topology/`, `topology-tools/`, `projects/`, `tests/`, `scripts/`, `taskfiles/`
- Do not create root `v4/` or `v5/` directories
- Do not modify `archive/v4/` unless explicitly requested
