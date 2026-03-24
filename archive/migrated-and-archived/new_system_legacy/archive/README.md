# Archive - Legacy Topology Files

This directory contains archived versions of topology configuration files.

## Contents

### Topology v1.1 (Archived 2025-10-10)

**Files:**
- `topology-v1.1.yaml` - Main topology configuration v1.1
- `topology-v1.1-backup.yaml` - Backup copy of v1.1
- `validate-topology-v1.1.py` - Validator script for v1.1 format

**Status:** Replaced by topology v2.0

**Structure:** Flat structure with top-level sections:
- `metadata`
- `bridges` (now in `logical_topology.bridges`)
- `networks` (now in `logical_topology.networks`)
- `trust_zones` (now in `logical_topology.trust_zones`)
- `vms` (now in `compute.vms`)
- `lxc` (now in `compute.lxc`)
- `storage`
- `services`

**Migration Date:** 2025-10-10

**Reason for Migration:**
- Better organization with physical/logical/compute separation
- ID-based references throughout
- Enhanced with backup policies and monitoring
- YAML anchors for reusability
- JSON Schema v7 validation

## Current Version

**Active topology:** `../topology.yaml` (v2.0.0)

**Structure:**
```yaml
version: "2.0.0"
metadata: {...}
physical_topology:
  locations: [...]
  devices: [...]
logical_topology:
  trust_zones: {...}
  networks: [...]
  bridges: [...]
  routing: [...]
  firewall_policies: [...]
compute:
  _defaults: {...}  # YAML anchors
  vms: [...]
  lxc: [...]
  templates: [...]
storage: [...]
services: [...]
backup: {...}       # NEW in v2.0
monitoring: {...}   # NEW in v2.0
workflows: {...}
documentation: {...}
```

## Restoration

To restore v1.1 (not recommended):
```bash
# Backup current v2.0
cp topology.yaml topology-v2.0-backup.yaml

# Restore v1.1
cp archive/topology-v1.1.yaml topology.yaml
cp archive/validate-topology-v1.1.py scripts/validate-topology.py

# Validate
python3 scripts/validate-topology.py
```

## Notes

- **DO NOT DELETE** these files - they serve as historical reference
- v2.0 is NOT backward compatible with v1.1 generators
- v1.1 validators will NOT work with v2.0 topology
- All new development should use v2.0 format
