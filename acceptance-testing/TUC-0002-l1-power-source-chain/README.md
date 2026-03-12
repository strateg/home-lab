# TUC-0002 L1 Power Source Chain

This TUC validates L1 lateral power wiring via `power.source_ref`:
- router instances draw power from PDU,
- PDU draws power from UPS,
- power bindings are preserved in compiled model.

## Quick Facts

- **Status:** `passed` (2026-03-12)
- **Primary Tests:** `test_tuc0002_l1_power_source_chain.py`, `test_l1_power_source_refs.py`
- **Evidence:** compile with zero errors/warnings; validator negative paths covered

## Related ADRs

- `adr/0062-modular-topology-architecture-consolidation.md`
- `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`
