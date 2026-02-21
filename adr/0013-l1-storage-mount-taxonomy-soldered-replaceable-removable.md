# ADR 0013: L1 Storage Mount Taxonomy for Soldered, Replaceable, and Removable Media

- Status: Accepted
- Date: 2026-02-21

## Context

L1 physical storage inventory already modeled disk type and storage ports, but did not explicitly encode how media is mounted:

- soldered to board (non-replaceable chip),
- replaceable via hardware port/socket,
- removable media via reader/slot.

For physical analysis and planning of L3 logical volumes, this distinction must be explicit and machine-validated.

## Decision

1. Add `mount_type` to L1 physical disks with enum:
   - `soldered`
   - `replaceable`
   - `removable`
   - `virtual`
2. Expand storage port taxonomy to include:
   - `ide`
   - `emmc-reader`
   - `onboard`
3. Enforce mount-type and port-type compatibility in validator.
4. Keep this in L1 only as hardware characteristics; logical mappings remain in L3.

## Consequences

Benefits:

- Clear differentiation between non-replaceable onboard memory and field-replaceable drives.
- Better hardware lifecycle planning and failure-domain analysis.
- Stronger basis for L3 storage modeling and migration strategy.

Trade-offs:

- Slightly more detailed L1 inventory maintenance.
- Additional validator rules increase strictness.

## References

- Files:
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology/L1-foundation/devices/owned/compute/gamayun.yaml`
  - `topology/L1-foundation/devices/owned/compute/orangepi5.yaml`
  - `topology/L1-foundation/devices/provider/compute/oracle-arm-frankfurt.yaml`
  - `topology/L1-foundation/devices/provider/compute/hetzner-cx22-nuremberg.yaml`
