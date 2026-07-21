# ADR 0011: L1 Physical Storage Taxonomy and L3 Disk Binding

- Status: Superseded by [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md)
- Date: 2026-02-20

## Context

L1 compute devices previously used loosely structured `specs.disks` (or only generic `storage` hints) without a formal taxonomy for storage media and without explicit disk-to-port binding.

This limited analysis quality and made it harder to reliably map L3 logical storage objects to real physical media.

## Decision

1. Introduce formal L1 storage taxonomy in schema:
   - `specs.storage_ports[]` with typed port classes (`sata`, `m2`, `sdio`, `qspi`, `virtual`, etc.);
   - `specs.disks[]` with disk classes (`hdd`, `ssd`, `nvme`, `sd-card`, `emmc`, `flash`) and lifecycle state.
2. Require each disk to declare `port_ref` and validate that it points to an existing `storage_port`.
3. Require baremetal compute devices to maintain explicit disk inventory in `specs.disks`.
4. Add validator checks that bind L3 storage to L1 physical inventory:
   - `L3_data.storage[].device_ref` must exist;
   - `disk_ref` requires `device_ref`;
   - `disk_ref` must exist in referenced L1 device `specs.disks`.
5. Update current compute device inventory to the new model (owned and provider compute nodes).

## Consequences

Benefits:

- L1 now carries explicit, analyzable physical storage topology.
- Port-level binding clarifies where each medium is connected.
- L3 storage modeling can be grounded in concrete disks instead of free-text assumptions.
- Validation catches drift between logical storage and physical inventory earlier.

Trade-offs:

- More detailed inventory upkeep is required when hardware changes.
- Schema/validator complexity increases.

## References

- Files:
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology/L1-foundation/devices/owned/compute/gamayun.yaml`
  - `topology/L1-foundation/devices/owned/compute/orangepi5.yaml`
  - `topology/L1-foundation/devices/provider/compute/oracle-arm-frankfurt.yaml`
  - `topology/L1-foundation/devices/provider/compute/hetzner-cx22-nuremberg.yaml`
  - `topology-tools/templates/docs/devices.md.j2`
  - `topology-tools/templates/docs/physical-topology.md.j2`
