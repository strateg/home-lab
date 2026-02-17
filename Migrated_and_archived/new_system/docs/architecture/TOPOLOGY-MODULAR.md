# Topology Modular Structure v2.2

## Overview

topology.yaml has been split into a modular structure for better maintainability. The main file is now just **36 lines** (was 2104 lines).

## Structure

```
topology.yaml                     # Main file (36 lines) - entry point with !include directives
topology/                         # Modular components (13 files, 88KB total)
├── metadata.yaml                 # 27 lines  - Project metadata, changelog
├── physical.yaml                 # 118 lines - Hardware, devices, locations
├── logical.yaml                  # 497 lines - Networks, bridges, DNS, firewall templates
├── compute.yaml                  # 269 lines - VMs and LXC containers
├── storage.yaml                  # 55 lines  - Storage pools configuration
├── services.yaml                 # 109 lines - Service definitions
├── ansible.yaml                  # 176 lines - Ansible playbook mappings
├── workflows.yaml                # 67 lines  - Automation workflows
├── security.yaml                 # 97 lines  - Security policies, firewall rules
├── backup.yaml                   # 103 lines - Backup configuration
├── monitoring.yaml               # 305 lines - Monitoring, alerts, health checks
├── documentation.yaml            # 33 lines  - Documentation metadata
└── notes.yaml                    # 11 lines  - Operational notes
```

## Benefits

✅ **Improved Readability**: Each file < 500 lines (vs 2104 in one file)
✅ **Better Navigation**: Find sections by filename
✅ **Reduced Git Conflicts**: Edit different modules independently
✅ **Clearer Separation**: Physical vs logical vs compute
✅ **Easier Collaboration**: Multiple people can work on different modules
✅ **Scalable**: Can further split large modules (e.g., compute/ → vms.yaml + lxc.yaml)

## Usage

### Viewing Infrastructure

```bash
# Main entry point shows structure
cat topology.yaml

# View specific components
cat topology/compute.yaml       # VMs and LXC
cat topology/logical.yaml       # Networks and bridges
cat topology/storage.yaml       # Storage configuration
```

### Editing Infrastructure

```bash
# Edit the module you need
vim topology/compute.yaml       # Add new VM or LXC
vim topology/logical.yaml       # Add network or bridge
vim topology/services.yaml      # Add new service

# Regenerate everything
python3 scripts/regenerate-all.py
```

### How It Works

The main `topology.yaml` uses `!include` directives:

```yaml
version: "2.2.0"
metadata: !include topology/metadata.yaml
physical_topology: !include topology/physical.yaml
logical_topology: !include topology/logical.yaml
# ... etc
```

All generators (validate, terraform, ansible, docs) automatically merge included files using `scripts/topology_loader.py`.

## Backward Compatibility

- **Backup**: Original file saved as `topology.yaml.backup` (2104 lines)
- **Generators**: All scripts updated to use `topology_loader.py` with !include support
- **Validation**: JSON Schema validation works with merged result
- **Git**: Generated files still committed (transparency)

## Migration

The split was done automatically using `scripts/split-topology.py` which:
- Preserves all comments and formatting
- Adds headers to each module
- Maintains proper YAML indentation
- Extracts sections by top-level keys

## Version

- **Previous**: v2.1.0 - Monolithic topology.yaml (2104 lines)
- **Current**: v2.2.0 - Modular structure (36 lines main + 13 modules)

## Files Changed

### New Files
- `topology.yaml` - Replaced with modular version (36 lines)
- `topology/*.yaml` - 13 module files
- `scripts/topology_loader.py` - YAML loader with !include support
- `scripts/split-topology.py` - Splitter script (for reference)

### Updated Files
- `scripts/validate-topology.py` - Uses topology_loader
- `scripts/generate-terraform.py` - Uses topology_loader
- `scripts/generate-ansible-inventory.py` - Uses topology_loader
- `scripts/generate-docs.py` - Uses topology_loader

### Backup
- `topology.yaml.backup` - Original monolithic file (2104 lines)

## Testing

All generators tested and working:

```bash
✅ python3 scripts/validate-topology.py          # Schema validation
✅ python3 scripts/generate-terraform.py         # Terraform generation
✅ python3 scripts/generate-ansible-inventory.py # Ansible inventory
✅ python3 scripts/generate-docs.py              # Documentation
✅ python3 scripts/regenerate-all.py             # Full regeneration
```

## Further Improvements

Potential future splits (if modules grow too large):

```
compute/
├── vms.yaml          # Virtual machines
├── lxc.yaml          # LXC containers
└── templates.yaml    # VM/LXC templates

logical/
├── networks.yaml     # Network definitions
├── bridges.yaml      # Bridge configuration
└── dns.yaml          # DNS records and zones
```

But currently all modules are manageable sizes (< 500 lines each).
