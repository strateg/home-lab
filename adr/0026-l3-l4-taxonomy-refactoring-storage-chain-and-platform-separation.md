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

### D9. Non-goals

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

### Phase 1 - Schema foundation

- Add L3 modular schema objects (`partitions`, `volume_groups`, `logical_volumes`, `filesystems`, `mount_points`, `storage_endpoints`, `data_assets`).
- Add L4 `storage.volumes[]`, `platform_type`, and `resource_profile_ref`.
- Add L5 `runtime`, `network_binding_ref`, and `endpoints`.
- Mark legacy fields as deprecated (description + warning metadata).

Done criteria:

- `topology-tools/schemas/topology-v4-schema.json` validates both old and new model.

### Phase 2 - Topology data migration scaffolding

- Introduce modular `topology/L3-data/*` structure and `_index.yaml` wiring.
- Populate new entities for existing storage chain.
- Add `data_asset_ref` to relevant L4 volumes.
- Add L5 `runtime` alongside existing refs.

Done criteria:

- Current repo topology validates in compatibility mode with zero errors.

### Phase 3 - Validators

- Implement L3 chain integrity checks in `topology-tools/scripts/validators/checks/storage.py`.
- Add L4/L5 cross-layer checks in relevant validator modules.
- Add deprecation warnings for legacy fields with strict-mode escalation.

Done criteria:

- Validator supports `compat` and `strict` behaviors.

### Phase 4 - Generators

- Update generators to read new model first, fallback to legacy during `M1-M2`.
- Enforce deterministic precedence when both old and new are present.
- Emit migration hints when legacy fallback is used.

Primary files:

- `topology-tools/scripts/generators/terraform/proxmox/generator.py`
- `topology-tools/scripts/generators/terraform/mikrotik/generator.py`
- `topology-tools/generate-ansible-inventory.py`
- `topology-tools/scripts/generators/docs/generator.py`

Done criteria:

- `topology-tools/regenerate-all.py` succeeds with new-only topology and with mixed compatibility topology.

### Phase 5 - Tests and quality gates

- Add fixture topologies: legacy-only, mixed, new-only.
- Add validator tests for each cross-layer rule.
- Add generator regression snapshots for key outputs.

Done criteria:

- CI validates all three fixture modes and blocks regressions.

### Phase 6 - Cutover

- Switch default validation to strict.
- Remove deprecated legacy fields from schema and validators.
- Remove fallback branches in generators.
- Update docs and ADR status.

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
