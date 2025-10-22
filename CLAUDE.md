# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is an **Infrastructure-as-Data** home lab project. The topology is defined in **modular YAML files** in `topology/` directory, with `topology.yaml` as the main entry point. This is the **canonical source of truth** that generates:
- Terraform configurations (Proxmox infrastructure)
- Ansible inventory and variables
- Network diagrams
- IP allocation documentation
- Service inventory

**Key Principle**: Edit `topology/*.yaml` modules → regenerate everything → apply with Terraform/Ansible.

### Modular Structure (v2.2)

**Main File**: `topology.yaml` (36 lines) - Entry point with `!include` directives
**Modules**: `topology/*.yaml` (13 files) - Organized by concern

```
topology/
├── metadata.yaml          # Project info, changelog
├── physical.yaml          # Hardware devices, locations
├── logical.yaml           # Networks, bridges, DNS
├── compute.yaml           # VMs and LXC containers
├── storage.yaml           # Storage pools
├── services.yaml          # Service definitions
├── ansible.yaml           # Ansible configuration
├── workflows.yaml         # Automation workflows
├── security.yaml          # Firewall policies
├── backup.yaml            # Backup configuration
├── monitoring.yaml        # Monitoring, alerts
├── documentation.yaml     # Documentation metadata
└── notes.yaml             # Operational notes
```

**Benefits**:
- ✅ Each module < 500 lines (was 2104 in one file)
- ✅ Edit modules independently (fewer Git conflicts)
- ✅ Clear separation of concerns
- ✅ Easy navigation and collaboration
- ✅ All generators automatically merge modules

See `TOPOLOGY-MODULAR.md` for details.

### Technology Stack

- **Hypervisor**: Proxmox VE 9 (Dell XPS L701X: 2 cores, 8GB RAM, SSD 180GB + HDD 500GB)
- **Infrastructure Provisioning**: Terraform (bpg/proxmox provider v0.50.0)
- **Configuration Management**: Ansible v2.14+ with cloud-init
- **Source of Truth**: topology.yaml (YAML format)
- **Version Control**: Git

### Directory Structure

```
home-lab/
├── new_system/                # ⭐ Infrastructure-as-Data (current)
│   ├── topology.yaml          # ⭐ Main entry point (36 lines, with !include)
│   ├── topology/              # ⭐ Modular topology components (13 files)
│   │   ├── metadata.yaml
│   │   ├── physical.yaml
│   │   ├── logical.yaml
│   │   ├── compute.yaml
│   │   ├── storage.yaml
│   │   ├── services.yaml
│   │   ├── ansible.yaml
│   │   ├── workflows.yaml
│   │   ├── security.yaml
│   │   ├── backup.yaml
│   │   ├── monitoring.yaml
│   │   ├── documentation.yaml
│   │   └── notes.yaml
│   ├── scripts/               # Generators (Python)
│   │   ├── topology_loader.py     # YAML loader with !include support
│   │   ├── generate-terraform.py
│   │   ├── generate-ansible-inventory.py
│   │   ├── generate-docs.py
│   │   └── validate-topology.py
│   ├── generated/             # Auto-generated from topology modules
│   │   ├── terraform/         # Terraform configs (DO NOT EDIT MANUALLY)
│   │   │   ├── provider.tf
│   │   │   ├── versions.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   ├── bridges.tf
│   │   │   ├── lxc.tf
│   │   │   └── vms.tf
│   │   ├── ansible/           # Ansible inventory (DO NOT EDIT MANUALLY)
│   │   │   └── inventory/
│   │   └── docs/              # Documentation (DO NOT EDIT MANUALLY)
│   ├── terraform -> generated/terraform/  # Symlink for convenience
│   ├── ansible/               # Ansible playbooks and roles (manual)
│   │   ├── playbooks/         # Service-specific playbooks
│   │   └── roles/             # Reusable roles
│   └── bare-metal/            # Bare-metal installation automation
├── old_system/                # Script-based setup (will be archived)
└── archive/                   # Legacy code archives
    └── legacy-terraform/      # Archived manual Terraform modules
```

## Common Workflows

### 1. Modify Infrastructure

**ALWAYS edit topology modules first, then regenerate:**

```bash
# 1. Edit the relevant module (VMs, networks, services, etc.)
vim new_system/topology/compute.yaml     # Add/modify VMs or LXC
vim new_system/topology/logical.yaml     # Add/modify networks or bridges
vim new_system/topology/services.yaml    # Add/modify services

# 2. Validate topology (automatically merges all modules)
python3 new_system/scripts/validate-topology.py

# 3. Regenerate Terraform
python3 new_system/scripts/generate-terraform.py

# 4. Regenerate Ansible inventory
python3 new_system/scripts/generate-ansible-inventory.py

# 5. Regenerate documentation
python3 new_system/scripts/generate-docs.py

# 6. Plan and apply Terraform changes
cd new_system/terraform  # (symlink to generated/terraform)
terraform plan
terraform apply

# 7. Run Ansible if needed
cd ../ansible
ansible-playbook -i inventory/production/hosts.yml site.yml
```

### 2. Test Infrastructure Changes

**Automated End-to-End Test** (Recommended):
```bash
# Run complete regeneration workflow test
cd new_system
./scripts/test-regeneration.sh

# This will:
# 1. Validate topology.yaml
# 2. Generate Terraform configs
# 3. Validate Terraform syntax
# 4. Generate Ansible inventory
# 5. Validate Ansible syntax
# 6. Check idempotency
# 7. Show git status
```

**Manual Testing**:
```bash
# Terraform
cd new_system/terraform  # (symlink to generated/terraform)
terraform init
terraform validate
terraform plan        # Review changes before applying

# Ansible
cd new_system/ansible
ansible all -i inventory/production/hosts.yml -m ping
ansible-playbook ... --syntax-check
ansible-playbook ... --check  # Dry run
```

### 3. Deploy New LXC Container

```bash
# 1. Add to new_system/topology.yaml under 'lxc:' section
# 2. Regenerate
python3 new_system/scripts/generate-terraform.py
python3 new_system/scripts/generate-ansible-inventory.py

# 3. Apply Terraform (creates LXC)
cd new_system/terraform  # (symlink to generated/terraform)
terraform apply -target='proxmox_virtual_environment_container.new_container'

# 4. Configure with Ansible (installs services)
cd ../ansible
ansible-playbook -i inventory/production/hosts.yml playbooks/new-service.yml
```

### 4. Fresh Proxmox Installation

Complete automation from bare metal to running infrastructure:

```bash
# 1. Create bootable USB
cd new_system/bare-metal
sudo ./create-usb.sh /dev/sdX proxmox-ve_9.0-1.iso

# 2. Boot and auto-install (15 min, automatic)

# 3. SSH and run post-install
ssh root@<proxmox-ip>
cd /root/post-install
./01-install-terraform.sh
./02-install-ansible.sh
./03-configure-storage.sh
./04-configure-network.sh
./05-init-git-repo.sh
reboot

# 4. Copy repository
scp -r ~/home-lab root@10.0.99.1:/root/

# 5. Generate and apply infrastructure
ssh root@10.0.99.1
cd /root/home-lab/new_system
python3 scripts/generate-terraform.py
python3 scripts/generate-ansible-inventory.py
cd terraform
terraform init
terraform apply
cd ../ansible
ansible-playbook -i inventory/production/hosts.yml site.yml
```

## Code Organization Principles

### What Terraform Manages (Proxmox-level)

- Network bridges (vmbr0-vmbr99)
- VMs and LXC containers (creation, resources, NICs)
- VM/LXC network interface attachments
- Storage pools
- Proxmox SDN (if used)

**DO NOT** use Terraform for:
- OS-level network configuration (use Ansible + cloud-init)
- Service installation (use Ansible)
- Application configuration (use Ansible)

### What Ansible Manages (OS-level)

- Network configuration inside VMs/LXC (via cloud-init + Ansible)
- Service installation and configuration
- System hardening and optimization
- User management
- Firewall rules inside OS

**DO NOT** use Ansible for:
- Creating VMs/LXC (use Terraform)
- Proxmox bridge configuration (use Terraform)
- VM resource allocation (use Terraform)

### What topology.yaml Contains

**Infrastructure as Data:**
- Physical interfaces (MAC addresses, names)
- Network bridges and their properties
- IP address allocations for all networks
- VM definitions (resources, NICs, disks)
- LXC definitions (resources, NICs, mounts)
- Storage configuration
- Routing rules
- Firewall policies (high-level)
- Service inventory

**NOT in topology.yaml:**
- Ansible playbook logic
- Terraform provider configuration
- Secrets (use Ansible Vault or Terraform variables)
- Application-specific configs

## Network Architecture

### Physical Layer
- **eth-usb**: USB Ethernet → vmbr0 (WAN to ISP)
- **eth-builtin**: Built-in Ethernet → vmbr1 (LAN to GL.iNet)

### Bridge Layer (Proxmox)
- **vmbr0**: WAN (DHCP from ISP) - OPNsense WAN interface
- **vmbr1**: LAN (192.168.10.254/24) - OPNsense LAN interface
- **vmbr2**: INTERNAL (10.0.30.1/24) - LXC containers
- **vmbr99**: MGMT (10.0.99.1/24) - Management network

### IP Allocation Strategy

```
WAN (vmbr0):           DHCP (ISP provided)
OPNsense LAN (vmbr1):  192.168.10.0/24
  - OPNsense LAN:      192.168.10.1
  - GL.iNet WAN:       192.168.10.2
  - Proxmox (unused):  192.168.10.254

GL.iNet LAN:           192.168.20.0/24 (user devices)
Guest WiFi:            192.168.30.0/24 (isolated)
IoT:                   192.168.40.0/24 (isolated)

LXC Internal (vmbr2):  10.0.30.0/24
  - Proxmox host:      10.0.30.1
  - PostgreSQL:        10.0.30.10
  - Redis:             10.0.30.20
  - Nextcloud:         10.0.30.30
  - Gateway (OPNsense):10.0.30.254

Management (vmbr99):   10.0.99.0/24
  - Proxmox UI:        10.0.99.1:8006
  - OPNsense UI:       10.0.99.10:443

VPN Home (Slate AX):   10.0.200.0/24
VPN Russia (Slate AX): 10.8.2.0/24
```

### Traffic Flow

```
Internet → ISP Router → vmbr0 → OPNsense (firewall)
                                    ↓
                          vmbr1 → GL.iNet Slate AX → WiFi/LAN users
                                    ↓
                        Users access LXC via routing:
                        192.168.20.x → 10.0.30.x (through OPNsense)

LXC Containers → vmbr2 → 10.0.30.254 (OPNsense INTERNAL) → Internet
```

## Storage Strategy

### SSD 180GB (local-lvm)
- **Purpose**: Production VMs and LXC (fast access needed)
- **Contains**: Running VMs/LXC root disks
- **Partitioning**: 50GB root + 2GB swap + 128GB LVM thin pool

### HDD 500GB (local-hdd)
- **Purpose**: Templates, backups, ISOs (infrequent access)
- **Contains**: VM/LXC templates (VMID 900-910), backups, ISO images
- **Path**: /mnt/hdd
- **Backup retention**: 3 last, 7 daily, 4 weekly, 6 monthly, 1 yearly

**Workflow**: Create template on HDD → Clone to SSD for production

## Important ID Ranges

- **VM Templates**: 910-919 (on local-hdd)
- **LXC Templates**: 900-909 (on local-hdd)
- **Production VMs**: 100-199 (on local-lvm)
- **Production LXC**: 200-299 (on local-lvm)

## Secrets Management

**Never commit these to Git:**
- `terraform.tfvars` (contains API tokens)
- `terraform.tfstate` (contains sensitive data)
- `.vault_pass` (Ansible vault password)
- `*.pem`, `*.key` (SSH keys)
- `.env` files

**Proper handling:**
- Terraform secrets: Use `terraform.tfvars` (gitignored)
- Ansible secrets: Use Ansible Vault
- SSH keys: Store in `~/.ssh/`, reference in configs
- API tokens: Environment variables or external secret managers

## Testing Strategy

### Unit Tests (Fast)
```bash
# Terraform validation
cd new_system/terraform
terraform validate
terraform fmt -check

# Ansible syntax check
cd new_system/ansible
ansible-playbook playbooks/site.yml --syntax-check
ansible-lint roles/
```

### Integration Tests (Slower)
```bash
# Terraform plan (no apply)
cd new_system/terraform
terraform plan

# Ansible dry run
cd new_system/ansible
ansible-playbook -i inventory/production/hosts.yml site.yml --check
```

### System Tests (Full deployment)
```bash
# Deploy to staging/dev environment
# Test end-to-end workflows
# See TESTING.md for comprehensive procedures
```

## Regenerating from topology.yaml

### When to Regenerate

**ALWAYS regenerate after editing topology.yaml:**
- Added/removed VM or LXC
- Changed IP address
- Added/removed network bridge
- Modified storage configuration
- Changed resource allocation

**Important**: Generated files are stored in git for transparency and easy rollback. After regeneration, commit changes:
```bash
git add new_system/generated/
git commit -m "Regenerate infrastructure from topology.yaml"
```

### What Gets Regenerated

```bash
python3 new_system/scripts/generate-terraform.py
# Generates:
#   new_system/generated/terraform/provider.tf
#   new_system/generated/terraform/versions.tf
#   new_system/generated/terraform/variables.tf
#   new_system/generated/terraform/outputs.tf
#   new_system/generated/terraform/bridges.tf
#   new_system/generated/terraform/vms.tf
#   new_system/generated/terraform/lxc.tf

python3 new_system/scripts/generate-ansible-inventory.py
# Generates:
#   new_system/generated/ansible/inventory/hosts.yml
#   new_system/generated/ansible/group_vars/all.yml

python3 new_system/scripts/generate-docs.py
# Generates:
#   docs/network-diagram.md (Mermaid)
#   docs/ip-allocation.md (tables)
#   docs/services.md (service inventory)
```

### Manual Files (Do Not Auto-Generate)

**These files are manually maintained:**
- `new_system/topology.yaml` - Source of truth (EDIT THIS!)
- `new_system/ansible/playbooks/*.yml` - Service-specific logic
- `new_system/ansible/roles/*/tasks/*.yml` - Role implementations
- `new_system/bare-metal/post-install/*.sh` - Bash scripts
- `new_system/scripts/templates/*.j2` - Jinja2 templates for generators

**NEVER edit files in `new_system/generated/`** - they will be overwritten!

## Cloud-Init Integration

LXC containers use cloud-init for initial OS configuration:

```yaml
# In topology.yaml
lxc:
  myservice:
    cloudinit:
      enabled: true
      user: "serviceuser"
      ssh_keys:
        - "ssh-ed25519 ..."
```

Terraform generates cloud-init snippets → Proxmox injects on first boot → Ansible configures services.

## Common Pitfalls

### ❌ DON'T: Edit generated Terraform files manually
```bash
# Wrong:
vim new_system/generated/terraform/bridges.tf  # This will be overwritten!
vim new_system/terraform/lxc.tf                # Same as above (symlink)
```

### ✅ DO: Edit topology.yaml and regenerate
```bash
# Correct:
vim new_system/topology.yaml
python3 new_system/scripts/generate-terraform.py
# All files in generated/ will be updated automatically
```

### ❌ DON'T: Use Terraform for OS-level networking
```hcl
# Wrong in Terraform:
provisioner "remote-exec" {
  inline = ["ip addr add ..."]  # Use Ansible instead!
}
```

### ✅ DO: Use Ansible for OS-level configuration
```yaml
# Correct in Ansible:
- name: Configure network interface
  ansible.builtin.template:
    src: interfaces.j2
    dest: /etc/network/interfaces
```

### ❌ DON'T: Hardcode IPs in Ansible playbooks
```yaml
# Wrong:
postgresql_host: "10.0.30.10"  # Hardcoded!
```

### ✅ DO: Reference topology-generated variables
```yaml
# Correct:
postgresql_host: "{{ hostvars['postgresql-db'].ansible_host }}"
```

## Migration from Old Setup

### From old_system (Script-Based)
If migrating from the old script-based setup (in `README-old-network-setup.md`):
1. Read `MIGRATION.md` for complete guide
2. Old scripts are in `old_system/proxmox/scripts/` (legacy, reference only)
3. Gradually migrate components to `new_system/topology.yaml`
4. Test each component before decommissioning old scripts

### From Legacy Terraform Modules
Legacy manual Terraform modules have been archived to `archive/legacy-terraform/`:
- Network modules (bridges configuration)
- Storage modules (storage pools configuration)
- Provider configurations

These are kept for reference only. All infrastructure is now auto-generated from topology.yaml.

## Performance Considerations

**Hardware Constraints**: Dell XPS L701X has only 8GB RAM (non-upgradable)

**RAM Allocation Strategy** (from topology.yaml):
- Proxmox OS: ~1.5 GB
- OPNsense VM: 2 GB (minimum for stability)
- LXC containers: 1-2 GB each
- **Available for LXC**: ~4 GB (after OPNsense)

**Offload to GL.iNet Slate AX** (512MB RAM):
- AdGuard Home (~100 MB)
- WireGuard/AmneziaWG servers (~40 MB)
- **Frees ~140 MB on Proxmox**

## Monitoring and Verification

```bash
# Check Terraform state matches topology
cd new_system/terraform
terraform plan  # Should show "No changes"

# Check Ansible idempotency
cd new_system/ansible
ansible-playbook -i inventory/production/hosts.yml site.yml --check
# Second run should show 0 changes

# Verify network bridges
ssh root@10.0.99.1 "brctl show"

# Verify LXC connectivity
ssh root@10.0.99.1 "pct exec 200 -- ping -c 3 8.8.8.8"

# Check storage usage
ssh root@10.0.99.1 "pvesm status"
```

## Documentation

- **README.md**: Project overview and quick start
- **MIGRATION.md**: Migration guide from script-based setup
- **TESTING.md**: Comprehensive testing procedures
- **new_system/topology.yaml**: Infrastructure definition (source of truth)
- **new_system/bare-metal/README.md**: Bare-metal installation guide
- **new_system/ansible/roles/*/README.md**: Role-specific documentation

## Generator Scripts (To Be Implemented)

These Python scripts transform `topology.yaml` into usable configs:

```bash
# Validate topology schema and consistency
python3 new_system/scripts/validate-topology.py

# Generate Terraform from topology
python3 new_system/scripts/generate-terraform.py

# Generate Ansible inventory from topology
python3 new_system/scripts/generate-ansible-inventory.py

# Generate documentation from topology
python3 new_system/scripts/generate-docs.py

# All-in-one regeneration
python3 new_system/scripts/regenerate-all.py
```

**TODO**: Implement these generators (see new_system/scripts/README.md for specifications)

## Working with Claude Code

When Claude Code helps with this repository:

1. **Always check topology.yaml first** - It's the source of truth
2. **Regenerate after topology changes** - Run generator scripts
3. **Use Terraform for Proxmox objects** - Bridges, VMs, LXC NICs
4. **Use Ansible for OS configuration** - Services, networking inside VMs/LXC
5. **Test changes incrementally** - Validate → Plan → Apply
6. **Document in topology.yaml** - Keep it updated

**Ask Claude Code to:**
- "Add a new LXC container for service X to topology.yaml"
- "Regenerate Terraform from topology.yaml"
- "Generate network diagram from topology.yaml"
- "Validate topology.yaml schema"
- "What IP should I use for service X?"

**Don't ask Claude Code to:**
- Edit generated Terraform files directly
- Hardcode IPs outside topology.yaml
- Mix Terraform and Ansible responsibilities
