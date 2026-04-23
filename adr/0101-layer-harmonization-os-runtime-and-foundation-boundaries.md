# ADR 0101: Layer Harmonization for OS Runtime and Foundation Boundaries

**Status:** Proposed
**Date:** 2026-04-23
**Depends on:** ADR 0062, ADR 0064, ADR 0071, ADR 0088

---

## Context

Current topology layering is OSI-like, but practical usage shows boundary blur between foundation and runtime concerns:

- `class.os` / `obj.os.*` / `inst.os.*` are currently placed in `L1`.
- `L1` device instances include data that belongs to higher concerns (network/runtime/service detail).
- Cloud VM objects are `L4`, while some cloud VM instances are currently authored in `L1`.
- `L2` VLAN instances include `host_os_ref`, coupling network allocation semantics to OS entity placement.

This increases cognitive load and weakens layer meaning for `class -> object -> instance` modeling.

---

## Decision

Adopt a harmonized layer contract with explicit concern boundaries:

1. **OS is a platform/runtime concern and belongs to `L4`**
   - `class.os` allowed layer: `L4`
   - `obj.os.*` layer: `L4`
   - `inst.os.*` layer/group mapping: `L4`

2. **`L1` is restricted to foundation concerns**
   - Physical device identity, hardware characteristics, power, physical links, firmware.
   - Runtime/network-policy/service internals are not canonical `L1` data.

3. **Cloud VM instances follow workload placement**
   - Instances extending `class.compute.workload.vm` are authored in `L4`.

4. **`L2` network allocations must not depend on OS placement**
   - Remove `host_os_ref` from `L2` VLAN allocation authoring.
   - Use endpoint references at device/workload level.

5. **Reference hygiene is required**
   - Normalize storage references to canonical names (`inst.storage.pool.*`).
   - Keep group/directory naming aligned with `layer-contract` mappings.

---

## Consequences

### Positive

- Clearer semantic boundary: foundation (`L1`) vs platform/runtime (`L4`).
- Reduced cross-layer conceptual coupling.
- More consistent placement for VM/cloud runtime entities.
- Better maintainability of topology authoring and validation rules.

### Trade-offs / Risks

- Requires coordinated migration across class/object/instance files.
- Existing validators and tests may require updates for moved `os` layer semantics.
- Transitional churn in topology diffs during migration window.

### Migration Impact

Migration is required for:

- `topology/layer-contract.yaml` (`group_layers`, `class_layers`)
- `topology/class-modules/software/class.os.yaml`
- all `topology/object-modules/software/obj.os.*.yaml`
- all project OS instances currently under `L1-foundation/os/`
- cloud VM instance placement authored under `L1`
- `L2` VLAN instances with `host_os_ref`
- `L7` backup refs using non-canonical pool instance IDs

---

## Validation

Minimum gates after migration implementation:

- `.venv/bin/python scripts/orchestration/lane.py validate-v5`
- `task validate:default`
- `task test:plugin-contract`

Recommended integrity checks:

- no `obj.os.*` or `inst.os.*` in `L1`
- no `host_os_ref` in `L2` VLAN instance files
- no `inst.pool.*` legacy storage refs

---

## References

- `topology/layer-contract.yaml`
- `topology/class-modules/software/class.os.yaml`
- `topology/object-modules/software/obj.os.*.yaml`
- `projects/home-lab/topology/instances/L1-foundation/os/*.yaml`
- `projects/home-lab/topology/instances/L2-network/network/inst.vlan.*.yaml`
- `projects/home-lab/topology/instances/L7-operations/operations/backup-*.yaml`
