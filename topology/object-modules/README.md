# Object Modules (Capability Templates)

This directory contains object-level templates for Class -> Object -> Instance mapping.

Object templates:

- `mikrotik/obj.mikrotik.chateau_lte7_ax.yaml`
- `mikrotik/obj.mikrotik.chr.yaml`

Rules reflected in templates:

- object declares `class_ref`
- object enables capabilities via direct IDs and/or capability packs
- vendor-only behavior is namespaced under `vendor.*`

Validation:

```bash
python topology-tools/check-capability-contract.py
```
