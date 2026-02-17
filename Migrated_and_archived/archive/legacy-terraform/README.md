# Legacy Terraform Modules Archive

**Archived Date**: 2025-10-22
**Status**: DEPRECATED - For reference only

---

## Purpose of This Archive

This directory contains the **legacy Terraform modules and configuration** from `new_system/terraform/` that were used during the transition to the **Infrastructure-as-Data** approach.

The project has fully migrated to a generator-based system where all Terraform configuration is automatically generated from `new_system/topology.yaml`.

---

## What Was Archived

### Terraform Modules (`modules/`)
- **network/** - Manual bridge configuration (vmbr0, vmbr1, vmbr2, vmbr99)
  - Contained hardcoded bridge definitions
  - Example WiFi bridge (commented)
  - VLAN configuration variables

- **storage/** - Manual storage pool configuration
  - local-lvm (SSD production storage)
  - local-hdd (HDD templates/backups)
  - NFS storage example (commented)
  - Backup retention policies

### Configuration Files
- **providers.tf** - Proxmox provider configuration with backend, random, local, and TLS providers
- **versions.tf** - Required provider versions
- **variables.tf** - Network, hardware, and storage variables
- **outputs.tf** - Useful outputs for management URLs and infrastructure info
- **environments/** - Empty production/development directories

---

## Why Was This Archived?

**Migration to Infrastructure-as-Data**:
- All infrastructure is now defined in `new_system/topology.yaml`
- Terraform code is auto-generated via `scripts/generate-terraform.py`
- Generated output is in `new_system/generated/terraform/`

**Benefits of the new approach**:
- ✅ Single source of truth (topology.yaml)
- ✅ Automatic validation before generation
- ✅ No manual sync between documentation and code
- ✅ Easier to modify and regenerate
- ✅ Better integration with Ansible inventory generation

---

## What Was Migrated to topology.yaml

### Fully Migrated to topology.yaml ✅
- Network bridge definitions (vmbr0, vmbr1, vmbr2, vmbr99)
- Storage pool configuration (local, local-lvm, local-hdd)
- Backup retention policies
- Network CIDR blocks and IP allocations
- Hardware specifications

### Added as Examples in topology.yaml ⚠️
- WiFi bridge configuration (commented example)
- NFS storage configuration (commented example)

### Incorporated into Generated Configuration ✅
- Provider configuration (providers.tf) - now in `generated/terraform/provider.tf`
- Required versions (versions.tf) - now in `generated/terraform/versions.tf`
- Outputs (outputs.tf) - now in `generated/terraform/outputs.tf`

---

## How to Use This Archive

### For Reference Only
This code is **NOT** intended to be used directly. It is kept for:
- Understanding the original manual configuration approach
- Extracting useful comments and documentation
- Reference when writing new generator templates

### If You Need Something From This Archive
1. **DO NOT** copy code directly to `generated/terraform/`
2. **DO** add the configuration to `topology.yaml`
3. **DO** regenerate using `python3 scripts/generate-terraform.py`

---

## Current Terraform Workflow

```bash
# 1. Edit infrastructure in topology.yaml
vim new_system/topology.yaml

# 2. Validate topology
python3 new_system/scripts/validate-topology.py

# 3. Regenerate Terraform
python3 new_system/scripts/generate-terraform.py

# 4. Apply changes
cd new_system/generated/terraform
terraform init
terraform plan
terraform apply
```

---

## File Structure

```
archive/legacy-terraform/terraform/
├── modules/
│   ├── network/
│   │   ├── main.tf           # Bridge definitions
│   │   ├── variables.tf      # Network variables
│   │   ├── outputs.tf
│   │   └── README.md
│   └── storage/
│       ├── main.tf           # Storage pool definitions
│       ├── variables.tf      # Storage variables
│       ├── outputs.tf
│       └── README.md
├── environments/
│   ├── production/           # (empty)
│   └── development/          # (empty)
├── providers.tf              # Provider configuration
├── versions.tf               # Required providers
├── variables.tf              # Global variables
└── outputs.tf                # Infrastructure outputs
```

---

## Related Archives

- `old_system/` - Previous script-based infrastructure (will be archived here later)
- Future archives of legacy configurations will be placed in `archive/`

---

## Questions?

Refer to the current documentation:
- **CLAUDE.md** - Infrastructure-as-Data architecture guide
- **README.md** - Project overview
- **new_system/topology.yaml** - Current infrastructure definition

---

**Remember**: This is legacy code. Always work with topology.yaml and generated configurations.
