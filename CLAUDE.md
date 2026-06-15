# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Universal AI Rulebook (Mandatory)

Load `docs/ai/AGENT-RULEBOOK.md` as the compact ADR-derived rulebook. Use `docs/ai/ADR-RULE-MAP.yaml` to select scoped rule packs before changing code, topology, deploy, tests, or ADRs.

This file is a Claude-specific adapter. It must not diverge from the universal rulebook.

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

**Execution Mode (ADR0097):** Plugins use `subinterpreter` mode by default (84/85 plugins). Declare `execution_mode` explicitly. Workers must not mutate pipeline-global state.

See `docs/ai/rules/plugin-runtime.md` for full rules.

## Deploy Domain (ADR0083-0085)

| Concept | Description |
|---------|-------------|
| Deploy bundle | Immutable execution input at `.work/deploy/bundles/<id>/` |
| Deploy runner | Workspace-aware backend (native/wsl/docker/remote) |
| Init-node | Device bootstrap orchestrator |

See `docs/guides/COMMON-WORKFLOWS.md` for commands.

## Secrets Management (ADR0072)

- SOPS with age encryption in `projects/home-lab/secrets/`
- Never commit plaintext secrets or include in commit messages
- Use `V5_SECRETS_MODE=passthrough` for validation without decryption
- Dynamic IP rule: Never store cloud VPS public IPs statically

See `docs/ai/rules/secrets.md` for full rules.

## ADR Policy

- One decision = one ADR in `adr/NNNN-short-title.md`
- Update `adr/REGISTER.md` with every change
- Large plans go in `adr/NNNN-analysis/` directories

## Working with Claude Code

**Do:**
- Check topology files first (source of truth)
- Run `lane.py validate-v5` after changes
- Follow plugin stage/manifest contracts
- Run `pytest tests -q` for validation

**Don't:**
- Edit `generated/` directly
- Break plugin contracts
- Skip validation steps

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

## SPC Mode (Optional)

For complex analysis, activate **Strict Process Compliance** mode by saying "SPC MODE" or "Работай по контракту". See `docs/ai/spc-contract.md` for the 7-step protocol.
