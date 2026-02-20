# Topology Migration: v1.1 → v2.0

**Migration Date**: 2025-10-10
**Status**: ✅ Complete

## Summary

Successfully migrated home lab infrastructure configuration from topology v1.1 to v2.0 with enhanced features.

## What Changed

### File Structure

**Before (v1.1):**
```
topology.yaml              (17 KB, flat structure)
topology-tools/validate-topology.py
```

**After (v2.0):**
```
topology.yaml              (43 KB, hierarchical structure)
archive/
  ├── topology-v1.1.yaml
  ├── topology-v1.1-backup.yaml
  ├── validate-topology-v1.1.py
  └── README.md
topology-tools/topology-schemas/
  └── topology-v3-schema.json
topology-tools/
  └── validate-topology.py  (new JSON Schema v7 validator)
```

### Configuration Structure

| Section | v1.1 Location | v2.0 Location |
|---------|--------------|---------------|
| Physical devices | - | `physical_topology.devices` |
| Network bridges | `bridges` | `logical_topology.bridges` |
| Networks | `networks` | `logical_topology.networks` |
| Trust zones | `trust_zones` | `logical_topology.trust_zones` |
| Routing | - | `logical_topology.routing` |
| Firewall | - | `logical_topology.firewall_policies` |
| VMs | `vms` | `compute.vms` |
| LXC | `lxc` | `compute.lxc` |
| Templates | - | `compute.templates` |
| Storage | `storage` | `storage` |
| Services | `services` | `services` |
| Backup | - | `backup` ⭐ NEW |
| Monitoring | - | `monitoring` ⭐ NEW |
| Workflows | - | `workflows` ⭐ NEW |

## New Features in v2.0

### 1. ✅ Comprehensive Structure
- **Physical topology**: Devices, locations, interfaces with MAC addresses
- **Logical topology**: Networks, bridges, routing, firewall policies
- **Compute**: VMs, LXC, templates with YAML anchors for reusability

### 2. ✅ Backup Policies (107 lines)
- Daily VM backups (OPNsense)
- Hourly PostgreSQL backups
- Daily LXC service backups
- Weekly full infrastructure backup
- Backup verification and storage monitoring

### 3. ✅ Monitoring & Health Checks (352 lines)
- Proxmox host health monitoring
- VM/LXC status checks
- Service health checks (PostgreSQL, Redis, Nextcloud)
- Network connectivity monitoring
- Alert configuration with escalation
- Notification channels (email, telegram)

### 4. ✅ YAML Anchors (42 lines)
Reusable defaults for:
- OS configuration (`*default_lxc_os`)
- DNS settings (`*default_dns`)
- Boot configuration (`*default_lxc_boot`)
- Storage configuration (`*default_lxc_storage_rootfs`)
- Network settings (`*default_lxc_network_internal`)
- Cloud-init (`*default_lxc_cloudinit`)
- Ansible (`*default_ansible_enabled`)

**Benefits**: Reduced duplication, improved maintainability, consistency

### 5. ✅ JSON Schema v7 Validation
- File: `topology-tools/topology-schemas/topology-v3-schema.json` (819 lines)
- Type validation, enums, patterns, required fields
- Reference consistency checking
- Detailed error messages with paths

### 6. ✅ Enhanced Validator
- File: `topology-tools/validate-topology.py` (393 lines)
- Two-step validation: schema + references
- Validates all `*_ref` fields point to existing IDs
- Better error reporting

## Size Comparison

| Metric | v1.1 | v2.0 | Change |
|--------|------|------|--------|
| File size | 17 KB | 43 KB | +153% |
| Line count | ~600 | 1594 | +165% |
| Sections | 9 | 11 | +2 |
| VMs | 1 | 1 | - |
| LXC containers | 3 | 3 | - |
| Backup policies | 0 | 4 | +4 |
| Health checks | 0 | 5 | +5 |
| Alert rules | 0 | 6 | +6 |

**Reason for size increase**: Added backup policies (107 lines), monitoring/health checks (352 lines), and expanded metadata.

## Migration Steps Performed

### 1. Created Archive Directory
```bash
mkdir -p archive/
```

### 2. Archived v1.1 Files
```bash
mv topology.yaml archive/topology-v1.1.yaml
mv topology-v1.1-backup.yaml archive/topology-v1.1-backup.yaml
mv topology-tools/validate-topology.py archive/validate-topology-v1.1.py
```

### 3. Promoted v2.0 to Production
```bash
mv topology-v2.0.yaml topology.yaml
mv scripts/validate-with-schema.py topology-tools/validate-topology.py
```

### 4. Updated Validator Default Paths
```python
# topology-tools/validate-topology.py
parser.add_argument("--topology", default="topology.yaml")  # was topology-v2.0.yaml
parser.add_argument("--schema", default="topology-tools/topology-schemas/topology-v3-schema.json")
```

### 5. Created Documentation
- `archive/README.md` - Archive contents explanation
- `MIGRATION-V1-TO-V2.md` - This file
- Updated `TOPOLOGY-V2-ANALYSIS.md` - Marked Phase 1 complete

## Validation

```bash
# Validate new topology
python3 topology-tools/validate-topology.py

# Output:
# ✅ Validation PASSED
# ✓ Topology is valid according to JSON Schema v7
# ✓ All references are consistent
```

## Breaking Changes

### ⚠️ Generators Must Be Updated

Old v1.1 generators will NOT work with v2.0 topology:

**What needs updating:**
- `topology-tools/generate-terraform.py` - Must handle `physical_topology`, `logical_topology`, `compute` sections
- `topology-tools/generate-ansible-inventory.py` - Must handle new structure
- `topology-tools/generate-docs.py` - Must handle expanded sections

**TODO**: Implement v2.0-compatible generators

### ⚠️ Path Changes

| Resource | v1.1 Path | v2.0 Path |
|----------|-----------|-----------|
| Bridges | `bridges` | `logical_topology.bridges` |
| Networks | `networks` | `logical_topology.networks` |
| VMs | `vms` | `compute.vms` |
| LXC | `lxc` | `compute.lxc` |

## Rollback Procedure (NOT RECOMMENDED)

If you need to revert to v1.1:

```bash
# 1. Backup v2.0
cp topology.yaml topology-v2.0-backup.yaml

# 2. Restore v1.1
cp archive/topology-v1.1.yaml topology.yaml
cp archive/validate-topology-v1.1.py topology-tools/validate-topology.py

# 3. Validate
python3 topology-tools/validate-topology.py
```

**Note**: You will lose all v2.0 enhancements (backup policies, monitoring, YAML anchors).

## Next Steps

### Immediate
1. ✅ Migration complete
2. ✅ Validation passing
3. ✅ Documentation updated

### Short-term (Phase 2 - Optional)
From TOPOLOGY-V2-ANALYSIS.md:
- SSH Key Management (MEDIUM priority, 1h)
- DNS Records (MEDIUM priority, 1h)
- Firewall Templates (MEDIUM priority, 30min)
- Ansible Variables Structure (MEDIUM priority, 1h)

### Medium-term
1. **Update generators** for v2.0 structure:
   - `generate-terraform.py` - Handle new sections
   - `generate-ansible-inventory.py` - Parse new structure
   - `generate-docs.py` - Document expanded topology

2. **Implement backup automation** based on `backup.policies`

3. **Implement monitoring** based on `monitoring.healthchecks`

4. **Test deployment** with new topology structure

## Benefits Achieved

✅ **Better Organization**: Physical/logical/compute separation
✅ **Automation Ready**: Backup and monitoring configs defined
✅ **Less Duplication**: YAML anchors reduce repetition
✅ **Better Validation**: JSON Schema + reference checking
✅ **More Complete**: Comprehensive device specs, interfaces, dependencies
✅ **Production Ready**: 1594 lines of validated infrastructure-as-data

## References

- **Analysis**: `TOPOLOGY-V2-ANALYSIS.md` - 10 improvements identified
- **Archive**: `archive/README.md` - Legacy files documentation
- **Schema**: `topology-tools/topology-schemas/topology-v3-schema.json` - JSON Schema v7
- **Validator**: `topology-tools/validate-topology.py` - Validation tool

---

**Migration completed successfully** ✅
**Current topology**: `topology.yaml` (v2.0.0, 1594 lines)
**Status**: Production-ready
