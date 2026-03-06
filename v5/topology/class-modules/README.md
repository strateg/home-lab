# Class Modules (v5)

This directory contains v5 class contracts for ADR 0062 (`Class -> Object -> Instance`).

Current contents:

- capability catalog template (`capability-catalog.example.yaml`)
- capability packs template (`capability-packs.example.yaml`)
- class contracts under `classes/`:
  - `network/`
  - `compute/`
  - `power/`
  - `service/`

Capability contract checker (legacy script, run with explicit v5 paths):

```bash
python v4/topology-tools/check-capability-contract.py \
  --catalog v5/topology/class-modules/capability-catalog.example.yaml \
  --packs v5/topology/class-modules/capability-packs.example.yaml \
  --classes-dir v5/topology/class-modules/classes \
  --objects-dir v5/topology/object-modules
```
