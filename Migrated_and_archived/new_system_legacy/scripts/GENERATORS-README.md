# Infrastructure Generators for Topology v2.0

This directory contains Python generators that transform `topology.yaml` v2.0 into usable configurations.

## 📋 Available Generators

### 1. 🏗️ Terraform Generator

**File**: `generate-terraform.py`

Generates Proxmox Terraform configuration from topology.

**Usage**:
```bash
python3 scripts/generate-terraform.py [--topology topology.yaml] [--output generated/terraform/]
```

**Output directory**: `generated/terraform/` (auto-cleaned before generation)

**Generates**:
- `provider.tf` - Proxmox provider configuration
- `variables.tf` - Terraform variables
- `terraform.tfvars.example` - Example variables file
- `bridges.tf` - Network bridges (4 bridges)
- `vms.tf` - Virtual machines (1 VM)
- `lxc.tf` - LXC containers (3 containers)

**Requirements**:
```bash
pip install pyyaml jinja2
```

**Example**:
```bash
# Generate Terraform configs
python3 scripts/generate-terraform.py

# Initialize and apply
cd generated/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your credentials
terraform init
terraform plan
terraform apply
```

---

### 2. 📦 Ansible Inventory Generator

**File**: `generate-ansible-inventory.py`

Generates Ansible inventory and group variables from topology.

**Usage**:
```bash
python3 scripts/generate-ansible-inventory.py [--topology topology.yaml] [--output generated/ansible/inventory/<env>]
```

**Output directory**: `generated/ansible/inventory/<env>/` (auto-cleaned before generation)

**Generates**:
- `hosts.yml` - Ansible inventory with groups
  - `lxc_containers` - All LXC containers
  - `virtual_machines` - All VMs
  - Trust zone groups (`untrusted_zone`, `dmz_zone`, `user_zone`, `internal_zone`, `management_zone`)
  - Service type groups (`databases`, `web_applications`, `cache_servers`)
- `group_vars/all.yml` - Common variables (networks, DNS, packages)
- `host_vars/*.yml` - Per-host variables (from `ansible.vars` in topology)

**Requirements**:
```bash
pip install pyyaml jinja2
```

**Example**:
```bash
# Generate Ansible inventory
python3 scripts/generate-ansible-inventory.py

# Test connectivity
ansible all -i generated/ansible/inventory/<env>/hosts.yml -m ping

# Run playbooks
ansible-playbook -i generated/ansible/inventory/<env>/hosts.yml playbooks/site.yml
```

---

### 3. 📚 Documentation Generator

**File**: `generate-docs.py`

Generates Markdown documentation from topology.

**Usage**:
```bash
python3 scripts/generate-docs.py [--topology topology.yaml] [--output generated/docs/]
```

**Output directory**: `generated/docs/` (auto-cleaned before generation)

**Generates**:
- `overview.md` - Infrastructure overview with statistics
- `network-diagram.md` - Network topology diagram (Mermaid)
- `ip-allocation.md` - IP address allocation tables
- `services.md` - Services inventory with dependencies
- `devices.md` - Physical devices, VMs, LXC, storage inventory

**Requirements**:
```bash
pip install pyyaml jinja2
```

**Example**:
```bash
# Generate documentation
python3 scripts/generate-docs.py

# View with Markdown preview (VSCode, GitHub, etc.)
```

---

## 🗂️ Directory Structure

```
new_system/
├── topology.yaml                   # 📝 SOURCE OF TRUTH
├── .gitignore                      # Ignores generated/ directory
├── generated/                      # ⚠️  AUTO-GENERATED (DO NOT EDIT!)
│   ├── terraform/
│   │   ├── provider.tf
│   │   ├── bridges.tf
│   │   ├── vms.tf
│   │   ├── lxc.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars.example
│   ├── ansible/
│   │   └── inventory/
│   │       └── production/
│   │           ├── hosts.yml
│   │           ├── group_vars/all.yml
│   │           └── host_vars/*.yml
│   └── docs/
│       ├── overview.md
│       ├── network-diagram.md
│       ├── ip-allocation.md
│       ├── services.md
│       └── devices.md
├── scripts/
│   ├── generate-terraform.py       # Terraform generator
│   ├── generate-ansible-inventory.py  # Ansible inventory generator
│   ├── generate-docs.py             # Documentation generator
│   ├── validate-topology.py         # JSON Schema v7 validator
│   ├── regenerate-all.py            # ⭐ Regenerate everything
│   └── templates/                   # Jinja2 templates
│       ├── terraform/
│       │   ├── provider.tf.j2
│       │   ├── bridges.tf.j2
│       │   ├── vms.tf.j2
│       │   ├── lxc.tf.j2
│       │   ├── variables.tf.j2
│       │   └── terraform.tfvars.example.j2
│       ├── ansible/
│       │   ├── hosts.yml.j2
│       │   ├── group_vars_all.yml.j2
│       │   └── host_vars.yml.j2
│       └── docs/
│           ├── overview.md.j2
│           ├── network-diagram.md.j2
│           ├── ip-allocation.md.j2
│           ├── services.md.j2
│           └── devices.md.j2
└── ansible/
    ├── playbooks/                   # ✏️  Manual (service logic)
    └── roles/                       # ✏️  Manual (reusable roles)
```

**Key principle**:
- ✏️  **Edit**: `topology.yaml`, `ansible/playbooks/`, `ansible/roles/`
- ⚠️  **DO NOT EDIT**: `generated/*` (auto-regenerated, changes will be lost!)

---

## 🚀 Quick Start

### Regenerate Everything (Recommended)

```bash
# ⭐ ONE COMMAND to regenerate everything
python3 scripts/regenerate-all.py

# This will:
# 1. Clean generated/ directory
# 2. Validate topology
# 3. Generate Terraform → generated/terraform/
# 4. Generate Ansible → generated/ansible/
# 5. Generate docs → generated/docs/
```

### Regenerate Individual Components

```bash
# 1. Validate topology
python3 scripts/validate-topology.py

# 2. Generate Terraform only
python3 scripts/generate-terraform.py

# 3. Generate Ansible inventory only
python3 scripts/generate-ansible-inventory.py

# 4. Generate documentation only
python3 scripts/generate-docs.py
```

**Note**: Each generator automatically **cleans** its output directory before generating files!

---

## 📝 Topology v2.0 Structure

Generators read from these topology sections:

| Generator | Reads From |
|-----------|------------|
| **Terraform** | `physical_topology.devices`, `logical_topology.bridges`, `compute.vms`, `compute.lxc`, `storage` |
| **Ansible** | `compute.vms`, `compute.lxc`, `logical_topology.networks`, `logical_topology.trust_zones` |
| **Documentation** | All sections |

---

## 🔄 When to Regenerate

**ALWAYS regenerate after editing topology.yaml:**

- ✅ Added/removed VM or LXC
- ✅ Changed IP address
- ✅ Added/removed network bridge
- ✅ Modified storage configuration
- ✅ Changed resource allocation
- ✅ Updated service definitions
- ✅ Modified trust zones or firewall rules

**Workflow**:
```bash
vim topology.yaml                         # 1. Edit topology
python3 scripts/regenerate-all.py         # 2. Regenerate everything
cd generated/terraform && terraform plan  # 3. Review changes
```

**Or step-by-step**:
```bash
vim topology.yaml                         # 1. Edit
python3 scripts/validate-topology.py      # 2. Validate
python3 scripts/generate-terraform.py     # 3. Regenerate Terraform
python3 scripts/generate-ansible-inventory.py  # 4. Regenerate Ansible
python3 scripts/generate-docs.py          # 5. Regenerate docs
cd generated/terraform && terraform plan  # 6. Review changes
```

---

## 🛠️ Customizing Templates

Templates are in `scripts/templates/` and use Jinja2 syntax.

**Example**: Customize Terraform output:

```bash
vim scripts/templates/terraform/lxc.tf.j2
# Make changes
python3 scripts/generate-terraform.py  # Regenerate
```

**Template variables available**:
- `topology_version` - Topology version (e.g., "2.0.0")
- `generated_at` - Generation timestamp
- All topology sections: `networks`, `bridges`, `vms`, `lxc`, `services`, etc.

---

## 🐛 Troubleshooting

### Generator Errors

```bash
# Check Python version (requires 3.7+)
python3 --version

# Install dependencies
pip install pyyaml jinja2

# Validate topology first
python3 scripts/validate-topology.py

# Run generator with full output
python3 scripts/generate-terraform.py --topology topology.yaml --output terraform/
```

### Common Issues

**1. "Missing required section"**
- Solution: Ensure topology.yaml has all required v2.0 sections

**2. "Template not found"**
- Solution: Check `scripts/templates/` directory exists with all `.j2` files

**3. "Reference validation failed"**
- Solution: Run `python3 scripts/validate-topology.py` to find broken references

---

## 📊 Generated Files Summary

| Generator | Files | Size | Time |
|-----------|-------|------|------|
| Terraform | 6 files | ~20 KB | <1s |
| Ansible | 3+ files | ~10 KB | <1s |
| Documentation | 5 files | ~20 KB | <1s |

**Total**: ~14 generated files from single `topology.yaml`

---

## ⚙️ Advanced Usage

### Generate to Different Locations

```bash
# Terraform to custom directory
python3 scripts/generate-terraform.py --output /path/to/custom/terraform

# Ansible to staging environment
python3 scripts/generate-ansible-inventory.py --output generated/ansible/inventory/staging

# Documentation to wiki
python3 scripts/generate-docs.py --output /wiki/infrastructure
```

**Important**: Custom output directories are NOT auto-cleaned. Use default `generated/` for auto-cleanup.

### Use with CI/CD

```yaml
# .github/workflows/validate-topology.yml
name: Validate Infrastructure
on: [push]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: pip install pyyaml jinja2 jsonschema
      - name: Validate topology
        run: python3 scripts/validate-topology.py
      - name: Generate configs
        run: |
          python3 scripts/generate-terraform.py
          python3 scripts/generate-ansible-inventory.py
          python3 scripts/generate-docs.py
```

---

## 📚 References

- **Topology Format**: See `topology.yaml` v3.0 structure
- **Schema**: `schemas/topology-v3-schema.json` (JSON Schema v7)
- **Validator**: `scripts/validate-topology.py`
- **Regenerate All**: `scripts/regenerate-all.py` ⭐
- **Migration Guide**: `MIGRATION-V1-TO-V2.md`
- **Changelog**: `CHANGELOG.md`
- **Git Ignore**: `.gitignore` (excludes `generated/`)

---

## ⚠️ Important Notes

### DO NOT Edit Generated Files

Files in `generated/` directory are **automatically regenerated** and **auto-cleaned**:
- ❌ DO NOT manually edit files in `generated/`
- ❌ DO NOT commit `generated/` to Git (it's gitignored)
- ✅ DO edit `topology.yaml` as the single source of truth
- ✅ DO edit `ansible/playbooks/` and `ansible/roles/` manually

### Generated Directory Structure

```
generated/
├── terraform/          # Cleaned before each terraform generation
├── ansible/            # Cleaned before each ansible generation
│   └── inventory/
│       └── production/
└── docs/               # Cleaned before each docs generation
```

Each generator **removes** its output directory before creating new files!

---

**Status**: ✅ All generators functional for topology v2.0
**Last Updated**: 2025-10-10
**Output**: `generated/` directory (gitignored, auto-cleaned)
