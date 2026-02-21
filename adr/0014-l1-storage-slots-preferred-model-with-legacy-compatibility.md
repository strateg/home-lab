# ADR 0014: Use L1 Storage Slots as Preferred Model with Legacy Compatibility

- Status: Accepted
- Date: 2026-02-21

## Context

The previous L1 storage model used two separate collections (`storage_ports` and `disks`) connected by `port_ref`.
While technically precise, this increases cognitive load: readers must mentally join two lists and verify references.

We need a simpler, human-friendly model while preserving migration safety for existing topology files.

## Decision

1. Introduce `specs.storage_slots[]` as the preferred L1 storage model.
2. Each slot carries:
   - bus type,
   - mount type,
   - optional installed media in `slot.media`.
3. Keep legacy `storage_ports + disks` supported during transition.
4. Normalize both formats in validator/tooling; emit warning when both are present.
5. Keep L3 bindings unchanged (`disk_ref` still points to media IDs), so migration is non-breaking for L3.

## Consequences

Benefits:

- Lower cognitive load: one object per physical slot with colocated media data.
- Easier review and maintenance of hardware inventory.
- Backward-compatible migration path.

Trade-offs:

- Temporary dual-format support increases validator complexity.
- Some templates/tooling require compatibility branches until legacy format is retired.

## References

- Files:
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology-tools/generate-proxmox-answer.py`
  - `topology-tools/templates/docs/devices.md.j2`
  - `topology-tools/templates/docs/physical-topology.md.j2`
  - `topology/L1-foundation/devices/owned/compute/gamayun.yaml`
  - `topology/L1-foundation/devices/owned/compute/orangepi5.yaml`
  - `topology/L1-foundation/devices/provider/compute/oracle-arm-frankfurt.yaml`
  - `topology/L1-foundation/devices/provider/compute/hetzner-cx22-nuremberg.yaml`
