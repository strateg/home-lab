# ADR 0015: Drop Legacy L1 Storage Compatibility After Storage Slots Migration

- Status: Accepted
- Date: 2026-02-21
- Supersedes: [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md)

## Context

`storage_slots` migration is complete for active topology sources.
Keeping fallback logic for legacy `storage_ports + disks` now adds complexity without operational value.

The remaining compatibility branches increased maintenance cost in:

- schema (parallel model definitions),
- validator normalization paths,
- templates and helper generators.

## Decision

1. Remove legacy L1 storage model support from active tooling:
   - no `storage_ports` and `specs.disks` support in schema;
   - no legacy parsing branches in validator;
   - no legacy fallback in documentation templates and Proxmox answer generator.
2. Keep L3 `disk_ref` contract unchanged (still references media IDs in `storage_slots[].media.id`).
3. Update docs to reference `storage_slots` as the only supported L1 storage model.

## Consequences

Benefits:

- Lower cognitive load and clearer data contract.
- Smaller validator/tooling code surface.
- Fewer ambiguous migration states.

Trade-offs:

- Old topologies using `storage_ports + disks` must be migrated before validation/generation.

## References

- Files:
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology-tools/generate-proxmox-answer.py`
  - `topology-tools/templates/docs/devices.md.j2`
  - `topology-tools/templates/docs/physical-topology.md.j2`
  - `topology-tools/README.md`
  - `topology-tools/GENERATORS-README.md`
  - `docs/guides/PROXMOX-USB-AUTOINSTALL.md`
