# Changelog

All notable changes to the home lab infrastructure configuration.

## [2.0.0] - 2025-10-10

### 🎉 Major Release - Topology v2.0

**Migration**: v1.1 → v2.0 complete. Old files archived in `archive/`.

### ✨ Added

#### Structure
- **Physical topology section**: Devices, locations, interfaces with MAC addresses
- **Logical topology section**: Reorganized networks, bridges, routing, firewall policies
- **Compute section**: Restructured VMs, LXC, templates with hierarchy
- **YAML anchors**: 8 reusable defaults for LXC configuration (reduce duplication)

#### Backup & Recovery (107 lines)
- 4 backup policies:
  - Daily VM backups (OPNsense) at 2 AM
  - Hourly PostgreSQL backups
  - Daily LXC services backup (Redis, Nextcloud) at 3 AM
  - Weekly full infrastructure backup (Sunday 1 AM)
- Backup verification with integrity checks
- Storage monitoring (80% warning, 90% critical)
- Retention policies: last/daily/weekly/monthly/yearly

#### Monitoring & Alerting (352 lines)
- 5 health check configurations:
  - Proxmox host (CPU, memory, disk, load, temperature, services)
  - OPNsense firewall (VM status, ports, ping)
  - PostgreSQL (LXC, port, process, query, connections)
  - Redis (LXC, port, process, redis_ping, memory)
  - Nextcloud (LXC, HTTP, nginx, php-fpm)
- Network monitoring (internet, internal connectivity)
- 6 alert rules (disk full, service down, memory critical, CPU high, backup failed, temperature)
- Notification channels: email (enabled), telegram (disabled)
- Monitoring dashboard (4 views)

#### Validation
- JSON Schema v7 (`schemas/topology-v2-schema.json`, 819 lines)
- New validator (`scripts/validate-topology.py`, 393 lines)
- Two-step validation: schema compliance + reference consistency
- Validates all `*_ref` fields point to existing IDs

#### Documentation
- `MIGRATION-V1-TO-V2.md` - Complete migration guide
- `archive/README.md` - Archive documentation
- `TOPOLOGY-V2-ANALYSIS.md` - Analysis and improvements
- `CHANGELOG.md` - This file

### 🔄 Changed
- **File size**: 17 KB → 43 KB (+153%)
- **Line count**: ~600 → 1594 (+165%)
- **Structure**: Flat → Hierarchical (physical/logical/compute)
- **Validator**: Custom Python → JSON Schema v7 based
- **References**: Hardcoded values → ID-based references throughout

### 📦 Deprecated
- Flat topology structure (v1.1)
- Direct top-level sections: `bridges`, `networks`, `vms`, `lxc`
- Old validator `validate-topology.py` (v1.1 format)

### 🗑️ Removed
- None (v1.1 files moved to `archive/` for reference)

### 🔧 Fixed
- N/A (new major version)

### 🔒 Security
- Enhanced trust zone definitions in logical topology
- Comprehensive firewall policy configuration
- SSH key management ready (to be implemented)

### 📊 Metrics

| Metric | v1.1 | v2.0 | Change |
|--------|------|------|--------|
| File size | 17 KB | 43 KB | +153% |
| Lines | ~600 | 1594 | +165% |
| Sections | 9 | 11 | +2 |
| Backup policies | 0 | 4 | +4 |
| Health checks | 0 | 5 | +5 |
| Alert rules | 0 | 6 | +6 |

---

## [1.1.0] - 2025-10-09

### ✨ Added
- Trust zones (5 levels: untrusted, dmz, user, internal, management)
- Enhanced metadata (author, created date, hardware disks)
- `trust_zone` field to all networks
- `bridge` field for explicit bridge mapping
- `managed_by` field for device ownership

### 🔄 Changed
- Improved metadata structure
- Better network-bridge consistency

### 🔧 Fixed
- Network validation improvements
- Trust zone reference validation

---

## [1.0.0] - 2025-10-06

### 🎉 Initial Release - Infrastructure as Data

**First version** of Infrastructure-as-Data topology for home lab.

### ✨ Added
- YAML topology structure
- Metadata section
- Network bridges (vmbr0, vmbr1, vmbr2, vmbr99)
- Networks (WAN, LAN, LXC Internal, Management)
- Storage configuration (SSD, HDD)
- VMs: OPNsense firewall
- LXC containers: PostgreSQL, Redis, Nextcloud
- Services inventory
- Basic validator script

### 📝 Structure
```yaml
metadata: {...}
bridges: [...]
networks: {...}
storage: [...]
vms: [...]
lxc: [...]
services: [...]
```

---

## Format

Based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

### Types of changes
- **✨ Added** - New features
- **🔄 Changed** - Changes in existing functionality
- **📦 Deprecated** - Soon-to-be removed features
- **🗑️ Removed** - Removed features
- **🔧 Fixed** - Bug fixes
- **🔒 Security** - Security fixes/improvements
- **📊 Metrics** - Measurements and statistics
