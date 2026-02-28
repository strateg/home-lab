# ADR 0050: Generated Directory Restructuring

- Status: Proposed
- Date: 2026-02-28

## Context

Current `generated/` structure is fragmented:

```
generated/
├── terraform/              # Proxmox TF (bridges, VMs, LXC)
├── terraform-mikrotik/     # MikroTik TF (separate root!)
├── ansible/inventory/      # All hosts inventory
├── bootstrap/mikrotik/     # MikroTik bootstrap scripts
└── docs/                   # Documentation
```

Problems:
1. **Inconsistent Terraform layout**: `terraform/` vs `terraform-mikrotik/` at same level
2. **Bootstrap scattered**: `bootstrap/mikrotik/` in generated, `bare-metal/` in repo root
3. **No device-centric view**: Finding all artifacts for a device requires searching everywhere
4. **Terraform runs from control machine**: Current split by technology doesn't reflect execution model

User insight: Terraform and Ansible run from a control machine, not on target devices. They should be grouped by tool with internal structure for targets.

### Constraints

1. **Terraform State**: Each root module needs separate state (mikrotik vs proxmox use different providers/credentials)
2. **Proxmox creates workloads**: Proxmox TF creates VMs/LXC, not just configures the host
3. **Ansible needs unified inventory**: Cross-host operations require single inventory root
4. **Makefile integration**: Deploy scripts reference generated paths

### Artifact Classification by Execution Context

| Artifact | Runs From | Runs Against | State Scope |
|----------|-----------|--------------|-------------|
| Bootstrap scripts | Console/SSH | Single device | None (imperative) |
| MikroTik Terraform | Control machine | MikroTik API | mikrotik.tfstate |
| Proxmox Terraform | Control machine | Proxmox API | proxmox.tfstate |
| Ansible playbooks | Control machine | All hosts via SSH | Inventory |

## Decision

Adopt **Tool-Centric with Subfolders** structure:

```
generated/
├── bootstrap/                      # Pre-IaC device initialization
│   ├── rtr-mikrotik-chateau/       # Device ID as folder
│   │   ├── init-terraform.rsc      # Enable REST API
│   │   └── bootstrap.rsc           # Full bootstrap
│   ├── srv-gamayun/
│   │   ├── answer.toml             # Proxmox auto-install
│   │   └── post-install/
│   │       ├── 01-install-terraform.sh
│   │       └── ...
│   └── srv-orangepi5/
│       └── cloud-init/
│           ├── user-data
│           └── network-config
│
├── terraform/                      # All Terraform configs
│   ├── mikrotik/                   # MikroTik root module
│   │   ├── provider.tf
│   │   ├── versions.tf
│   │   ├── variables.tf
│   │   ├── interfaces.tf
│   │   ├── firewall.tf
│   │   ├── dhcp.tf
│   │   ├── qos.tf
│   │   ├── vpn.tf
│   │   ├── containers.tf
│   │   ├── outputs.tf
│   │   ├── terraform.tfvars.example
│   │   └── .terraform/            # Provider cache
│   │
│   └── proxmox/                    # Proxmox root module
│       ├── provider.tf
│       ├── versions.tf
│       ├── variables.tf
│       ├── bridges.tf
│       ├── vms.tf
│       ├── lxc.tf
│       ├── outputs.tf
│       ├── terraform.tfvars.example
│       └── .terraform/
│
├── ansible/                        # All Ansible configs
│   └── inventory/
│       └── production/
│           ├── hosts.yml
│           ├── group_vars/
│           │   └── all.yml
│           └── host_vars/          # Per-device variables
│               ├── rtr-mikrotik-chateau.yml
│               ├── srv-gamayun.yml
│               ├── srv-orangepi5.yml
│               ├── lxc-postgresql.yml
│               └── lxc-redis.yml
│
└── docs/                           # Generated documentation
    ├── overview.md
    ├── network-diagram.md
    ├── ip-allocation.md
    ├── services.md
    └── devices/                    # Per-device summaries
        ├── rtr-mikrotik-chateau.md
        └── srv-gamayun.md
```

### Key Design Decisions

1. **`terraform/` as unified root**: Subfolders `mikrotik/` and `proxmox/` are separate Terraform root modules with independent states

2. **Subfolder naming by target system** (not OSI layer):
   - `mikrotik/` - clear, everyone knows it's the router
   - `proxmox/` - clear, everyone knows it's the hypervisor
   - Future: `oracle/`, `hetzner/` for VPS providers

3. **`bootstrap/` by device ID**: Each physical device gets its own folder with init scripts

4. **`ansible/` unified**: Single inventory with `host_vars/` for per-device customization

### Comparison: Current vs Proposed

| Aspect | Current | Proposed |
|--------|---------|----------|
| Terraform roots | `terraform/`, `terraform-mikrotik/` | `terraform/mikrotik/`, `terraform/proxmox/` |
| Bootstrap | `bootstrap/mikrotik/` + `bare-metal/` | `bootstrap/{device-id}/` |
| Ansible | `ansible/inventory/` | `ansible/inventory/` (unchanged) |
| Find device files | Search multiple dirs | `bootstrap/{id}/` + `ansible/.../host_vars/{id}.yml` |

### Alternative Options Considered

#### Option A: Pure Device-Centric (User's Initial Proposal)

```
generated/
├── rtr-mikrotik-chateau/
│   ├── routeros/
│   ├── terraform/
│   └── ansible/
├── srv-gamayun/
│   ├── terraform/
│   └── ansible/
```

**Rejected because:**
- Proxmox TF creates LXC containers - they don't belong to srv-gamayun device folder
- Ansible inventory must be unified for cross-host operations
- Multiple Terraform roots per device complicates state management

#### Option B: OSI Layer Names

```
generated/
├── bootstrap/
├── terraform/
│   ├── L2-network/
│   └── L4-platform/
├── ansible/
```

**Rejected because:**
- Adds cognitive load (need to remember layer numbers)
- `mikrotik/` and `proxmox/` are more intuitive than `L2-network/`

#### Option C: Domain-Centric Nesting (Previous ADR Version)

```
generated/
├── bootstrap/
├── network/
│   └── terraform/
├── platform/
│   └── terraform/
├── configuration/
│   └── ansible/
```

**Rejected because:**
- Extra nesting level (`network/terraform/` vs `terraform/mikrotik/`)
- `network/` and `platform/` are abstract; `terraform/mikrotik/` is concrete
- User correctly noted Terraform should be grouped together

### Makefile Integration

```makefile
# Directory definitions
GENERATED_DIR := $(ROOT_DIR)/generated
BOOTSTRAP_DIR := $(GENERATED_DIR)/bootstrap
TF_MIKROTIK_DIR := $(GENERATED_DIR)/terraform/mikrotik
TF_PROXMOX_DIR := $(GENERATED_DIR)/terraform/proxmox
ANSIBLE_INVENTORY := $(GENERATED_DIR)/ansible/inventory/production

# Terraform targets
plan-mikrotik:
	cd $(TF_MIKROTIK_DIR) && terraform plan

plan-proxmox:
	cd $(TF_PROXMOX_DIR) && terraform plan

apply-mikrotik:
	cd $(TF_MIKROTIK_DIR) && terraform apply

apply-proxmox:
	cd $(TF_PROXMOX_DIR) && terraform apply

# Ansible targets
configure:
	ansible-playbook -i $(ANSIBLE_INVENTORY) playbooks/site.yml
```

### Generator Updates Required

| Generator | Current Output | New Output |
|-----------|----------------|------------|
| generate-terraform-proxmox.py | `generated/terraform/` | `generated/terraform/proxmox/` |
| generate-terraform-mikrotik.py | `generated/terraform-mikrotik/` | `generated/terraform/mikrotik/` |
| generate-ansible-inventory.py | `generated/ansible/inventory/` | `generated/ansible/inventory/` (no change) |
| generate-mikrotik-bootstrap.py | `generated/bootstrap/mikrotik/` | `generated/bootstrap/rtr-mikrotik-chateau/` |
| generate-docs.py | `generated/docs/` | `generated/docs/` (no change) |

### Migration Path

1. Update generator output paths
2. Move existing state files:
   ```bash
   mv generated/terraform/ generated/terraform/proxmox/
   mv generated/terraform-mikrotik/ generated/terraform/mikrotik/
   mv generated/bootstrap/mikrotik/ generated/bootstrap/rtr-mikrotik-chateau/
   ```
3. Update Makefile paths
4. Update repo root symlink: `terraform -> generated/terraform/proxmox`
5. Test all `make plan-*` targets
6. Update CLAUDE.md documentation

## Implementation Plan

### Phase 1: Prepare (no breaking changes)

**1.1 Create new directory structure**
```bash
mkdir -p generated/terraform/mikrotik
mkdir -p generated/terraform/proxmox
mkdir -p generated/bootstrap/rtr-mikrotik-chateau
mkdir -p generated/bootstrap/srv-gamayun
mkdir -p generated/bootstrap/srv-orangepi5
```

**1.2 Update generators (output paths)**

| File | Change |
|------|--------|
| `topology-tools/scripts/generators/terraform/mikrotik/cli.py:19` | `default_output = "generated/terraform/mikrotik"` |
| `topology-tools/scripts/generators/terraform/proxmox/cli.py:19` | `default_output = "generated/terraform/proxmox"` |
| `topology-tools/scripts/generators/bootstrap/mikrotik/generator.py:19` | `DEFAULT_OUTPUT_DIR = ... / "bootstrap" / "rtr-mikrotik-chateau"` |

**1.3 Update regenerate-all.py**
- Line 304: `cd generated/terraform/mikrotik`
- Line 305: `cd generated/terraform/proxmox`

**1.4 Update deployers**
- `topology-tools/scripts/deployers/mikrotik_bootstrap.py:220-221`: Update paths

### Phase 2: Migrate existing files

**2.1 Move Terraform files**
```bash
# Backup current state
cp -r generated/terraform generated/terraform-proxmox-backup
cp -r generated/terraform-mikrotik generated/terraform-mikrotik-backup

# Move to new structure
mv generated/terraform/* generated/terraform/proxmox/
mv generated/terraform-mikrotik/* generated/terraform/mikrotik/

# Clean up old directories (after verification)
rmdir generated/terraform-mikrotik
```

**2.2 Move bootstrap files**
```bash
mv generated/bootstrap/mikrotik/* generated/bootstrap/rtr-mikrotik-chateau/
rmdir generated/bootstrap/mikrotik
```

**2.3 Update root symlink**
```bash
rm terraform
ln -s generated/terraform/proxmox terraform
```

### Phase 3: Update Makefile

**File: `deploy/Makefile`**

```makefile
# Old paths
GENERATED_DIR := $(ROOT_DIR)/generated
# Keep this

# New paths (add these)
TF_MIKROTIK_DIR := $(GENERATED_DIR)/terraform/mikrotik
TF_PROXMOX_DIR := $(GENERATED_DIR)/terraform/proxmox
BOOTSTRAP_DIR := $(GENERATED_DIR)/bootstrap

# Update targets
plan-mikrotik:
    @if [ -f $(TF_MIKROTIK_DIR)/terraform.tfvars ]; then \
        cd $(TF_MIKROTIK_DIR) && terraform init -upgrade && terraform plan; \
    ...

plan-proxmox:
    @if [ -f $(TF_PROXMOX_DIR)/terraform.tfvars ]; then \
        cd $(TF_PROXMOX_DIR) && terraform init -upgrade && terraform plan; \
    ...
```

### Phase 4: Update documentation

**4.1 Update CLAUDE.md**
- Directory structure diagram
- Workflow commands (`cd generated/terraform/mikrotik`)
- Common pitfalls section

**4.2 Update deploy/Makefile help text**

**4.3 Update bootstrap/mikrotik/README.md path references**

### Phase 5: Verification

**5.1 Test generation**
```bash
python3 topology-tools/regenerate-all.py
# Verify files appear in new locations
ls -la generated/terraform/mikrotik/
ls -la generated/terraform/proxmox/
ls -la generated/bootstrap/rtr-mikrotik-chateau/
```

**5.2 Test Terraform**
```bash
cd deploy
make init-mikrotik  # Should work with new paths
make init-proxmox
make plan-mikrotik
make plan-proxmox
```

**5.3 Test Ansible**
```bash
ansible-inventory -i generated/ansible/inventory/production --list
```

**5.4 Clean up backups**
```bash
rm -rf generated/terraform-proxmox-backup
rm -rf generated/terraform-mikrotik-backup
```

### Implementation Order

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Update generators (no file moves yet)             │
│   1.1 Create directories                                   │
│   1.2 Update generator default paths                       │
│   1.3 Update regenerate-all.py                             │
│   1.4 Update deployers                                     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Migrate files                                     │
│   2.1 Backup & move terraform files                        │
│   2.2 Move bootstrap files                                 │
│   2.3 Update symlink                                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Update Makefile                                   │
│   Update all path references in deploy/Makefile            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Update documentation                              │
│   4.1 CLAUDE.md                                            │
│   4.2 Makefile help                                        │
│   4.3 README files                                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 5: Verification & cleanup                            │
│   5.1 Test regeneration                                    │
│   5.2 Test Terraform init/plan                             │
│   5.3 Test Ansible inventory                               │
│   5.4 Remove backups                                       │
└─────────────────────────────────────────────────────────────┘
```

### Rollback Plan

If issues arise:
```bash
# Restore from backups
rm -rf generated/terraform/mikrotik generated/terraform/proxmox
mv generated/terraform-proxmox-backup/* generated/terraform/
mv generated/terraform-mikrotik-backup generated/terraform-mikrotik

# Revert symlink
rm terraform
ln -s generated/terraform terraform

# Revert generator code changes via git
git checkout -- topology-tools/scripts/generators/
```

### Files to Modify (Complete List)

| File | Type | Changes |
|------|------|---------|
| `topology-tools/scripts/generators/terraform/mikrotik/cli.py` | Generator | default_output path |
| `topology-tools/scripts/generators/terraform/proxmox/cli.py` | Generator | default_output path |
| `topology-tools/scripts/generators/bootstrap/mikrotik/generator.py` | Generator | DEFAULT_OUTPUT_DIR |
| `topology-tools/regenerate-all.py` | Orchestrator | Print paths |
| `topology-tools/scripts/deployers/mikrotik_bootstrap.py` | Deployer | Print paths |
| `deploy/Makefile` | Build | All TF paths |
| `CLAUDE.md` | Docs | Directory structure, commands |
| `bootstrap/mikrotik/README.md` | Docs | Path references |
| `terraform` (symlink) | Symlink | Target path |

## Consequences

### Positive

1. **Intuitive grouping**: All Terraform together, all Ansible together
2. **Clear target naming**: `mikrotik/`, `proxmox/` immediately recognizable
3. **Device bootstrap consolidated**: All init scripts under `bootstrap/{device-id}/`
4. **Scales to new targets**: Add `terraform/oracle/`, `terraform/hetzner/` for VPS
5. **Minimal Ansible changes**: Inventory structure unchanged
6. **Simple mental model**: "I want Terraform? Go to `terraform/`. Which target? `mikrotik/` or `proxmox/`"

### Negative

1. **Migration effort**: Move files, update generators, update Makefile
2. **Symlink update**: Root `terraform/` symlink needs update
3. **State files move**: Terraform state paths change (or need `terraform init -migrate-state`)

### Neutral

1. Terraform provider cache (`.terraform/`) duplicated per root module (already the case)
2. `terraform.tfvars` needed per root module (already the case)

## References

- ADR 0046: generators-architecture-refactoring
- ADR 0048: topology-v4-architecture-consolidation
- ADR 0049: mikrotik-bootstrap-automation
- Devices: topology/L1-foundation/devices/
