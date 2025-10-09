# Infrastructure Generators for Topology v2.0

This directory contains Python generators that transform `topology.yaml` v2.0 into usable configurations.

## 📋 Available Generators

### 1. 🏗️ Terraform Generator

**File**: `generate-terraform.py`

Generates Proxmox Terraform configuration from topology.

**Usage**:
```bash
python3 scripts/generate-terraform.py [--topology topology.yaml] [--output terraform/]
```

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
cd terraform
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
python3 scripts/generate-ansible-inventory.py [--topology topology.yaml] [--output ansible/inventory/production]
```

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
ansible all -i ansible/inventory/production/hosts.yml -m ping

# Run playbooks
ansible-playbook -i ansible/inventory/production/hosts.yml playbooks/site.yml
```

---

### 3. 📚 Documentation Generator

**File**: `generate-docs.py`

Generates Markdown documentation from topology.

**Usage**:
```bash
python3 scripts/generate-docs.py [--topology topology.yaml] [--output docs/]
```

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
scripts/
├── generate-terraform.py          # Terraform generator
├── generate-ansible-inventory.py  # Ansible inventory generator
├── generate-docs.py                # Documentation generator
├── validate-topology.py            # JSON Schema v7 validator
├── claude-logger.py                # Claude API logger
├── templates/                      # Jinja2 templates
│   ├── terraform/
│   │   ├── provider.tf.j2
│   │   ├── bridges.tf.j2
│   │   ├── vms.tf.j2
│   │   ├── lxc.tf.j2
│   │   ├── variables.tf.j2
│   │   └── terraform.tfvars.example.j2
│   ├── ansible/
│   │   ├── hosts.yml.j2
│   │   ├── group_vars_all.yml.j2
│   │   └── host_vars.yml.j2
│   └── docs/
│       ├── overview.md.j2
│       ├── network-diagram.md.j2
│       ├── ip-allocation.md.j2
│       ├── services.md.j2
│       └── devices.md.j2
└── GENERATORS-README.md           # This file
```

---

## 🚀 Quick Start

### Regenerate Everything

```bash
# 1. Validate topology
python3 scripts/validate-topology.py

# 2. Generate Terraform
python3 scripts/generate-terraform.py

# 3. Generate Ansible inventory
python3 scripts/generate-ansible-inventory.py

# 4. Generate documentation
python3 scripts/generate-docs.py
```

### Create Regenerate-All Script

Create `scripts/regenerate-all.py`:

```python
#!/usr/bin/env python3
import subprocess

scripts = [
    ("Validating topology", ["python3", "scripts/validate-topology.py"]),
    ("Generating Terraform", ["python3", "scripts/generate-terraform.py"]),
    ("Generating Ansible inventory", ["python3", "scripts/generate-ansible-inventory.py"]),
    ("Generating documentation", ["python3", "scripts/generate-docs.py"]),
]

for desc, cmd in scripts:
    print(f"\n{desc}...")
    subprocess.run(cmd, check=True)

print("\n✅ All generators completed successfully!")
```

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
vim topology.yaml                         # 1. Edit
python3 scripts/validate-topology.py     # 2. Validate
python3 scripts/generate-terraform.py    # 3. Regenerate Terraform
python3 scripts/generate-ansible-inventory.py  # 4. Regenerate Ansible
python3 scripts/generate-docs.py         # 5. Regenerate docs
cd terraform && terraform plan            # 6. Review changes
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
python3 scripts/generate-terraform.py --output /path/to/terraform

# Ansible to staging environment
python3 scripts/generate-ansible-inventory.py --output ansible/inventory/staging

# Documentation to wiki
python3 scripts/generate-docs.py --output /wiki/infrastructure
```

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

- **Topology Format**: See `topology.yaml` v2.0 structure
- **Schema**: `schemas/topology-v2-schema.json` (JSON Schema v7)
- **Validator**: `scripts/validate-topology.py`
- **Migration Guide**: `MIGRATION-V1-TO-V2.md`
- **Changelog**: `CHANGELOG.md`

---

**Status**: ✅ All generators functional for topology v2.0
**Last Updated**: 2025-10-10
