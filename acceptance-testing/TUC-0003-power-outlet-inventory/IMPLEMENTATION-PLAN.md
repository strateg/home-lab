# Implementation Plan

## Workstreams

1. Extend power object modules with outlet inventory.
2. Enforce inventory-aware validation in `power_source_refs` plugin.
3. Add regression tests and keep existing relation diagnostics stable.

## Tasks

1. Add `properties.power.outlets` to PDU/UPS power objects.
2. Add plugin check for unknown outlet with deterministic `E7806`.
3. Extend integration tests for valid and invalid outlet scenarios.

## Exit Criteria

1. Unknown `power.outlet_ref` fails with `E7806`.
2. Valid outlet refs pass.
3. Core compile/integration suites stay green.

## Rollback

- Remove `E7806` check from validator.
- Revert outlet inventory blocks from power object modules.
