# Codex Agent Configuration

Load `docs/ai/AGENT-RULEBOOK.md` before any code changes.

## Quick Context

| Aspect | Value |
|--------|-------|
| Architecture | Infrastructure-as-Data, Class → Object → Instance |
| Source of truth | `topology/topology.yaml`, `topology/class-modules/`, `topology/object-modules/` |
| Project instances | `projects/home-lab/topology/instances/` |
| Generated outputs | `generated/` (DO NOT EDIT) |
| Principle | Edit topology → compile → generate → apply |

## Commands

```bash
.venv/bin/python topology-tools/compile-topology.py                                    # Compile
V5_SECRETS_MODE=passthrough .venv/bin/python scripts/orchestration/lane.py validate-v5 # Validate
python -m pytest tests -q                                                              # Test
```

## Codex-Specific

- **Role overlay:** `.codex/rules/tech-lead-architect.md`
- **Priority:** If conflict, ADRs and `docs/ai/AGENT-RULEBOOK.md` win

## References

- **Full rules:** `docs/ai/AGENT-RULEBOOK.md`
- **ADR routing:** `docs/ai/ADR-RULE-MAP.yaml`
- **Workflows:** `docs/guides/COMMON-WORKFLOWS.md`
- **SPC mode:** Say "SPC MODE" for formal analysis. See `docs/ai/spc-contract.md`

## Plugin Architecture

Applies to all plugin families (`discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`).

Runtime lifecycle has 6 stages: `discover -> compile -> validate -> generate -> assemble -> build`.

Stage affinity must be preserved: `discover -> discoverers`, `compile -> compilers`, `validate -> validators`, `generate -> generators`, `assemble -> assemblers`, `build -> builders`.

See ADR 0063 (Plugin Microkernel), ADR 0080 (6-stage pipeline), ADR 0106 (Capability-driven).
