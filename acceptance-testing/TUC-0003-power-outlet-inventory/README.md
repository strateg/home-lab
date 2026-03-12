# TUC-0003 Power Outlet Inventory

This TUC validates `power.outlet_ref` against source object outlet inventory.

## Quick Facts

- **Status:** `passed` (2026-03-12)
- **Primary Tests:** `test_l1_power_source_refs.py`, `test_tuc0003_power_outlet_inventory.py`
- **Primary Diagnostic:** `E7806`

## Scope

- source outlet declaration in power objects,
- runtime validation that `outlet_ref` exists in declared inventory,
- deterministic diagnostics for outlet mismatch.

## Dependencies

- Consumes L1 power-chain baseline from `TUC-0002-l1-power-source-chain`.
