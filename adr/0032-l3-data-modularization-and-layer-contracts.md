# ADR 0032: L3 Data Modularization and Layer Contracts

- Status: Proposed
- Date: 2026-02-22

## Context

`L3_data` is currently maintained as a single file (`topology/L3-data.yaml`), while neighboring layers already use modular structure:

- L1: modularized by domains (`devices`, `media`, `attachments`, links).
- L2: modularized by domains (`networks`, `routing`, `firewall`, etc.).
- L5/L6/L7: partially modularized by concern.

This creates uneven maintainability and larger review diffs in L3, even though L3 has two distinct responsibilities and grows with each infrastructure expansion:

- new local devices (for example NAS),
- new compute nodes (for example additional Proxmox host),
- new provider nodes (cloud instances with persistent data).

L3 already mixes two classes of entities:

1. Internal storage chain model:
   - `partitions`
   - `volume_groups`
   - `logical_volumes`
   - `filesystems`
   - `mount_points`
2. Public cross-layer contract consumed by upper layers:
   - `storage_endpoints`
   - `data_assets`

Cross-layer dependency analysis:

- Downward (`L3 -> lower layers`):
  - L3 depends on L1 physical inventory via `media_attachment_ref` and `device_ref`.
  - L3 should not depend on L4+.
  - L3 does not require direct semantic dependency on L2.
- Upward (`L4/L5/L6/L7 <- L3`):
  - L4 consumes `storage_endpoints` and `data_assets`.
  - L5 consumes `data_assets` references.
  - L7 backup consumes `data_assets` and storage endpoint identifiers.
  - L6 should remain indirectly connected through services, not direct L3 internals.

The current monolith increases coupling risk: internal chain changes can accidentally affect public references and upper layers, and human operators must parse too much unrelated context for small changes.

## Decision

Adopt modular L3 structure with explicit separation between internal chain and public contract.

Canonical structure:

```text
topology/L3-data/
  partitions/
  volume-groups/
  logical-volumes/
  filesystems/
  mount-points/
  storage-endpoints/
    _index.yaml
    owned/
      _index.yaml
    provider/
      _index.yaml
  data-assets/
    _index.yaml
    owned/
      _index.yaml
    provider/
      _index.yaml
```

`topology/L3-data.yaml` becomes composition root with `!include` per key:

- `partitions`
- `volume_groups`
- `logical_volumes`
- `filesystems`
- `mount_points`
- `storage_endpoints`
- `data_assets`

Contract boundary rules:

1. Internal L3 chain (implementation details):
   - `partitions`, `volume_groups`, `logical_volumes`, `filesystems`, `mount_points`.
   - Upper layers must not reference these IDs directly.
2. Public L3 API for upper layers:
   - `storage_endpoints` and `data_assets` only.
   - IDs are stable and backward compatible.
3. L3 downward references:
   - Allowed: L1 references (`media_attachment_ref`, `device_ref`).
   - Forbidden: references to L4/L5/L6/L7.
4. Upper-layer usage:
   - L4 workload storage binds only via `storage_endpoint_ref` and `data_asset_ref`.
   - L5/L7 use `data_asset_ref`; `storage_ref` in operations must resolve to endpoint IDs.
5. Module ownership partitioning:
   - `owned/` modules for local/bare-metal estate.
   - `provider/` modules for cloud/provider estate.
   - This split is only for navigation and review scope; semantic type comes from object fields.

Extension patterns (required):

1. Add NAS:
   - add device and attachments in L1,
   - add NAS endpoints/assets in `storage-endpoints/owned/` and `data-assets/owned/`,
   - upper layers reference only new endpoint/asset IDs.
2. Add Proxmox node:
   - L1 node and media inventory,
   - new L3 chain modules only for this node,
   - expose only node-specific endpoints/assets for L4/L7 consumption.
3. Add cloud node:
   - L1 provider-instance,
   - L3 entries under `provider/`,
   - no change required in existing owned-node chain modules.

Cognitive-load controls (required):

1. One object per file; file name equals object ID.
2. Stable ID grammar: `se-<scope>-<node>-<purpose>`, `data-<scope>-<workload>-<purpose>`.
3. Keep public-contract modules (`storage-endpoints`, `data-assets`) small and owner-partitioned.
4. Upper layers must never reference internal chain IDs.
5. Every expansion follows checklist from `docs/architecture/L3-DATA-MODULARIZATION-PLAN.md`.

Validation/governance extensions:

1. Add L3 file-placement policy roots to validator policy.
2. Add semantic checks:
   - detect upper-layer references to L3 internal chain IDs,
   - ensure L7 storage refs resolve to `storage_endpoints`.
3. Keep strict mode as default for canonical topology.

## Consequences

Benefits:

- Smaller, scoped diffs in L3 changes.
- Clear API boundary between L3 internals and upper-layer consumers.
- Scalable expansion path for NAS/new Proxmox/cloud without touching unrelated modules.
- Lower risk of accidental breakage in L4/L5/L7 when changing storage internals.
- Better symmetry with existing L1/L2 modular design.
- Reduced cognitive load: change is localized by owner and by contract type.

Trade-offs:

- More files and index maintenance.
- Initial migration effort and stricter validation can surface existing drift.
- Requires disciplined ID naming and module placement conventions.

Migration impact:

1. Non-functional split first (same IDs, same content, new file layout).
2. Validation and generators must pass without behavior change.
3. Then enforce stricter semantic checks and cleanup of non-canonical refs.

## References

- Current L3 root: `topology/L3-data.yaml`
- Modular guide: `topology/MODULAR-GUIDE.md`
- Rollout plan: `docs/architecture/L3-DATA-MODULARIZATION-PLAN.md`
- L3 schema section: `topology-tools/schemas/topology-v4-schema.json`
- Storage validator: `topology-tools/scripts/validators/checks/storage.py`
- Related ADRs:
  - [0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md)
  - [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md)
  - [0031](0031-layered-topology-toolchain-contract-alignment.md)
