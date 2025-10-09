# Changelog

All notable changes to the home lab infrastructure configuration.

## [2.1.0] - 2025-10-10

### 🎉 Phase 2 Improvements - Enhanced Configuration

**Phase**: 2 of 3 complete. Medium priority features implemented.

### ✨ Added

#### Security Configuration (107 lines)
- **SSH Key Management**: Centralized SSH key definitions
  - 3 SSH keys: admin-primary, automation, backup
  - Key types, purposes, expiration dates
  - `authorized_for` references to devices/VMs/LXC
  - SSH key deployment strategy (cloud-init, ansible, manual)
- **Certificate Management**: TLS certificate configuration
  - Self-signed wildcard certificate for `*.home.local`
  - Let's Encrypt certificate for VPN
  - Auto-renewal settings
  - `used_by` references to services
- **Security Policies**: Password, SSH, firewall policies
  - Password complexity requirements
  - SSH hardening settings
  - Firewall default actions

#### DNS Records (117 lines)
- **DNS Zones**: home.local zone configuration
  - Primary zone: home.local
  - 6 A records (gamayun, opnsense, postgresql, redis, nextcloud)
  - 3 CNAME records (db, cache, cloud)
  - 3 SRV records for service discovery (PostgreSQL, Redis, Nextcloud)
  - TTL configuration per record
- **DNS Forwarders**: Google, Cloudflare, local AdGuard
- **DNS Settings**: Recursion, DNSSEC, cache, query ACLs

#### Firewall Templates (42 lines)
- **5 Reusable Templates**: DRY principle for firewall rules
  - `tmpl-web-access`: HTTP/HTTPS (ports 80, 443)
  - `tmpl-database-access`: PostgreSQL, MySQL, Redis, MongoDB
  - `tmpl-ssh-access`: SSH with rate limiting (10 conn/60s)
  - `tmpl-management-access`: SSH, HTTPS, Proxmox, RDP
  - `tmpl-icmp-allow`: Ping and traceroute
- **Template Properties**: Ports, protocols, actions, rate limits

#### Ansible Configuration (197 lines)
- **Group Variables**: Structured group_vars
  - `all`: Common settings (user, python, packages, DNS, NTP)
  - `lxc_containers`: Cloud-init, security, monitoring
  - `databases`: Backup schedule, connection limits
  - `web_applications`: SSL, cert auto-renewal, rate limiting
- **Host Variables**: Detailed host-specific config
  - `postgresql-db`: Version, connections, databases, users, HBA entries
  - `redis-cache`: Port, bind, maxmemory, policy, save intervals
  - `nextcloud`: Version, domain, admin, DB config, Redis, trusted domains, apps
- **Playbook Mappings**: 4 playbooks defined
  - `site.yml`: Run all playbooks in order
  - `postgresql.yml`, `redis.yml`, `nextcloud.yml`: Service-specific
- **Vault Variables**: Placeholders for ansible-vault encryption
  - PostgreSQL passwords, Nextcloud admin password, Proxmox API token
- **Ansible Config**: ansible.cfg settings in topology

### 🔄 Changed
- **Version**: 2.0.0 → 2.1.0
- **File size**: 43 KB → 57 KB (+33%)
- **Line count**: 1594 → 2071 (+477 lines, +30%)
- **Metadata**: Updated last_updated to 2025-10-10

### 📊 Metrics

| Metric | v2.0.0 | v2.1.0 | Change |
|--------|--------|--------|--------|
| File size | 43 KB | 57 KB | +14 KB (+33%) |
| Lines | 1594 | 2071 | +477 (+30%) |
| SSH Keys | 0 | 3 | +3 |
| Certificates | 0 | 2 | +2 |
| DNS Records | 0 | 12 | +12 |
| Firewall Templates | 0 | 5 | +5 |
| Ansible Group Vars | 0 | 4 | +4 |
| Ansible Host Vars | 0 | 3 | +3 |

### 🎯 Implementation Time

| Feature | Estimated | Actual |
|---------|-----------|--------|
| SSH Key Management | 1h | 30min |
| DNS Records | 1h | 45min |
| Firewall Templates | 30min | 20min |
| Ansible Variables | 1h | 45min |
| **Total** | **3.5h** | **~2h** |

### ✅ Validation
- ✓ JSON Schema v7 validation passed
- ✓ All references consistent
- ✓ No breaking changes

---

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

#### Generators (3 Python scripts + 14 Jinja2 templates)
- **Terraform Generator** (`generate-terraform.py`, 327 lines)
  - Generates: provider.tf, bridges.tf, vms.tf, lxc.tf, variables.tf
  - 6 Terraform files from topology
  - 4 bridges, 1 VM, 3 LXC containers
- **Ansible Inventory Generator** (`generate-ansible-inventory.py`, 301 lines)
  - Generates: hosts.yml, group_vars/all.yml, host_vars/*.yml
  - Groups by trust zones and service types
  - 3+ Ansible files from topology
- **Documentation Generator** (`generate-docs.py`, 358 lines)
  - Generates: overview.md, network-diagram.md, ip-allocation.md, services.md, devices.md
  - Mermaid network diagrams
  - 5 Markdown files from topology
- **14 Jinja2 templates** in `scripts/templates/`

#### Documentation
- `MIGRATION-V1-TO-V2.md` - Complete migration guide
- `archive/README.md` - Archive documentation
- `TOPOLOGY-V2-ANALYSIS.md` - Analysis and improvements
- `scripts/GENERATORS-README.md` - Generators documentation
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
