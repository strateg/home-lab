# ADR 0016: L1 Storage Media Registry and Slot Attachments

- Status: Superseded by [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md)
- Date: 2026-02-21

## Context

L1 currently stores removable and replaceable media inline inside device slot definitions
(`devices[].specs.storage_slots[].media`).

This couples stable hardware slot specifications with mutable inventory state (insert/eject/swap),
which increases editing effort and cognitive load:

- moving a USB flash drive between devices requires editing multiple device files;
- removable inventory cannot be managed as a single registry;
- topology diffs mix static hardware specs and operational media changes.

## Decision

1. Keep `devices[].specs.storage_slots[]` as the canonical physical slot model (bus, mount, connector).
2. Introduce global L1 media registry: `L1_foundation.media_registry[]`.
3. Introduce explicit attachment registry: `L1_foundation.media_attachments[]`, linking:
   - `device_ref`
   - `slot_ref`
   - `media_ref`
4. Remove inline slot media payload from the active L1 contract.
5. Keep L3 `disk_ref` naming unchanged for now; it references media IDs from `media_registry`.

## Consequences

Benefits:

- Lower cognitive load: static slot specs are separated from mutable media state.
- Portable media lifecycle is explicit (add/remove/swap by attachment records).
- Cleaner diffs and easier audit/history of storage changes.

Trade-offs:

- Requires migration of existing topologies from inline slot media to registry+attachment model.
- Adds two additional L1 inventories that must be validated together.

Migration impact:

- Device files keep only slot capabilities.
- Media metadata moves into `media_registry`.
- Active placements move into `media_attachments`.

## References

- Schema:
  - `topology-tools/schemas/topology-v4-schema.json`
- Validator:
  - `topology-tools/validate-topology.py`
- L1 modular structure:
  - `topology/L1-foundation.yaml`
  - `topology/L1-foundation/media/_index.yaml`
  - `topology/L1-foundation/media-attachments/_index.yaml`
- Docs/templates:
  - `topology-tools/templates/docs/devices.md.j2`
  - `topology-tools/templates/docs/physical-topology.md.j2`
