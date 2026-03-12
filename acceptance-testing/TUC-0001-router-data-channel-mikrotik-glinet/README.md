# TUC-0001 Router Data Link + Data Channel

This TUC validates OSI-aligned modeling of two router instances where:
- an ethernet cable instance models physical connectivity as `class.network.physical_link` (L1),
- an ethernet channel instance models information flow as `class.network.data_link` (L2),
- the cable instance explicitly references the channel it creates.

## Quick Facts

- **Status:** `passed` (2026-03-11)
- **TUC Test File:** `v5/tests/plugin_integration/test_tuc0001_router_data_link.py` (`9 passed`)
- **Regression:** plugin integration regression suite green (see `EVIDENCE-LOG.md`)
- **Evidence:** Compile runs with zero errors; determinism validated; all validators operational

## Why This Matters

This TUC demonstrates:
1. **Multi-layer modeling**: OSI-separated L1 (physical) and L2 (logical) as distinct classes/objects/instances.
2. **Cross-layer linkage**: Cables create channels; channels reference cables; endpoints must align bidirectionally.
3. **Instance-specific properties**: Cable length, shielding, color are per-instance while object defines nominal properties.
4. **Deterministic validation**: Plugin validators enforce contracts consistently across compile runs.
5. **Plugin extensibility**: Custom validators per object module (MikroTik port naming, GL.iNet DSA rules, etc.).

## What Gets Tested

- ✅ Valid cable + channel between real routers compiles without error
- ✅ Unknown endpoint device is caught with stable diagnostic code
- ✅ Invalid port names are rejected for each router type
- ✅ Cable/channel reference integrity is enforced
- ✅ Instance-specific properties (`length_m`, `shielding`, `category`) are preserved
- ✅ Plugin order and output remain deterministic across repeated runs
- ✅ No regressions in existing plugin contract/integration tests

## How to Run

See `IMPLEMENTATION-PLAN.md` for Workstream 5 and `TEST-MATRIX.md` for test scenarios.

## Related ADRs

- `adr/0062-modular-topology-architecture-consolidation.md` (class/object/instance architecture)
- `adr/0063-plugin-microkernel-for-compiler-validators-generators.md` (plugin runtime)
- `adr/0068-object-yaml-as-instance-template-with-explicit-overrides.md` (instance overrides)
- `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md` (plugin-first cutover)
- `adr/0071-sharded-instance-files-and-flat-instances-root.md` (instance storage layout)
