# TUC-0002: L1 Power Source Chain (Router -> PDU -> UPS)

## Metadata

- `id`: `TUC-0002`
- `status`: `passed` (2026-03-12)
- `owner`: `topology-tools`
- `created_at`: `2026-03-12`
- `target_date`: `2026-03-19`
- `related_adrs`:
  - `adr/0062-modular-topology-architecture-consolidation.md`
  - `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
  - `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`
  - `adr/0071-sharded-instance-files-and-flat-instances-root.md`

## Objective

Prove that L1 power topology is modeled and validated via `power.source_ref` with deterministic diagnostics.

## Scope

- In scope:
  - L1 relation `power.source_ref` (`L1 -> L1`)
  - Source class constraints (`class.power.pdu` or `class.power.ups`)
  - Outlet occupancy checks (`power.outlet_ref` collision detection)
  - Cycle detection in power graph
  - Compile-time preservation of power bindings in effective model
- Out of scope:
  - Physical outlet inventory schema on source objects
  - Electrical load/capacity simulation
  - L2+ data-channel behavior

## Preconditions

- Plugin-first runtime is active.
- Sharded instance source mode is active.
- L1 instances exist for `rtr-mikrotik-chateau`, `rtr-slate`, `pdu-rack`, `ups-main`.

## Inputs

- Topology/model files:
  - `v5/topology/topology.yaml`
  - `v5/topology/instances/l1_devices/rtr-mikrotik-chateau.yaml`
  - `v5/topology/instances/l1_devices/rtr-slate.yaml`
  - `v5/topology/instances/l1_devices/pdu-rack.yaml`
- Plugin manifests:
  - `v5/topology-tools/plugins/plugins.yaml`
- Tests:
  - `v5/tests/plugin_integration/test_l1_power_source_refs.py`
  - `v5/tests/plugin_integration/test_tuc0002_l1_power_source_chain.py`

## Expected Outcomes

- `power.source_ref` relation is validated by dedicated plugin with `E78xx` diagnostics.
- Invalid relations (unknown target, wrong layer/class, bad format, cycle, outlet collision) fail deterministically.
- Valid chain (`router -> pdu -> ups`) compiles with zero errors/warnings.
- `instance_data.power.*` remains present in effective JSON for related L1 rows.

## Acceptance Criteria

1. Valid chain compiles successfully with `errors=0`, `warnings=0`.
2. `rtr-mikrotik-chateau` and `rtr-slate` reference `pdu-rack`; `pdu-rack` references `ups-main`.
3. `base.validator.power_source_refs` emits stable codes `E7801..E7805` for invalid scenarios.
4. Compile output preserves `power.source_ref` and `power.outlet_ref` fields for L1 instances.

## Risks and Open Questions

- Outlet inventory is not yet modeled in source objects; validation is string-level + occupancy only.
- Future TUC should formalize outlet catalog and compatibility checks.
