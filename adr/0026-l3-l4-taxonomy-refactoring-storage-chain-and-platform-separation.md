# ADR 0026: L3/L4 Taxonomy Refactoring — Storage Chain and Platform Separation

- Status: Proposed
- Date: 2026-02-21

## Context

### Problem 1: L3 Storage Model Skips Intermediate Abstractions

Current L3 `storage:` jumps directly from physical media references to Proxmox storage endpoints,
missing critical intermediate abstractions:

```
L1: media_registry → media_attachments
         ↓
L3: storage (Proxmox-specific)     ← MISSING: partitions, VG, LV, filesystems
         ↓
L4: lxc.storage.rootfs
```

This creates several issues:

- `storage.os_device: /dev/pve/data` mixes runtime paths with logical definitions
- `storage.disk_ref` duplicates information already in `L1.media_attachments`
- No representation of partition tables, LVM volume groups, logical volumes, or filesystems
- Cannot model complex storage scenarios (multiple VGs, ZFS pools, thin provisioning details)

### Problem 2: L3 data_assets Weak Typing

Current `DataAssetType` conflates different dimensions:

```yaml
DataAssetType: [config-export, database, cache, backup-artifact, volume, file, media]
```

- `config-export` describes backup strategy, not data type
- `database` vs `cache` describes engine role, not asset category
- `volume` vs `file` describes storage abstraction, not data semantics
- No criticality, retention, or backup policy linkage

### Problem 3: L4 Mixes Platform and Application Configuration

LXC definitions contain application-specific configuration that belongs in L5:

```yaml
lxc:
- id: lxc-postgresql
  ansible:
    vars:
      postgresql_version: '16'        # ← Application config (belongs in L5)
      postgresql_databases:            # ← Data schema (belongs in L3/L5)
      - name: nextcloud
      postgresql_users:                # ← Access control (belongs in L5)
      - name: nextcloud
```

This violates separation of concerns:
- L4 should define compute resources (CPU, RAM, storage capacity)
- L5 should define application configuration
- L3 should define data schemas and assets

### Problem 4: L4 Type/Role Duplicates L5 ServiceType

```yaml
# L4:
LxcType: [database, cache, web, application, utility, proxy]
LxcRole: [database-server, cache-server, web-server, app-server, proxy-server]

# L5:
ServiceType: [database, cache, web-application, ...]
```

These overlap significantly. L4 should describe platform characteristics, not application roles.

### Problem 5: No Volume Mounts in L4

Current L4 only defines `rootfs`, with no model for additional data volumes:

```yaml
lxc:
  storage:
    rootfs:
      storage_ref: storage-lvm
      size_gb: 8
    # volumes: ← MISSING
```

This prevents:
- Linking LXC volumes to L3 data_assets
- Proper separation of OS storage from application data
- Backup policy association per volume

### Problem 6: L5 IP Duplication and external_services Redundancy

```yaml
# L4:
lxc:
- id: lxc-postgresql
  networks:
  - ip: 10.0.30.10/24

# L5:
services:
- id: svc-postgresql
  ip: 10.0.30.10              # ← Duplicated!
  lxc_ref: lxc-postgresql
```

Additionally, `external_services` in L5 duplicates service definitions for Docker workloads,
with hardcoded volume paths that have no L3 linkage.

### Problem 7: No Cross-Layer Data Asset Linkage

```
L3.data_assets ──?──► L4.lxc.volumes
       │
       └──────?──────► L5.services
```

There is no explicit connection between:
- Data assets and the LXC volumes that store them
- Data assets and the services that consume them
- Backup policies and the data assets they protect

## Decision

### D1: Introduce Full Storage Chain in L3

Create modular L3 structure with complete storage abstraction hierarchy:

```
topology/L3-data/
├── _index.yaml
├── partitions/           # Disk partitions (EFI, swap, LVM PV, etc.)
├── volume-groups/        # LVM VGs, ZFS pools
├── logical-volumes/      # LVM LVs, ZFS datasets
├── filesystems/          # Filesystem definitions
├── mount-points/         # Mount configurations
├── storage-endpoints/    # Proxmox/Docker storage (replaces current 'storage')
└── data-assets/          # Improved data asset definitions
```

New entity types:

```yaml
# partitions/gamayun.yaml
partitions:
- id: part-gamayun-ssd-3
  media_attachment_ref: attach-gamayun-slot-sata-0  # ← L1 link
  number: 3
  type: lvm-pv
  size: remaining

# volume-groups/pve.yaml
volume_groups:
- id: vg-pve
  name: pve
  type: lvm
  pv_refs: [part-gamayun-ssd-3]                     # ← L3 partition link

# logical-volumes/pve-data.yaml
logical_volumes:
- id: lv-pve-data
  name: data
  type: thin-pool
  vg_ref: vg-pve                                    # ← L3 VG link

# storage-endpoints/proxmox.yaml
storage_endpoints:
- id: se-local-lvm
  name: local-lvm
  platform: proxmox
  type: lvmthin
  lv_ref: lv-pve-data                               # ← L3 LV link
  content: [images, rootdir]
```

### D2: Improve data_assets Typing

Replace flat `DataAssetType` with structured attributes:

```yaml
DataAssetCategory:
  - database           # Structured data (PostgreSQL, MySQL)
  - cache              # Ephemeral fast storage (Redis, Memcached)
  - timeseries         # TSDB (Prometheus, InfluxDB)
  - search-index       # Elasticsearch, Meilisearch
  - object-storage     # MinIO, S3-compatible
  - file-share         # Nextcloud, SMB shares
  - media-library      # Jellyfin, Plex content
  - configuration      # Application configs
  - secrets            # Vault, sealed secrets
  - logs               # Log archives

DataAsset:
  properties:
    id: DataAssetRef
    name: string
    category: DataAssetCategory
    engine: string                    # postgresql, redis, prometheus
    engine_version: string
    criticality: [low, medium, high, critical]
    storage_endpoint_ref: StorageEndpointRef
    mount_point_ref: MountPointRef
    backup_policy_refs: [BackupPolicyRef]
    retention_days: integer
    encryption_at_rest: boolean
```

### D3: Remove Application Config from L4

Move all application-specific configuration from `lxc.ansible.vars` to L5 `services.config`:

```yaml
# L4 (platform only):
lxc:
- id: lxc-postgresql
  platform_type: lxc-unprivileged
  resource_profile_ref: profile-database
  # NO ansible.vars with application config

# L5 (application config):
services:
- id: svc-postgresql
  runtime:
    lxc_ref: lxc-postgresql
  config:
    engine: postgresql
    version: '16'
    listen_addresses: '0.0.0.0'
    max_connections: 50
```

### D4: Replace L4 Type/Role with Platform-Focused Taxonomy

```yaml
# Remove:
LxcType: [database, cache, web, ...]
LxcRole: [database-server, cache-server, ...]

# Add:
PlatformType:
  - lxc-privileged
  - lxc-unprivileged
  - lxc-nested
  - vm-bios
  - vm-uefi
  - vm-cloud-init

ResourceProfile:
  id: ResourceProfileRef
  cpu:
    cores: integer
    limit_percent: integer
  memory:
    mb: integer
    swap_mb: integer
  storage:
    rootfs_gb: integer
  tuning:
    vm_swappiness: integer
    dirty_ratio: integer
```

### D5: Add Volume Mounts to L4 with data_asset_ref

```yaml
lxc:
- id: lxc-postgresql
  storage:
    rootfs:
      storage_endpoint_ref: se-local-lvm
      size_gb: 8
    volumes:
    - id: vol-pg-data
      mount_point: /var/lib/postgresql/data
      storage_endpoint_ref: se-local-lvm
      size_gb: 20
      data_asset_ref: data-postgresql-main    # ← L3 link!
      backup: true
```

### D6: Unify L5 Service Runtime Model

Replace `device_ref` / `lxc_ref` / `container: true` with unified `runtime`:

```yaml
services:
- id: svc-postgresql
  runtime:
    type: lxc
    lxc_ref: lxc-postgresql
    # IP resolved from lxc.networks[0].ip

- id: svc-nextcloud
  runtime:
    type: docker
    device_ref: orangepi5
    image: nextcloud:28

  data_asset_refs:
  - data-nextcloud                    # ← L3 link resolves paths
```

Remove `external_services` — absorbed into `services` with `runtime.type: docker`.

### D7: Remove IP Duplication in L5

Services with `runtime.lxc_ref` or `runtime.device_ref` should not duplicate IP addresses.
IP is resolved from the referenced platform entity.

Validation rule:
```
IF service.runtime.lxc_ref EXISTS THEN
  service.ip MUST NOT EXIST OR
  service.ip MUST EQUAL lxc.networks[0].ip
```

### D8: Add Cross-Layer Validation Rules

```yaml
L3_validation:
  - partition.media_attachment_ref EXISTS IN L1.media_attachments
  - volume_group.pv_refs ALL EXIST IN L3.partitions WHERE type=lvm-pv
  - storage_endpoint references lv_ref OR mount_point_ref
  - data_asset WHERE criticality IN [high, critical] MUST have backup_policy_refs

L4_validation:
  - lxc.storage.volumes[].data_asset_ref EXISTS IN L3.data_assets
  - lxc.storage.*.storage_endpoint_ref EXISTS IN L3.storage_endpoints
  - lxc MUST NOT contain ansible.vars with application keys (warning)

L5_validation:
  - service.runtime.lxc_ref EXISTS IN L4.lxc
  - service.data_asset_refs ALL EXIST IN L3.data_assets
```

## Consequences

### Benefits

1. **Complete storage chain**: Full traceability from physical media to application data
2. **Clear layer contracts**: L3 = data, L4 = platform resources, L5 = application config
3. **Explicit data ownership**: data_assets linked to volumes and services
4. **Better backup modeling**: backup_policy_refs directly on data_assets
5. **Reduced duplication**: Single source of truth for IPs, storage paths
6. **Improved typing**: Category + engine + criticality instead of flat enum
7. **Platform-focused L4**: Resource profiles instead of application roles

### Trade-offs

1. **Migration effort**: Significant restructuring of L3 and L4 files
2. **Schema complexity**: More entity types and cross-references
3. **Validation overhead**: More cross-layer rules to implement
4. **Generator updates**: All generators must adapt to new structure

### Migration Impact

| Phase | Layer | Changes |
|-------|-------|---------|
| 1 | L3 | Create modular `L3-data/` directory structure |
| 2 | L3 | Add partitions, volume_groups, logical_volumes |
| 3 | L3 | Rename `storage` → `storage_endpoints`, remove physical refs |
| 4 | L3 | Add mount_points with data_asset linkage |
| 5 | L3 | Refactor data_assets with new schema |
| 6 | L4 | Create resource_profiles |
| 7 | L4 | Add lxc.storage.volumes with data_asset_ref |
| 8 | L4 | Remove ansible.vars application config |
| 9 | L4 | Replace type/role with platform_type/resource_profile_ref |
| 10 | L5 | Add services.config for application settings |
| 11 | L5 | Replace device_ref/lxc_ref with unified runtime |
| 12 | L5 | Remove external_services |
| 13 | L5 | Remove duplicated IP fields |
| 14 | Schema | Update JSON Schema definitions |
| 15 | Validators | Add cross-layer validation rules |
| 16 | Generators | Update all generators for new structure |

### Compatibility

- **Breaking change**: L3 `storage` renamed to `storage_endpoints`
- **Breaking change**: L4 `lxc.type` and `lxc.role` removed
- **Breaking change**: L5 `external_services` removed
- **Deprecation**: L4 `ansible.vars` with application keys (warning, then error)

## References

- Previous storage ADRs:
  - ADR-0011: L1 Physical Storage Taxonomy
  - ADR-0012: Separate L1 Physical Disk Specs from L3 Logical Storage Mapping
  - ADR-0016: L1 Storage Media Registry and Slot Attachments
- Schema:
  - `topology-tools/schemas/topology-v4-schema.json`
- Current layer files:
  - `topology/L3-data.yaml`
  - `topology/L4-platform.yaml`
  - `topology/L5-application.yaml`
- Validators:
  - `topology-tools/scripts/validators/`
- Generators:
  - `topology-tools/scripts/generators/`
