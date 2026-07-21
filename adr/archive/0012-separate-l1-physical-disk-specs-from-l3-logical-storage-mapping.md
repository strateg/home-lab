# ADR 0012: Separate L1 Physical Disk Specs from L3 Logical Storage Mapping

- Status: Superseded by [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md)
- Date: 2026-02-21

## Context

L1 device inventory mixed hardware facts with runtime OS disk naming (`/dev/*`) and planned OS intent.
This blurred the layer boundary:

- L1 should describe vendor/hardware capabilities only.
- L3 should describe logical storage configuration and OS-visible mappings.

Without strict separation, analysis and automation become brittle (for example, `/dev/sdX` naming can change).

## Decision

1. Keep `L1_foundation.devices[].specs.disks[]` physical-only:
   - media type, size, state, hardware port binding (`port_ref`), vendor/model/serial, physical flags.
2. Disallow logical OS disk path at L1 disk level:
   - remove `device` from `PhysicalDisk` schema and set strict `additionalProperties: false`.
3. Move OS-visible disk path mapping into `L3_data.storage[]`:
   - add `os_device` field (e.g. `/dev/sda3`, `/dev/pve/data`).
4. Keep OS compatibility in L1 via capability field:
   - `supported_operating_systems` on device.
5. Add validator rules to enforce separation:
   - L1 disk entries containing logical `device` field are errors;
   - `os.planned` in L1 compute devices is an error (move upward);
   - `storage.disk_ref` + `storage.device_ref` must resolve to real L1 disk inventory;
   - warn when `disk_ref` exists without `os_device`.

## Consequences

Benefits:

- Clearer layer contracts: hardware facts in L1, logical storage mapping in L3.
- Better resilience to runtime device-name drift.
- Stronger guarantees for future L3 logical volume modeling.

Trade-offs:

- Slightly more verbose L3 storage definitions (`os_device` + disk binding).
- Existing tooling that read `/dev/*` from L1 must be adjusted.

## References

- Files:
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology/L3-data.yaml`
  - `topology/L1-foundation/devices/owned/compute/gamayun.yaml`
  - `topology/L1-foundation/devices/owned/compute/orangepi5.yaml`
  - `topology/L1-foundation/devices/provider/compute/oracle-arm-frankfurt.yaml`
  - `topology/L1-foundation/devices/provider/compute/hetzner-cx22-nuremberg.yaml`
  - `topology-tools/generate-proxmox-answer.py`
