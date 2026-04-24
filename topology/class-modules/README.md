# Class Modules (v5)

This directory contains v5 class contracts for ADR 0062 (`Class -> Object -> Instance`).
Layer placement for classes is governed by `v5/topology/layer-contract.yaml` (`class_layers` section).

Current contents:

- class contracts under `classes/`:
  - `router/`
  - `compute/`
  - `power/`
  - `service/`
- router capabilities/packs are colocated with router class:
  - `classes/router/capability-catalog.yaml`
  - `classes/router/capability-packs.yaml`
  - `classes/router/capability-id-migration.yaml`
- capability IDs use generalized network namespace: `cap.net.*`

Capability contract checker (legacy script, run with explicit v5 paths):

```bash
python v5/topology-tools/check-capability-contract.py \
  --catalog v5/topology/class-modules/L1-foundation/router/capability-catalog.yaml \
  --packs v5/topology/class-modules/L1-foundation/router/capability-packs.yaml \
  --classes-dir v5/topology/class-modules \
  --objects-dir v5/topology/object-modules
```
