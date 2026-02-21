# TODO: Architectural Improvements

This file tracks planned architectural improvements for the home-lab infrastructure-as-data project.

---

## Critical Priority: L3/L4 Taxonomy Refactoring

> **ADR**: [0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md](adr/0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md)
> **Status**: Proposed
> **Complexity**: High
> **Impact**: Foundational improvement to data model consistency

This refactoring addresses fundamental issues in the topology layer model:
- L3 skips intermediate storage abstractions (partitions, VG, LV)
- L4 mixes platform resources with application configuration
- No cross-layer linkage between data assets, volumes, and services
- Significant duplication between L4 and L5

### Phase 1: L3 Modular Structure

**Status**: Not Started
**Estimated effort**: 2-3 sessions

**Goal**: Create modular L3 directory structure with full storage chain.

**Current state**:
```
topology/L3-data.yaml     # Monolithic file with storage + data_assets
```

**Target state**:
```
topology/L3-data/
├── _index.yaml           # Main entry with !include directives
├── partitions/           # Disk partitions
│   └── gamayun.yaml      # Partitions on Proxmox host
├── volume-groups/        # LVM VGs, ZFS pools
│   └── pve.yaml          # Proxmox default VG
├── logical-volumes/      # LVM LVs, ZFS datasets
│   └── pve-data.yaml     # Thin pool for VM/LXC
├── filesystems/          # FS definitions
│   └── default.yaml
├── mount-points/         # Mount configurations
│   └── default.yaml
├── storage-endpoints/    # Proxmox/Docker storage (replaces 'storage')
│   ├── proxmox.yaml
│   └── docker.yaml
└── data-assets/          # Improved data asset definitions
    ├── databases.yaml
    ├── application-data.yaml
    └── media.yaml
```

**Tasks**:

- [ ] **1.1** Create directory structure `topology/L3-data/`
  ```bash
  mkdir -p topology/L3-data/{partitions,volume-groups,logical-volumes,filesystems,mount-points,storage-endpoints,data-assets}
  ```

- [ ] **1.2** Create `_index.yaml` with !include directives
  ```yaml
  # L3 Data - Modular Layout
  # Part of Home Lab Topology v4.0.0
  partitions: !include partitions/_index.yaml
  volume_groups: !include volume-groups/_index.yaml
  logical_volumes: !include logical-volumes/_index.yaml
  filesystems: !include filesystems/_index.yaml
  mount_points: !include mount-points/_index.yaml
  storage_endpoints: !include storage-endpoints/_index.yaml
  data_assets: !include data-assets/_index.yaml
  ```

- [ ] **1.3** Migrate current `storage:` → `storage-endpoints/proxmox.yaml`
  - Remove `disk_ref`, `os_device` (physical refs belong in chain)
  - Keep `storage_ref` pattern but rename to `storage_endpoint_ref`

- [ ] **1.4** Create initial `partitions/gamayun.yaml`
  ```yaml
  # Derived from current L1 media_attachments + L3 storage.os_device
  partitions:
  - id: part-gamayun-ssd-1
    media_attachment_ref: attach-gamayun-slot-sata-0
    number: 1
    type: efi
    size_mb: 512

  - id: part-gamayun-ssd-2
    media_attachment_ref: attach-gamayun-slot-sata-0
    number: 2
    type: swap
    size_gb: 8

  - id: part-gamayun-ssd-3
    media_attachment_ref: attach-gamayun-slot-sata-0
    number: 3
    type: lvm-pv
    size: remaining
    description: LVM physical volume for pve VG
  ```

- [ ] **1.5** Create `volume-groups/pve.yaml`
  ```yaml
  volume_groups:
  - id: vg-pve
    name: pve
    type: lvm
    pv_refs:
    - part-gamayun-ssd-3
    description: Proxmox default volume group
  ```

- [ ] **1.6** Create `logical-volumes/pve-data.yaml`
  ```yaml
  logical_volumes:
  - id: lv-pve-root
    name: root
    type: standard
    vg_ref: vg-pve
    size_gb: 20
    description: Proxmox root filesystem

  - id: lv-pve-data
    name: data
    type: thin-pool
    vg_ref: vg-pve
    size: remaining
    description: Thin pool for VM/LXC images and rootfs
  ```

- [ ] **1.7** Update L3-data.yaml to use !include from L3-data/
  ```yaml
  # L3 Data
  # Part of Home Lab Topology v4.0.0
  # Modular layout - see topology/L3-data/ for components

  partitions: !include L3-data/partitions/_index.yaml
  volume_groups: !include L3-data/volume-groups/_index.yaml
  # ... etc
  ```

**Validation after Phase 1**:
```bash
python3 topology-tools/validate-topology.py
# Should pass with new structure
```

---

### Phase 2: L3 Data Assets Taxonomy

**Status**: Not Started
**Estimated effort**: 1-2 sessions

**Goal**: Replace flat `DataAssetType` enum with structured attributes.

**Current state**:
```yaml
DataAssetType: [config-export, database, cache, backup-artifact, volume, file, media]

data_assets:
- id: data-postgresql-db
  type: database           # Flat, no engine/version/criticality
  storage_ref: storage-lvm
```

**Target state**:
```yaml
DataAssetCategory: [database, cache, timeseries, search-index, object-storage,
                    file-share, media-library, configuration, secrets, logs]

data_assets:
- id: data-postgresql-main
  name: PostgreSQL Primary Database
  category: database
  engine: postgresql
  engine_version: '16'
  criticality: high
  storage_endpoint_ref: se-local-lvm
  databases:                    # Engine-specific metadata
  - name: nextcloud
    owner: nextcloud
  - name: homelab
    owner: app
  backup_policy_refs:
  - backup-hourly-postgresql
  - backup-daily-postgresql-lxc
  retention_days: 90
  encryption_at_rest: false
```

**Tasks**:

- [ ] **2.1** Define new schema types in JSON Schema
  ```json
  {
    "DataAssetCategory": {
      "type": "string",
      "enum": ["database", "cache", "timeseries", "search-index",
               "object-storage", "file-share", "media-library",
               "configuration", "secrets", "logs"]
    },
    "Criticality": {
      "type": "string",
      "enum": ["low", "medium", "high", "critical"]
    }
  }
  ```

- [ ] **2.2** Update `DataAsset` schema
  ```json
  {
    "DataAsset": {
      "type": "object",
      "required": ["id", "name", "category"],
      "properties": {
        "id": { "pattern": "^data-[a-z0-9-]+$" },
        "name": { "type": "string" },
        "category": { "$ref": "#/definitions/DataAssetCategory" },
        "engine": { "type": "string" },
        "engine_version": { "type": "string" },
        "criticality": { "$ref": "#/definitions/Criticality" },
        "storage_endpoint_ref": { "$ref": "#/definitions/StorageEndpointRef" },
        "mount_point_ref": { "$ref": "#/definitions/MountPointRef" },
        "backup_policy_refs": {
          "type": "array",
          "items": { "$ref": "#/definitions/BackupPolicyRef" }
        },
        "retention_days": { "type": "integer", "minimum": 1 },
        "encryption_at_rest": { "type": "boolean" }
      }
    }
  }
  ```

- [ ] **2.3** Migrate existing data_assets to new format
  - `data-postgresql-db` → `data-postgresql-main` with full attributes
  - `data-redis-db` → `data-redis-cache` with category=cache
  - Add `criticality` based on actual importance
  - Link to existing backup policies in L7

- [ ] **2.4** Create `data-assets/databases.yaml`
  ```yaml
  # Database data assets
  data_assets:
  - id: data-postgresql-main
    name: PostgreSQL Primary Database
    category: database
    engine: postgresql
    engine_version: '16'
    criticality: high
    storage_endpoint_ref: se-local-lvm
    databases:
    - name: nextcloud
      owner: nextcloud
      size_estimate_mb: 500
    - name: homelab
      owner: app
      size_estimate_mb: 100
    backup_policy_refs:
    - backup-hourly-postgresql
    - backup-daily-postgresql-lxc
    retention_days: 90
    description: Primary PostgreSQL instance hosting all application databases
  ```

- [ ] **2.5** Create `data-assets/application-data.yaml`
  ```yaml
  # Application data assets (volumes, configs)
  data_assets:
  - id: data-nextcloud
    name: Nextcloud Application Data
    category: file-share
    engine: nextcloud
    engine_version: '28'
    criticality: high
    mount_point_ref: mp-nvme-nextcloud
    backup_policy_refs:
    - backup-orangepi5-data
    - backup-offsite-weekly
    retention_days: 365
    encryption_at_rest: false
    description: Nextcloud user files, config, and application data

  - id: data-jellyfin-config
    name: Jellyfin Configuration
    category: configuration
    engine: jellyfin
    criticality: medium
    mount_point_ref: mp-nvme-jellyfin-config
    backup_policy_refs:
    - backup-orangepi5-data
    retention_days: 30
    description: Jellyfin server configuration (media paths separate)
  ```

- [ ] **2.6** Add validation rule: high/critical criticality requires backup_policy_refs
  ```python
  # In validator
  def check_data_asset_backup_policy(data_assets, errors, warnings):
      for asset in data_assets:
          if asset.get('criticality') in ['high', 'critical']:
              if not asset.get('backup_policy_refs'):
                  errors.append(
                      f"data_asset '{asset['id']}' has criticality={asset['criticality']} "
                      f"but no backup_policy_refs defined"
                  )
  ```

**Validation after Phase 2**:
```bash
python3 topology-tools/validate-topology.py
# New validation rules should catch missing backup policies
```

---

### Phase 3: L4 Resource Profiles

**Status**: Not Started
**Estimated effort**: 1 session

**Goal**: Create reusable resource profiles for LXC/VM sizing.

**Current state**:
```yaml
lxc:
- id: lxc-postgresql
  resources:
    cores: 2
    memory_mb: 1024
    swap_mb: 1024
  # Inline, no reuse
```

**Target state**:
```yaml
# resource-profiles/default.yaml
resource_profiles:
- id: profile-minimal
  description: Lightweight services (DNS, small proxies)
  cpu:
    cores: 1
    limit_percent: 50
  memory:
    mb: 256
    swap_mb: 128
  storage:
    rootfs_gb: 4

- id: profile-database
  description: Database-optimized (higher memory, tuned swappiness)
  cpu:
    cores: 2
    limit_percent: 100
  memory:
    mb: 1024
    swap_mb: 1024
  storage:
    rootfs_gb: 8
  tuning:
    vm_swappiness: 10
    dirty_ratio: 40

# lxc/databases.yaml
lxc:
- id: lxc-postgresql
  resource_profile_ref: profile-database    # Reference instead of inline
  # Can still override specific values if needed
  resources_override:
    memory_mb: 2048  # Override profile default
```

**Tasks**:

- [ ] **3.1** Create `topology/L4-platform/` directory structure
  ```bash
  mkdir -p topology/L4-platform/{resource-profiles,lxc,vms,templates}
  ```

- [ ] **3.2** Define `ResourceProfile` schema
  ```json
  {
    "ResourceProfile": {
      "type": "object",
      "required": ["id", "description"],
      "properties": {
        "id": { "pattern": "^profile-[a-z0-9-]+$" },
        "description": { "type": "string" },
        "cpu": {
          "type": "object",
          "properties": {
            "cores": { "type": "integer", "minimum": 1 },
            "limit_percent": { "type": "integer", "minimum": 1, "maximum": 100 }
          }
        },
        "memory": {
          "type": "object",
          "properties": {
            "mb": { "type": "integer", "minimum": 64 },
            "swap_mb": { "type": "integer", "minimum": 0 }
          }
        },
        "storage": {
          "type": "object",
          "properties": {
            "rootfs_gb": { "type": "integer", "minimum": 1 }
          }
        },
        "tuning": {
          "type": "object",
          "properties": {
            "vm_swappiness": { "type": "integer", "minimum": 0, "maximum": 100 },
            "dirty_ratio": { "type": "integer", "minimum": 0, "maximum": 100 }
          }
        }
      }
    }
  }
  ```

- [ ] **3.3** Create `resource-profiles/default.yaml` with standard profiles
  - `profile-minimal`: 1 core, 256MB, 4GB rootfs
  - `profile-standard`: 1 core, 512MB, 8GB rootfs
  - `profile-database`: 2 cores, 1024MB, 8GB rootfs, tuned
  - `profile-compute`: 2 cores, 2048MB, 8GB rootfs
  - `profile-memory-heavy`: 1 core, 4096MB, 8GB rootfs

- [ ] **3.4** Update LXC schema to support `resource_profile_ref`
  ```json
  {
    "Lxc": {
      "properties": {
        "resource_profile_ref": { "$ref": "#/definitions/ResourceProfileRef" },
        "resources_override": {
          "type": "object",
          "description": "Override specific profile values"
        }
      }
    }
  }
  ```

- [ ] **3.5** Update Terraform generator to resolve profiles
  ```python
  def get_lxc_resources(lxc: dict, profiles: list[dict]) -> dict:
      """Resolve resource profile with optional overrides."""
      profile_ref = lxc.get('resource_profile_ref')
      if profile_ref:
          profile = find_by_id(profiles, profile_ref)
          resources = deep_copy(profile)
      else:
          resources = lxc.get('resources', {})

      # Apply overrides
      overrides = lxc.get('resources_override', {})
      deep_merge(resources, overrides)

      return resources
  ```

---

### Phase 4: L4 Volume Mounts with Data Asset Linkage

**Status**: Not Started
**Estimated effort**: 2 sessions

**Goal**: Add LXC volume mounts that link to L3 data assets.

**Current state**:
```yaml
lxc:
- id: lxc-postgresql
  storage:
    rootfs:
      storage_ref: storage-lvm
      size_gb: 8
  # No additional volumes
  # No link to data_assets
```

**Target state**:
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
      description: PostgreSQL data directory
```

**Tasks**:

- [ ] **4.1** Define `StorageVolume` schema
  ```json
  {
    "StorageVolume": {
      "type": "object",
      "required": ["id", "mount_point", "storage_endpoint_ref", "size_gb"],
      "properties": {
        "id": { "pattern": "^vol-[a-z0-9-]+$" },
        "mount_point": { "type": "string", "pattern": "^/.*" },
        "storage_endpoint_ref": { "$ref": "#/definitions/StorageEndpointRef" },
        "size_gb": { "type": "integer", "minimum": 1 },
        "data_asset_ref": { "$ref": "#/definitions/DataAssetRef" },
        "backup": { "type": "boolean" },
        "readonly": { "type": "boolean" },
        "description": { "type": "string" }
      }
    }
  }
  ```

- [ ] **4.2** Update LXC schema to include `storage.volumes`
  ```json
  {
    "Lxc": {
      "properties": {
        "storage": {
          "type": "object",
          "properties": {
            "rootfs": { "$ref": "#/definitions/LxcRootfs" },
            "volumes": {
              "type": "array",
              "items": { "$ref": "#/definitions/StorageVolume" }
            }
          }
        }
      }
    }
  }
  ```

- [ ] **4.3** Add cross-layer validation
  ```python
  def check_volume_data_asset_refs(lxc_list, data_assets, errors):
      """Validate that volume data_asset_refs exist in L3."""
      asset_ids = {a['id'] for a in data_assets}

      for lxc in lxc_list:
          for vol in lxc.get('storage', {}).get('volumes', []):
              ref = vol.get('data_asset_ref')
              if ref and ref not in asset_ids:
                  errors.append(
                      f"lxc '{lxc['id']}' volume '{vol['id']}' references "
                      f"non-existent data_asset '{ref}'"
                  )
  ```

- [ ] **4.4** Update lxc-postgresql with volumes
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
        data_asset_ref: data-postgresql-main
        backup: true
        description: PostgreSQL PGDATA directory
  ```

- [ ] **4.5** Update Terraform generator for LXC volumes
  ```hcl
  # Generated lxc.tf should include:
  resource "proxmox_virtual_environment_container" "lxc_postgresql" {
    # ...
    disk {
      datastore_id = "local-lvm"
      size         = 8
    }

    mount_point {
      volume = "local-lvm:vm-200-disk-1"
      path   = "/var/lib/postgresql/data"
      size   = "20G"
    }
  }
  ```

- [ ] **4.6** Update backup generator to use volume.backup flag
  ```python
  # When generating vzdump configs, include volumes marked backup: true
  def get_backup_volumes(lxc: dict) -> list[str]:
      return [
          vol['mount_point']
          for vol in lxc.get('storage', {}).get('volumes', [])
          if vol.get('backup', False)
      ]
  ```

---

### Phase 5: L4 Platform Type Taxonomy

**Status**: Not Started
**Estimated effort**: 1 session

**Goal**: Replace application-focused `type`/`role` with platform-focused taxonomy.

**Current state**:
```yaml
LxcType: [database, cache, web, application, utility, proxy]
LxcRole: [database-server, cache-server, web-server, app-server, proxy-server]

lxc:
- id: lxc-postgresql
  type: database           # Application role, not platform characteristic
  role: database-server    # Redundant with type
```

**Target state**:
```yaml
PlatformType: [lxc-privileged, lxc-unprivileged, lxc-nested,
               vm-bios, vm-uefi, vm-cloud-init]

lxc:
- id: lxc-postgresql
  platform_type: lxc-unprivileged
  resource_profile_ref: profile-database
  # Application role moved to L5 services
```

**Tasks**:

- [ ] **5.1** Define `PlatformType` enum in schema
  ```json
  {
    "PlatformType": {
      "type": "string",
      "enum": [
        "lxc-privileged",
        "lxc-unprivileged",
        "lxc-nested",
        "vm-bios",
        "vm-uefi",
        "vm-cloud-init"
      ]
    }
  }
  ```

- [ ] **5.2** Remove `LxcType` and `LxcRole` from schema
  - Add deprecation warning in validator first
  - Remove in next major version

- [ ] **5.3** Update LXC definitions with `platform_type`
  ```yaml
  lxc:
  - id: lxc-postgresql
    platform_type: lxc-unprivileged
    # Remove: type: database
    # Remove: role: database-server
  ```

- [ ] **5.4** Move application role to tags
  ```yaml
  lxc:
  - id: lxc-postgresql
    platform_type: lxc-unprivileged
    tags: [database, postgresql, production]
    # Tags used for Ansible group membership
  ```

- [ ] **5.5** Update Ansible inventory generator
  ```python
  # Use tags instead of type/role for group membership
  def get_lxc_groups(lxc: dict) -> list[str]:
      groups = ['lxc_containers']
      for tag in lxc.get('tags', []):
          groups.append(f"tag_{tag}")
      return groups
  ```

---

### Phase 6: Remove Application Config from L4

**Status**: Not Started
**Estimated effort**: 2 sessions

**Goal**: Move application configuration from `lxc.ansible.vars` to L5 `services.config`.

**Current state**:
```yaml
# L4 lxc contains application config:
lxc:
- id: lxc-postgresql
  ansible:
    vars:
      postgresql_version: '16'
      postgresql_listen_addresses: 10.0.30.10
      postgresql_databases:
      - name: nextcloud
      postgresql_users:
      - name: nextcloud
        password: '{{ vault_... }}'
```

**Target state**:
```yaml
# L4 lxc - platform only:
lxc:
- id: lxc-postgresql
  platform_type: lxc-unprivileged
  resource_profile_ref: profile-database
  ansible:
    enabled: true
    # NO vars with application config

# L5 services - application config:
services:
- id: svc-postgresql
  runtime:
    type: lxc
    lxc_ref: lxc-postgresql
  config:
    engine: postgresql
    version: '16'
    listen_addresses: '0.0.0.0'
    max_connections: 50
    shared_buffers: 256MB
    databases:
    - name: nextcloud
      owner: nextcloud
    - name: homelab
      owner: app
    users:
    - name: nextcloud
      password: '{{ vault_postgresql_nextcloud_password }}'
      database: nextcloud
    pg_hba:
    - type: host
      database: nextcloud
      user: nextcloud
      address: 10.0.30.50/32
      method: scram-sha-256
```

**Tasks**:

- [ ] **6.1** Add `config` field to Service schema
  ```json
  {
    "Service": {
      "properties": {
        "config": {
          "type": "object",
          "description": "Application-specific configuration",
          "additionalProperties": true
        }
      }
    }
  }
  ```

- [ ] **6.2** Create service-specific config schemas (optional, for validation)
  ```json
  {
    "PostgresqlConfig": {
      "type": "object",
      "properties": {
        "engine": { "const": "postgresql" },
        "version": { "type": "string" },
        "listen_addresses": { "type": "string" },
        "max_connections": { "type": "integer" },
        "databases": { "type": "array" },
        "users": { "type": "array" },
        "pg_hba": { "type": "array" }
      }
    }
  }
  ```

- [ ] **6.3** Migrate postgresql config from L4 to L5
  - Move `lxc.ansible.vars.postgresql_*` → `service.config.*`
  - Keep L4 `ansible.enabled: true` without vars

- [ ] **6.4** Migrate redis config from L4 to L5
  - Move `lxc.ansible.vars.redis_*` → `service.config.*`

- [ ] **6.5** Add deprecation warning for L4 application config
  ```python
  APPLICATION_CONFIG_KEYS = [
      'postgresql_', 'redis_', 'nginx_', 'mysql_',
      'nextcloud_', 'grafana_', 'prometheus_'
  ]

  def check_l4_application_config(lxc_list, errors, warnings):
      for lxc in lxc_list:
          ansible_vars = lxc.get('ansible', {}).get('vars', {})
          for key in ansible_vars:
              for prefix in APPLICATION_CONFIG_KEYS:
                  if key.startswith(prefix):
                      warnings.append(
                          f"lxc '{lxc['id']}' contains application config "
                          f"'{key}' in ansible.vars. "
                          f"Move to L5 services.config (see ADR-0026)"
                      )
  ```

- [ ] **6.6** Update Ansible inventory generator
  ```python
  # Generate host_vars from L5 services.config instead of L4 ansible.vars
  def generate_host_vars(services: list, lxc_list: list) -> dict:
      host_vars = {}
      for svc in services:
          lxc_ref = svc.get('runtime', {}).get('lxc_ref')
          if lxc_ref:
              lxc = find_by_id(lxc_list, lxc_ref)
              hostname = lxc['name']
              host_vars[hostname] = svc.get('config', {})
      return host_vars
  ```

---

### Phase 7: L5 Unified Runtime Model

**Status**: Not Started
**Estimated effort**: 1-2 sessions

**Goal**: Replace mixed `device_ref`/`lxc_ref`/`container: true` with unified `runtime`.

**Current state**:
```yaml
services:
# LXC service:
- id: svc-postgresql
  lxc_ref: lxc-postgresql
  ip: 10.0.30.10              # Duplicated from L4

# Docker service:
- id: svc-nextcloud
  device_ref: orangepi5
  container: true
  container_runtime: docker
  container_image: nextcloud:28
  ip: 10.0.30.50

# Native service:
- id: svc-wireguard
  device_ref: mikrotik-chateau
  native: true
```

**Target state**:
```yaml
services:
# LXC service:
- id: svc-postgresql
  runtime:
    type: lxc
    lxc_ref: lxc-postgresql
    # IP resolved from lxc.networks[0].ip - NO duplication

# Docker service:
- id: svc-nextcloud
  runtime:
    type: docker
    device_ref: orangepi5
    image: nextcloud:28
    # IP resolved from device or explicit

# Native service:
- id: svc-wireguard
  runtime:
    type: native
    device_ref: mikrotik-chateau
```

**Tasks**:

- [ ] **7.1** Define `ServiceRuntime` schema
  ```json
  {
    "ServiceRuntime": {
      "type": "object",
      "required": ["type"],
      "properties": {
        "type": {
          "type": "string",
          "enum": ["lxc", "vm", "docker", "podman", "native", "external"]
        },
        "lxc_ref": { "$ref": "#/definitions/LxcRef" },
        "vm_ref": { "$ref": "#/definitions/VmRef" },
        "device_ref": { "$ref": "#/definitions/DeviceRef" },
        "image": { "type": "string" },
        "compose_file": { "type": "string" }
      }
    }
  }
  ```

- [ ] **7.2** Update Service schema
  ```json
  {
    "Service": {
      "properties": {
        "runtime": { "$ref": "#/definitions/ServiceRuntime" },
        "data_asset_refs": {
          "type": "array",
          "items": { "$ref": "#/definitions/DataAssetRef" }
        }
      }
    }
  }
  ```

- [ ] **7.3** Migrate services to use `runtime`
  - Convert `lxc_ref: X` → `runtime: { type: lxc, lxc_ref: X }`
  - Convert `device_ref: X, container: true` → `runtime: { type: docker, device_ref: X }`
  - Convert `device_ref: X, native: true` → `runtime: { type: native, device_ref: X }`

- [ ] **7.4** Remove deprecated fields from Service schema
  - Remove: `lxc_ref` (moved to runtime)
  - Remove: `device_ref` (moved to runtime)
  - Remove: `container`, `container_runtime`, `container_image`
  - Remove: `native`

- [ ] **7.5** Add `data_asset_refs` to services
  ```yaml
  services:
  - id: svc-postgresql
    runtime:
      type: lxc
      lxc_ref: lxc-postgresql
    data_asset_refs:
    - data-postgresql-main        # ← L3 link

  - id: svc-nextcloud
    runtime:
      type: docker
      device_ref: orangepi5
      image: nextcloud:28
    data_asset_refs:
    - data-nextcloud              # ← L3 link (resolves mount paths)
    dependencies:
    - service_ref: svc-postgresql
    - service_ref: svc-redis
  ```

- [ ] **7.6** Add validation: runtime.lxc_ref must exist
  ```python
  def check_service_runtime_refs(services, lxc_list, vm_list, devices, errors):
      lxc_ids = {l['id'] for l in lxc_list}

      for svc in services:
          runtime = svc.get('runtime', {})

          if runtime.get('type') == 'lxc':
              ref = runtime.get('lxc_ref')
              if ref and ref not in lxc_ids:
                  errors.append(
                      f"service '{svc['id']}' runtime.lxc_ref '{ref}' "
                      f"does not exist in L4.lxc"
                  )
  ```

---

### Phase 8: Remove external_services and IP Duplication

**Status**: Not Started
**Estimated effort**: 1 session

**Goal**: Eliminate `external_services` section and IP duplication.

**Current state**:
```yaml
# L5 has both services AND external_services:
services:
- id: svc-nextcloud
  ip: 10.0.30.50
  # ... partial definition

external_services:
- id: ext-orangepi5
  ip: 10.0.30.50              # Duplicated!
  docker_services:
  - name: nextcloud
    image: nextcloud:28
    volumes:
    - /mnt/nvme/nextcloud/... # Hardcoded paths
```

**Target state**:
```yaml
# Single services list, no external_services:
services:
- id: svc-nextcloud
  runtime:
    type: docker
    device_ref: orangepi5
    image: nextcloud:28
  # IP resolved from device network config or explicit override
  data_asset_refs:
  - data-nextcloud            # Paths resolved from L3
```

**Tasks**:

- [ ] **8.1** Remove `external_services` from schema
  - Add deprecation warning first
  - Remove field from L5 schema

- [ ] **8.2** Migrate external_services content to services
  - Each `docker_services[]` entry becomes a full service with `runtime.type: docker`
  - Volume paths replaced with `data_asset_refs`

- [ ] **8.3** Remove IP from services that have runtime refs
  ```python
  def check_service_ip_duplication(services, lxc_list, errors, warnings):
      for svc in services:
          runtime = svc.get('runtime', {})

          if runtime.get('lxc_ref'):
              lxc = find_by_id(lxc_list, runtime['lxc_ref'])
              lxc_ip = lxc['networks'][0]['ip'].split('/')[0]
              svc_ip = svc.get('ip')

              if svc_ip and svc_ip != lxc_ip:
                  errors.append(
                      f"service '{svc['id']}' has ip={svc_ip} but "
                      f"runtime.lxc_ref points to lxc with ip={lxc_ip}"
                  )
              elif svc_ip:
                  warnings.append(
                      f"service '{svc['id']}' has redundant ip field. "
                      f"IP is resolved from runtime.lxc_ref"
                  )
  ```

- [ ] **8.4** Update docs generator to resolve IPs from runtime
  ```python
  def get_service_ip(service: dict, lxc_list: list, devices: list) -> str:
      """Resolve service IP from runtime reference."""
      runtime = service.get('runtime', {})

      if runtime.get('lxc_ref'):
          lxc = find_by_id(lxc_list, runtime['lxc_ref'])
          return lxc['networks'][0]['ip'].split('/')[0]

      if runtime.get('device_ref'):
          # Use explicit IP or resolve from device
          return service.get('ip') or resolve_device_ip(runtime['device_ref'])

      return service.get('ip', 'unknown')
  ```

---

### Phase 9: Schema and Generator Updates

**Status**: Not Started
**Estimated effort**: 2-3 sessions

**Goal**: Update JSON Schema and all generators for new structure.

**Tasks**:

- [ ] **9.1** Update `topology-v4-schema.json` with all new types
  - PartitionType, VolumeGroupType, LogicalVolumeType
  - FilesystemType, MountPoint
  - StorageEndpoint (replaces Storage)
  - DataAssetCategory, Criticality
  - ResourceProfile, PlatformType
  - ServiceRuntime

- [ ] **9.2** Add cross-layer reference validation to schema
  ```json
  {
    "$defs": {
      "StorageEndpointRef": {
        "type": "string",
        "pattern": "^se-[a-z0-9-]+$"
      },
      "MountPointRef": {
        "type": "string",
        "pattern": "^mp-[a-z0-9-]+$"
      }
    }
  }
  ```

- [ ] **9.3** Update Terraform Proxmox generator
  - Resolve `storage_endpoint_ref` → actual storage name
  - Generate LXC volumes from `storage.volumes`
  - Use resource profiles for CPU/memory

- [ ] **9.4** Update Terraform MikroTik generator
  - No direct L3/L4 changes, but verify compatibility

- [ ] **9.5** Update Ansible inventory generator
  - Generate host_vars from L5 `services.config`
  - Use tags for group membership
  - Resolve data_asset paths for volume mounts

- [ ] **9.6** Update docs generator
  - New storage chain documentation
  - Data asset inventory with criticality
  - Service runtime types

- [ ] **9.7** Add comprehensive validator rules
  ```python
  # validators/cross_layer.py
  def validate_l3_l4_l5_chain(topology, errors, warnings):
      """Validate complete cross-layer reference chain."""

      # L3 internal
      validate_partition_media_refs(topology, errors)
      validate_vg_partition_refs(topology, errors)
      validate_lv_vg_refs(topology, errors)
      validate_storage_endpoint_refs(topology, errors)

      # L3 → L4
      validate_lxc_storage_endpoint_refs(topology, errors)
      validate_lxc_volume_data_asset_refs(topology, errors)

      # L4 → L5
      validate_service_runtime_refs(topology, errors)
      validate_service_data_asset_refs(topology, errors)

      # Cross-cutting
      validate_data_asset_backup_policies(topology, errors, warnings)
      validate_no_ip_duplication(topology, errors, warnings)
  ```

---

### Phase 10: Documentation and ADR Updates

**Status**: Not Started
**Estimated effort**: 1 session

**Goal**: Update all documentation to reflect new structure.

**Tasks**:

- [ ] **10.1** Update CLAUDE.md layer descriptions
  ```markdown
  | Layer | File | Contains |
  |-------|------|----------|
  | L3 | L3-data/ | partitions, volume_groups, logical_volumes, filesystems, mount_points, storage_endpoints, data_assets |
  | L4 | L4-platform/ | resource_profiles, lxc (platform-only), vms, templates |
  | L5 | L5-application.yaml | services (with runtime, config, data_asset_refs), certificates, dns |
  ```

- [ ] **10.2** Create migration guide document
  ```markdown
  # Migration Guide: L3/L4 Taxonomy Refactoring

  ## Breaking Changes
  - `storage` renamed to `storage_endpoints`
  - `lxc.type` and `lxc.role` removed
  - `external_services` removed
  - `lxc.ansible.vars` application config moved to L5

  ## Step-by-step Migration
  1. Run `python3 topology-tools/migrate-l3-l4.py --dry-run`
  2. Review proposed changes
  3. Run `python3 topology-tools/migrate-l3-l4.py`
  4. Validate: `python3 topology-tools/validate-topology.py`
  5. Regenerate: `python3 topology-tools/regenerate-all.py`
  ```

- [ ] **10.3** Update generated docs templates
  - `templates/docs/storage.md.j2` → storage chain visualization
  - `templates/docs/services.md.j2` → runtime types, data assets
  - `templates/docs/data-assets.md.j2` → new template

- [ ] **10.4** Mark ADR-0026 as Accepted after implementation

---

## High Priority

### 1. Topology Caching in Regeneration Pipeline

**Status**: Planned
**Complexity**: Medium
**Impact**: Performance improvement for full regeneration

**Problem**:
Currently `regenerate-all.py` runs each generator as a separate subprocess, causing the topology to be loaded and parsed 5+ times (once per generator).

**Solution**:
Implement shared topology caching:

```python
# Option A: In-memory cache (single process)
class TopologyCache:
    _instance: Dict[str, Any] = None

    @classmethod
    def get(cls, path: str) -> Dict[str, Any]:
        if cls._instance is None:
            cls._instance = load_topology(path)
        return cls._instance

# Option B: File-based cache (multi-process)
# Write parsed topology to .cache/topology.json
# Generators check mtime and use cache if fresh
```

**Files to modify**:
- `topology-tools/regenerate-all.py`
- `topology-tools/scripts/generators/common/topology.py`

**Estimated reduction**: Load time from ~0.5s × 5 = 2.5s → 0.5s (80% faster)

---

### 2. Parallel Generator Execution

**Status**: Planned
**Complexity**: Low
**Impact**: 2-3x faster regeneration

**Problem**:
Generators run sequentially but are completely independent.

**Solution**:
Use `concurrent.futures.ThreadPoolExecutor` or `ProcessPoolExecutor`:

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

generators = [
    ("Terraform (Proxmox)", "generate-terraform-proxmox.py"),
    ("Terraform (MikroTik)", "generate-terraform-mikrotik.py"),
    ("Ansible", "generate-ansible-inventory.py"),
    ("Documentation", "generate-docs.py"),
]

with ProcessPoolExecutor(max_workers=4) as executor:
    futures = {
        executor.submit(run_generator, name, script): name
        for name, script in generators
    }
    for future in as_completed(futures):
        name = futures[future]
        result = future.result()
        print(f"{name}: {'OK' if result == 0 else 'FAILED'}")
```

**Files to modify**:
- `topology-tools/regenerate-all.py`

**Considerations**:
- Validation must complete before generators start
- Output ordering may change (use buffered output per generator)
- Error handling for partial failures

---

### 3. Dry-Run Mode for Generators

**Status**: Planned
**Complexity**: Low
**Impact**: Safer preview of changes

**Problem**:
No way to preview what files would be generated/modified without actually writing them.

**Solution**:
Add `--dry-run` flag to all generators:

```python
class GeneratorCLI:
    def add_extra_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be generated without writing files"
        )

# In generator:
def write_file(self, path: Path, content: str) -> None:
    if self.dry_run:
        print(f"[DRY-RUN] Would write: {path} ({len(content)} bytes)")
        return
    path.write_text(content, encoding="utf-8")
```

**Files to modify**:
- `topology-tools/scripts/generators/common/base.py`
- All generator classes (add `dry_run` parameter)

**Output example**:
```
$ python3 generate-terraform-proxmox.py --dry-run
[DRY-RUN] Would write: generated/terraform/provider.tf (1234 bytes)
[DRY-RUN] Would write: generated/terraform/bridges.tf (567 bytes)
[DRY-RUN] Would write: generated/terraform/lxc.tf (2345 bytes)
...
Summary: 7 files would be written (12.3 KB total)
```

---

## Medium Priority

### 4. Generator Diff Mode

**Status**: Idea
**Complexity**: Medium
**Impact**: Better change visibility

**Problem**:
Hard to see what changed after regeneration without manual `git diff`.

**Solution**:
Add `--diff` flag that shows unified diff of changes:

```python
parser.add_argument(
    "--diff",
    action="store_true",
    help="Show diff of changes instead of writing"
)

# Use difflib.unified_diff() to compare old vs new content
```

---

### 5. Incremental Generation

**Status**: Idea
**Complexity**: High
**Impact**: Much faster for small changes

**Problem**:
Changing one LXC container regenerates all Terraform files.

**Solution**:
Track dependencies and only regenerate affected files:

```yaml
# .cache/generation-manifest.yaml
files:
  generated/terraform/lxc.tf:
    sources:
      - topology/L4-platform.yaml
      - topology/L2-network.yaml  # for bridge refs
    hash: sha256:abc123...
```

**Considerations**:
- Complex dependency tracking
- May not be worth it for current codebase size
- Risk of stale outputs if dependencies missed

---

### 6. Unit Tests for Generators

**Status**: Planned
**Complexity**: Medium
**Impact**: Regression prevention

**Problem**:
No automated tests for generator logic.

**Solution**:
Add pytest-based test suite:

```
topology-tools/tests/
├── conftest.py              # Fixtures (sample topologies)
├── generators/
│   ├── test_proxmox.py
│   ├── test_mikrotik.py
│   └── test_docs.py
└── validators/
    ├── test_storage.py
    └── test_network.py
```

**Test examples**:
```python
def test_proxmox_generates_bridges(sample_topology):
    gen = TerraformGenerator(sample_topology, "/tmp/out")
    gen.load_topology()
    gen.generate_bridges()

    content = (Path("/tmp/out") / "bridges.tf").read_text()
    assert "resource \"proxmox_virtual_environment_network_linux_bridge\"" in content

def test_vlan_tag_validation(sample_topology_with_vlan_mismatch):
    errors = []
    warnings = []
    check_vlan_tags(sample_topology_with_vlan_mismatch, errors=errors, warnings=warnings)
    assert len(errors) == 1
    assert "vlan_tag" in errors[0]
```

---

### 7. Schema Auto-Generation from Python Types

**Status**: Idea
**Complexity**: High
**Impact**: Single source of truth for types

**Problem**:
JSON Schema and Python dataclasses/TypedDicts can drift.

**Solution**:
Use `pydantic` models as source of truth:

```python
from pydantic import BaseModel

class LXCContainer(BaseModel):
    id: str
    name: str
    vmid: int
    template_ref: str
    networks: list[NetworkConfig]

# Auto-generate JSON Schema:
# LXCContainer.model_json_schema()
```

---

## Low Priority

### 8. Generator Plugin System

**Status**: Future
**Complexity**: High
**Impact**: Extensibility

Allow external generators via entry points:

```toml
# pyproject.toml
[project.entry-points."topology_tools.generators"]
custom = "my_package:CustomGenerator"
```

---

### 9. Watch Mode for Development

**Status**: Future
**Complexity**: Medium

Auto-regenerate on topology file changes:

```bash
python3 regenerate-all.py --watch
# Uses watchdog to monitor topology/ directory
```

---

### 10. Generation Metrics Dashboard

**Status**: Future
**Complexity**: Low

Track generation statistics over time:

```yaml
# .cache/metrics.yaml
runs:
  - timestamp: 2026-02-21T15:00:00
    duration_ms: 1920
    files_generated: 24
    topology_version: 4.0.0
```

---

## Completed

- [x] ADR-0025: Generator Protocol and CLI Base Class (2026-02-21)
- [x] 100% type hints for public functions (2026-02-21)
- [x] Comprehensive `__init__.py` exports (2026-02-21)
- [x] ADR-0026: L3/L4 Taxonomy Refactoring proposal (2026-02-21)

---

## Notes

- Priorities may shift based on actual pain points encountered
- High-impact/low-complexity items should be tackled first
- Consider ADR for any significant architectural change
- L3/L4 refactoring is foundational — complete before other major changes
