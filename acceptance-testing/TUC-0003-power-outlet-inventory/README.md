# TUC-0003 Power Outlet Inventory

This TUC validates `power.outlet_ref` against source object outlet inventory.

Scope:
- source outlet declaration in power objects,
- runtime validation that `outlet_ref` exists in declared inventory,
- deterministic diagnostics for outlet mismatch.
