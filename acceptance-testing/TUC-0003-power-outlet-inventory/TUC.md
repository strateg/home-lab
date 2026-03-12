# TUC-0003: Power Outlet Inventory Validation

## Metadata

- `id`: `TUC-0003`
- `status`: `passed` (2026-03-12)
- `owner`: `topology-tools`
- `created_at`: `2026-03-12`
- `target_date`: `2026-03-19`
- `related_adrs`:
  - `adr/0062-modular-topology-architecture-consolidation.md`
  - `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
  - `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`

## Objective

Ensure `power.outlet_ref` is validated against source object outlet inventory, not only by string format.

## Scope

- In scope:
  - Power object outlet inventory declaration in object properties
  - Runtime validation in `base.validator.power_source_refs`
  - Deterministic diagnostic `E7806` for outlet inventory mismatch
- Out of scope:
  - Electrical load/capacity constraints
  - Outlet state telemetry

## Preconditions

- L1 power relation validator plugin is enabled.
- Power source object modules define outlet inventory.

## Inputs

- `v5/topology/object-modules/power/obj.pdu.generic.managed.yaml`
- `v5/topology/object-modules/power/obj.apc.backups.650va.yaml`
- `v5/topology-tools/plugins/validators/power_source_refs_validator.py`
- `v5/tests/plugin_integration/test_l1_power_source_refs.py`
- `v5/tests/plugin_integration/test_tuc0003_power_outlet_inventory.py`

## Expected Outcomes

- Valid outlet references pass.
- Unknown outlet references fail with `E7806`.
- Existing `E7801..E7805` behavior remains stable.

## Acceptance Criteria

1. Power objects declare outlet inventory under `properties.power.outlets`.
2. `power.outlet_ref` not found in source inventory produces `E7806`.
3. Plugin integration tests pass with new outlet inventory checks.

## Risks and Open Questions

- Inventory schema is intentionally lightweight; richer outlet metadata may require a follow-up TUC.
