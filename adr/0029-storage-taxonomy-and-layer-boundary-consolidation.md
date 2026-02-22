# ADR 0029: Consolidate Storage Taxonomy and L1/L3 Boundary Contract

- Status: Accepted
- Date: 2026-02-22
- Supersedes:
  - [0011](0011-l1-physical-storage-taxonomy-and-l3-disk-binding.md)
  - [0012](0012-separate-l1-physical-disk-specs-from-l3-logical-storage-mapping.md)
  - [0013](0013-l1-storage-mount-taxonomy-soldered-replaceable-removable.md)
  - [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md)
  - [0015](0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md)
  - [0016](0016-l1-storage-media-registry-and-slot-attachments.md)

## Context

Storage modeling evolved through several migration ADRs.
The resulting implementation is stable, but architectural intent is split across many documents.

Current governance needs one canonical contract for:

1. L1 physical storage representation.
2. L1 mutable media inventory representation.
3. L1/L3 boundary for logical storage mapping.
4. Compatibility policy for legacy storage shapes.

## Decision

1. Canonical L1 physical model is slot-centric:
   - `devices[].specs.storage_slots[]` defines physical slot capability and connector characteristics.
2. Canonical mutable media inventory model is registry + attachments:
   - `L1_foundation.media_registry[]` defines media objects.
   - `L1_foundation.media_attachments[]` defines where media is currently attached (`device_ref`, `slot_ref`, `media_ref`).
3. L1 remains physical-only:
   - no OS runtime logical mapping (`/dev/*`, planned OS intent) in L1 disk/media objects.
4. L3 carries logical/runtime storage mapping:
   - OS-visible and logical storage bindings are modeled in L3 entities and storage references.
5. `mount_type` taxonomy remains mandatory hardware semantics (`soldered`, `replaceable`, `removable`, `virtual`) and is validated against slot/media characteristics.
6. Legacy pre-slot models are non-canonical in active workflows; compatibility support is treated as historical migration path, not current authoring target.

## Consequences

Benefits:

- One stable source of truth for storage architecture decisions.
- Lower cognitive overhead when editing topology and validator rules.
- Cleaner separation between physical facts (L1) and logical placement/runtime mapping (L3+).

Trade-offs:

- Historical migration details are now primarily in superseded ADRs.
- Changes to storage architecture should update this ADR unless a new decision boundary appears.

## References

- Replaced ADRs:
  - [0011](0011-l1-physical-storage-taxonomy-and-l3-disk-binding.md)
  - [0012](0012-separate-l1-physical-disk-specs-from-l3-logical-storage-mapping.md)
  - [0013](0013-l1-storage-mount-taxonomy-soldered-replaceable-removable.md)
  - [0014](0014-l1-storage-slots-preferred-model-with-legacy-compatibility.md)
  - [0015](0015-drop-legacy-storage-compatibility-after-storage-slots-migration.md)
  - [0016](0016-l1-storage-media-registry-and-slot-attachments.md)
- Related current model ADR:
  - [0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md)
- Canonical paths:
  - `topology/L1-foundation.yaml`
  - `topology/L3-data.yaml`
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/scripts/validators/checks/storage.py`
