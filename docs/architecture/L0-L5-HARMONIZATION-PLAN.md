# L0-L5 Harmonization Plan (ADR-0043)

Status: Active
Date: 2026-02-24
Scope: L0-L5

## Goals

1. Consistent ID naming across layers
2. Complete data governance coverage
3. Cleaner trust zone model
4. Reduced cognitive load

## Phase 0: Quick Cleanup (Non-breaking) ✅ COMPLETE

### P0.1: Add missing data_asset_refs ✅

**Tasks**:
- [x] Create `data-loki.yaml` in L3
- [x] Create `data-alertmanager.yaml` in L3
- [x] Create `data-adguard-secondary.yaml` in L3
- [x] Add `data_asset_refs` to svc-loki
- [x] Add `data_asset_refs` to svc-alertmanager
- [x] Add `data_asset_refs` to svc-adguard-secondary

**Files**:
```
topology/L3-data/data-assets/data-loki.yaml (new)
topology/L3-data/data-assets/data-alertmanager.yaml (new)
topology/L3-data/data-assets/data-adguard-secondary.yaml (new)
topology/L5-application/services/orangepi5/monitoring.yaml (update)
```

**Acceptance**:
```bash
grep -c "data_asset_refs" topology/L5-application/services/orangepi5/monitoring.yaml
# Should return 5 (all monitoring services have refs)
```

### P0.2: Remove orphaned data assets ✅

**Tasks**:
- [x] Delete `data-postgresql-rootfs.yaml`
- [x] Delete `data-redis-rootfs.yaml`
- [x] Remove rootfs data_asset_ref from lxc-postgresql and lxc-redis

**Rationale**: LXC rootfs is infrastructure (managed by Proxmox backup), not application data.

**Files**:
```
topology/L3-data/data-assets/data-postgresql-rootfs.yaml (delete)
topology/L3-data/data-assets/data-redis-rootfs.yaml (delete)
```

**Acceptance**:
```bash
ls topology/L3-data/data-assets/ | grep -c rootfs
# Should return 0
```

### P0.3: Mark reserved trust zones ✅

**Tasks**:
- [x] Add `reserved: true` to `guest` zone
- [x] Add `reserved: true` to `untrusted` zone
- [x] Add `reserved` field to TrustZoneDefinition schema

**Files**:
```
topology/L2-network/trust-zones/baseline.yaml (update)
topology-tools/schemas/topology-v4-schema.json (update)
```

## Phase 1: Naming Harmonization (Breaking) ✅ COMPLETE

### P1.1: Standardize L1 device ID prefixes ✅

**Mapping**:
| Current | New | Class |
|---------|-----|-------|
| `gamayun` | `srv-gamayun` | compute |
| `orangepi5` | `srv-orangepi5` | compute |
| `mikrotik-chateau` | `rtr-mikrotik` | network |
| `slate-ax1800` | `rtr-slate` | network |
| `hetzner-cx22-nuremberg` | `vps-hetzner-nuremberg` | provider |
| `oracle-arm-frankfurt` | `vps-oracle-frankfurt` | provider |
| `ups-main` | `ups-main` | power (OK) |
| `pdu-rack-home` | `pdu-rack` | power |

**Tasks**:
- [x] Update L1 device files (rename + update id field)
- [x] Update all device_ref in L1 (data-links, power-links, media-attachments)
- [x] Update all device_ref in L2 (bridges, networks.ip_allocations, networks.managed_by_ref)
- [x] Update all device_ref in L3 (data_assets)
- [x] Update all device_ref, host_os[].device_ref in L4
- [x] Update all runtime.target_ref in L5
- [x] Update all device_ref in L5 (dns records)
- [x] Run validation

**Impact**: 95 files, ~200 refs updated

**Acceptance**:
```bash
grep -r "gamayun\|orangepi5" topology/ --include="*.yaml" | grep -v "srv-"
# Should return 0 matches (all updated to srv- prefix)
```

### P1.2: Split servers trust zone ✅

**Mapping**:
| Service | Current Zone | New Zone |
|---------|--------------|----------|
| svc-postgresql | servers | servers-data |
| svc-redis | servers | servers-data |
| svc-nextcloud | servers | servers-app |
| svc-jellyfin | servers | servers-app |
| svc-homeassistant | servers | servers-app |
| svc-prometheus | servers | servers-mon |
| svc-alertmanager | servers | servers-mon |
| svc-loki | servers | servers-mon |
| svc-grafana | servers | servers-mon |
| svc-adguard-secondary | servers | servers-mon |
| svc-adguard | servers | servers (keep, edge DNS) |
| svc-ntp | servers | servers (keep, infra) |
| svc-syslog-forward | servers | servers-mon |

**Tasks**:
- [x] Add `servers-data`, `servers-app`, `servers-mon` to trust zones
- [x] Add zone definitions to baseline.yaml
- [x] Update trust_zone_ref in all affected services
- [x] Update L4 LXC workloads trust_zone_ref
- [x] Run validation

**Files**:
```
topology/L2-network/trust-zones/baseline.yaml (update)
topology-tools/schemas/topology-v4-schema.json (update)
topology/L5-application/services/**/*.yaml (update refs)
topology/L4-platform/workloads/lxc/*.yaml (update refs)
```

## Phase 2: IP Derivation ✅ COMPLETE (ADR-0044)

### P2.1: Design IP resolution pattern ✅

**Implemented pattern (Option B - IpRef)**:
```yaml
ip_refs:
  postgres_host:
    lxc_ref: lxc-postgresql
    network_ref: net-servers
config:
  docker:
    environment:
      POSTGRES_HOST: '{{ ip_refs.postgres_host }}'
```

**Schema additions**:
- [x] IpRef definition (lxc_ref, vm_ref, host_os_ref, service_ref + network_ref)
- [x] ip_refs field on Service
- [x] url_derived field for automatic URL generation
- [x] url_port field for port override

### P2.2: Migrate services ✅

**Migrated**: 21 → 1 hardcoded IPs
- [x] svc-nextcloud (POSTGRES_HOST, REDIS_HOST)
- [x] svc-postgresql (listen_addresses, pg_hba)
- [x] svc-redis (bind)
- [x] svc-prometheus (scrape_targets)
- [x] svc-loki (log_sources)
- [x] svc-syslog-forward (remote_address)
- [x] All UI services (url_derived)

**Remaining**: `10.0.30.0/24` subnet in pg_hba (intentional - not a host IP)

### P2.3: Generator implementation

**Status**: Deferred - topology is prepared, generators need update to resolve refs.

When implemented, generators will:
1. Parse `ip_refs` from services
2. Resolve IPs from L2 ip_allocations or L4 workload networks
3. Substitute `{{ ip_refs.* }}` placeholders
4. Generate `url` from `url_derived` + runtime target IP

## Validation Gate

Run after each phase:

```bash
# 1. Strict validation
python3 topology-tools/validate-topology.py --topology topology.yaml --strict

# 2. Regenerate
python3 topology-tools/regenerate-all.py

# 3. Check for unexpected changes
git diff --stat generated/

# 4. Run fixture matrix
python3 topology-tools/run-fixture-matrix.py
```

## Execution Order

```
P0.1 (data assets)     ──┐
P0.2 (delete orphans)  ──┼── Can run in parallel
P0.3 (mark reserved)   ──┘
         │
         ▼
    [Validate + Commit P0]
         │
         ▼
P1.1 (device prefixes) ─── Sequential, breaking
         │
         ▼
    [Validate + Commit P1.1]
         │
         ▼
P1.2 (split zones)     ─── Sequential, breaking
         │
         ▼
    [Validate + Commit P1.2]
         │
         ▼
    [Future: P2 via ADR-0044]
```

## Rollback

```bash
# Restore from git
git checkout topology/

# Verify
python3 topology-tools/validate-topology.py --topology topology.yaml --strict
```
