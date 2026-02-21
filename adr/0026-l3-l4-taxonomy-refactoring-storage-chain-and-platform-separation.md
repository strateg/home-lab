# ADR 0026: L3/L4 Taxonomy Refactoring - Storage Chain and Platform Separation

- Status: Accepted
- Date: 2026-02-21

## Context

The current topology model has four structural issues:

1. L3 storage jumps from L1 media attachments directly to platform storage objects, skipping partition/LVM/filesystem abstractions.
2. L3 `data_assets` mix data semantics with storage placement details.
3. L4 includes application configuration (`ansible.vars`) that belongs to L5 service config.
4. L5 runtime metadata duplicates network/IP facts already defined in L4 and L2.

This causes weak traceability, duplicated source-of-truth fields, and expensive generator/validator logic.

## Decision

### D1. Introduce full L3 storage chain

Adopt a modular L3 structure:

```text
topology/L3-data/
|-- _index.yaml
|-- partitions/
|-- volume-groups/
|-- logical-volumes/
|-- filesystems/
|-- mount-points/
|-- storage-endpoints/
`-- data-assets/
```

Core relation chain:

```text
L1.media_attachments
  -> L3.partitions
  -> L3.volume_groups
  -> L3.logical_volumes
  -> L3.filesystems
  -> L3.mount_points
  -> L3.storage_endpoints
```

To avoid over-modeling in small home-lab setups, implementations MAY support a shorthand
`storage_endpoints[].infer_from` mode that derives intermediate chain entities
(partition/VG/LV/filesystem/mount) deterministically.
This shorthand is an authoring convenience only; the canonical model remains explicit chain entities.

### D2. Define strict ownership (single source of truth)

Ownership contract:

- L3 `data_assets` define data semantics and governance only.
- L4 `storage.rootfs` and `storage.volumes[]` define placement and capacity.
- L5 services define runtime and consumption.

Therefore:

- `DataAsset` MUST NOT contain placement fields (`storage_endpoint_ref`, `mount_point_ref`, absolute host paths).
- Placement is expressed only in L4 volumes via `storage_endpoint_ref`, `mount_path`, and `size_gb`.
- Service-to-data linkage is expressed only via `service.data_asset_refs`.

### D3. Refactor `data_assets` typing with conditional requirements

Introduce `DataAsset` as:

```yaml
DataAsset:
  properties:
    id: DataAssetRef
    name: string
    category: [database, cache, timeseries, search-index, object-storage, file-share, media-library, configuration, secrets, logs]
    criticality: [low, medium, high, critical]
    backup_policy_refs: [BackupPolicyRef]
    retention_days: integer
    encryption_at_rest: boolean
    engine: string
    engine_version: string
```

Validation contract:

- `engine` is REQUIRED for `database`, `cache`, `timeseries`, `search-index`, `object-storage`.
- `engine` is OPTIONAL for `configuration`, `secrets`, `logs`, `file-share`, `media-library`.
- `backup_policy_refs` is REQUIRED when `criticality in [high, critical]`.

### D4. Keep L4 platform-focused

Replace application-oriented L4 taxonomy with platform-oriented fields:

```yaml
platform_type: [lxc-unprivileged, lxc-privileged, lxc-nested, vm-uefi, vm-bios, vm-cloud-init]
resource_profile_ref: ResourceProfileRef
```

Deprecations:

- `lxc.type` and `lxc.role` become deprecated compatibility fields.
- `lxc.ansible.vars` with application keys becomes deprecated.

### D5. Add explicit L4 volume model

L4 storage model:

```yaml
lxc:
- id: lxc-postgresql
  storage:
    rootfs:
      storage_endpoint_ref: se-local-lvm
      size_gb: 8
    volumes:
    - id: vol-pg-data
      mount_path: /var/lib/postgresql/data
      storage_endpoint_ref: se-local-lvm
      size_gb: 20
      data_asset_ref: data-postgresql-main
```

Validation:

- `volumes[].data_asset_ref` must exist in L3 `data_assets`.
- `rootfs` SHOULD NOT reference a `data_asset_ref`.

### D6. Unify L5 runtime model and network binding

Use one runtime object:

```yaml
services:
- id: svc-postgresql
  runtime:
    type: lxc        # lxc | vm | docker | baremetal
    target_ref: lxc-postgresql
    network_binding_ref: net-servers
  endpoints:
  - name: pg
    protocol: tcp
    port: 5432
  data_asset_refs:
  - data-postgresql-main
```

Rules:

- Replace `lxc_ref`, `vm_ref`, `device_ref`, and `external_services` with `runtime`.
- `network_binding_ref` removes the implicit `networks[0]` assumption.
- Service IP is resolved from runtime target + binding; explicit `service.ip` becomes deprecated.

### D7. Add cross-layer validation contracts

Add domain checks:

- L3 integrity (partition -> VG -> LV -> FS -> mount -> endpoint chain).
- L4 placement (`storage_endpoint_ref`, `data_asset_ref`) consistency.
- L5 runtime target resolution and `data_asset_refs` integrity.
- Governance rules for critical assets and backup policies.

### D8. Adopt compatibility-first migration (no big bang)

Migration policy:

1. `M1` (dual-read): validators/generators read old + new fields, write old.
2. `M2` (dual-write): generators write new fields and (optionally) old compatibility fields.
3. `M3` (warn-hardening): legacy fields produce warnings by default, errors in strict mode.
4. `M4` (cutover): schema removes legacy fields; generators/validators stop reading them.

This ADR is accepted only with the phased plan below.

### D9. Versioning policy

Versioning policy for this migration:

- `v4.1.x`: compatibility schema (dual-read foundations in schema/validators).
- `v4.2.x`: dual-write period for generators and migration assistant tooling.
- `v5.0.0`: strict-only model after legacy field removal.

### D10. Non-goals

Out of scope for this ADR:

- Runtime orchestration changes (systemd, k8s, docker compose mechanics).
- Backup execution engine implementation details.
- Secrets provider implementation beyond metadata linkage.

## Consequences

### Benefits

1. Full storage traceability from physical media to service data.
2. Clear layer contract: L3 (data semantics), L4 (placement/resources), L5 (runtime/configuration).
3. Reduced field duplication and fewer ambiguous overrides.
4. Better governance through enforceable criticality/backup rules.
5. Safer rollout due to compatibility-first migration.

### Trade-offs

1. More schema entities and references increase modeling complexity.
2. Validator and generator refactor cost is significant.
3. Temporary dual-read/dual-write period increases maintenance load.

### Risks

1. Migration drift if strict-mode gates are delayed.
2. Partial generator migration may produce mixed old/new output.
3. Documentation lag can confuse operators during `M2-M3`.

## Implementation Plan

### Phase 1 - Compatibility baseline (completed)

- Added new schema entities and refs for L3/L4/L5 while preserving legacy fields.
- Added deprecation markers (`x-deprecated`) for legacy placement/runtime fields.
- Added cross-layer validation for L3 chain integrity and runtime/resource references.
- Added strict mode (`validate-topology.py --strict`) to escalate warnings into errors.

Done criteria:

- `topology-tools/schemas/topology-v4-schema.json` validates legacy and mixed topologies.
- `topology-tools/validate-topology.py` supports `compat` and `strict` behavior.

### Phase 2 - Topology scaffolding and authoring model

- Introduce modular `topology/L3-data/*` structure and `_index.yaml` wiring.
- Seed `resource_profiles` in `L4_platform` and migrate representative LXC entries.
- Add `services[].runtime` and `network_binding_ref` alongside legacy service refs.
- Keep legacy fields present but warn in validation output.

Done criteria:

- Current repository topology validates in compat mode with zero errors.
- At least one service and one LXC are modeled in the new style.

### Phase 3 - Migration tooling and reporting

- Add migration assistant (`migrate-to-v5.py`) with `--dry-run`.
- Emit machine-readable migration report for legacy fields and required conversions.
- Support deterministic transforms for:
  - `L3_data.storage -> storage_endpoints`
  - `services.*_ref -> services.runtime`
  - `lxc.resources -> resource_profile_ref`

Done criteria:

- Tool produces stable conversion output and explicit checklist for manual review.

### Phase 4 - Generator dual-write rollout

- Update generators to read new model first and fallback to legacy during `M1-M2`.
- Implement deterministic precedence when both old and new fields are present.
- Add support for `storage_endpoints[].infer_from` shorthand expansion in generation path.

Primary files:

- `topology-tools/scripts/generators/terraform/proxmox/generator.py`
- `topology-tools/scripts/generators/terraform/mikrotik/generator.py`
- `topology-tools/generate-ansible-inventory.py`
- `topology-tools/scripts/generators/docs/generator.py`

Done criteria:

- `topology-tools/regenerate-all.py` succeeds for legacy-only, mixed, and new-only fixture sets.

### Phase 5 - Quality gates and strict hardening

- Add fixture topologies: legacy-only, mixed, new-only.
- Add validator tests for chain integrity and deprecation escalation behavior.
- Add generator regression snapshots for key outputs.
- Enable strict mode in CI for new-only fixtures.

Done criteria:

- CI blocks regressions and fails on strict-mode warnings for new-only fixtures.

### Phase 6 - v5 cutover

- Switch default validation profile to strict for mainline topologies.
- Remove deprecated legacy fields from schema and validators.
- Remove fallback branches in generators and migration compatibility code.
- Update docs and ADR status for cutover completion.

Done criteria:

- Legacy fields absent from repository topology and generated outputs.

## Acceptance Criteria

1. No duplicated placement fields between L3 and L4 in the final model.
2. No duplicated service IP source of truth in L5.
3. Critical/high `data_assets` always include backup policy linkage.
4. Full regeneration works for legacy/mixed/new fixtures during compatibility phases.
5. Final strict mode passes on new-only topology with zero deprecation warnings.

## References

- Previous ADRs:
  - ADR-0011: `adr/0011-l1-physical-storage-taxonomy-and-l3-disk-binding.md`
  - ADR-0012: `adr/0012-separate-l1-physical-disk-specs-from-l3-logical-storage-mapping.md`
  - ADR-0016: `adr/0016-l1-storage-media-registry-and-slot-attachments.md`
- Schema:
  - `topology-tools/schemas/topology-v4-schema.json`
- Topology layers:
  - `topology/L3-data.yaml`
  - `topology/L4-platform.yaml`
  - `topology/L5-application.yaml`
- Validation code:
  - `topology-tools/scripts/validators/`
- Generation code:
  - `topology-tools/scripts/generators/`
