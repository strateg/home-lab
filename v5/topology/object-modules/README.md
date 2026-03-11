# Object Modules (v5)

This directory contains object contracts for ADR 0062 (`Class -> Object -> Instance`).
Objects inherit layer placement from their class (`v5/topology/layer-contract.yaml`) unless they define a narrower `topology.allowed_layers` override.

Current object groups:

- `mikrotik/` (existing router objects)
- `glinet/` (travel-router object)
- `proxmox/` (hypervisor + LXC object family)
- `orangepi/` (edge-node object)
- `cloud/` (cloud VM objects)
- `power/` (UPS/PDU objects)
- `service/` (L5 service objects)

Rules reflected in templates:

- object declares `class_ref`
- object enables capabilities via direct IDs and/or capability packs
- vendor-only behavior is namespaced under `vendor.*`

Validation (legacy checker, run with explicit v5 paths):

```bash
python v5/topology-tools/check-capability-contract.py \
  --catalog v5/topology/class-modules/classes/router/capability-catalog.yaml \
  --packs v5/topology/class-modules/classes/router/capability-packs.yaml \
  --classes-dir v5/topology/class-modules/classes \
  --objects-dir v5/topology/object-modules
```
