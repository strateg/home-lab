# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is an **Infrastructure-as-Data** home lab project using **OSI-like layer architecture (v4.0)**. The topology is defined in **8 layer files** (L0-L7) in `topology/` directory, with `topology.yaml` as the main entry point. This is the **canonical source of truth** that generates:
- Terraform configurations (Proxmox infrastructure)
- Terraform configurations (MikroTik RouterOS)
- Ansible inventory and assembled runtime inventory
- Network diagrams
- IP allocation documentation
- Service inventory
- Deploy-ready `dist/` packages

**Key Principle**: Edit `topology/L*.yaml` layers → regenerate everything → apply with Terraform/Ansible.

### OSI-Layer Architecture (v4.0)

**Main File**: `topology.yaml` - Entry point with `!include` directives
**Layers**: `topology/L0-L7.yaml` (8 files) - Organized by OSI-like principles

```
topology/
├── L0-meta.yaml           # Meta: version, defaults, security policies
├── L1-foundation.yaml     # Foundation: physical devices, interfaces, physical power inventory
├── L2-network.yaml        # Network: networks, bridges, firewall, QoS, IPv6
├── L3-data.yaml           # Data: storage pools, data assets
├── L4-platform.yaml       # Platform: VMs, LXC containers, templates
├── L5-application.yaml    # Application: services, certificates, DNS
├── L6-observability.yaml  # Observability: monitoring, alerts, dashboards
└── L7-operations.yaml     # Operations: workflows, power resilience policies, ansible config, backups
```

**Layer Dependency Rules**:
- Higher layers (L7) can reference lower layers (L0-L6)
- Lower layers CANNOT reference higher layers
- Example: L5 (services) can reference L4 (LXC) but NOT vice versa

**Benefits**:
- Clear separation of concerns following OSI model principles
- Explicit dependency direction (top-down only)
- Each layer < 700 lines
- Easier to understand infrastructure hierarchy
- All generators automatically merge layers

### Technology Stack

- **Hypervisor**: Proxmox VE 9 (Dell XPS L701X: 2 cores, 8GB RAM, SSD 180GB + HDD 500GB)
- **Router**: MikroTik Chateau LTE7 ax (ARM64, 1GB RAM, RouterOS 7.x)
- **SBC**: Orange Pi 5 (RK3588S, 16GB RAM, NVMe 256GB)
- **Infrastructure Provisioning**:
  - Terraform (bpg/proxmox provider v0.85+)
  - Terraform (terraform-routeros/routeros provider)
- **Configuration Management**: Ansible v2.14+ with cloud-init
- **Source of Truth**: topology.yaml (YAML format, v4.0)
- **Version Control**: Git

### Directory Structure

```
home-lab/
├── topology.yaml              # Main entry point with !include
├── topology/                  # OSI-like layer files (8 files)
│   ├── L0-meta.yaml           # Meta layer
│   ├── L1-foundation.yaml     # Physical devices
│   ├── L2-network.yaml        # Networks, bridges, firewall
│   ├── L3-data.yaml           # Storage
│   ├── L4-platform.yaml       # VMs, LXC
│   ├── L5-application.yaml    # Services
│   ├── L6-observability.yaml  # Monitoring
│   └── L7-operations.yaml     # Workflows, backup
├── topology-tools/            # Topology-driven generators/validator
│   ├── topology_loader.py
│   ├── generate-terraform-proxmox.py
│   ├── generate-terraform-mikrotik.py
│   ├── generate-ansible-inventory.py
│   ├── assemble-ansible-runtime.py
│   ├── assemble-deploy.py
│   ├── validate-dist.py
│   ├── generate-docs.py
│   ├── validate-topology.py
│   ├── regenerate-all.py
│   ├── schemas/               # JSON Schema + validator policy
│   └── templates/             # Jinja2 templates for generators
├── manual-scripts/            # Manual setup/config scripts
│   ├── openwrt/
│   ├── opi5/
│   └── archive/
├── generated/                 # Auto-generated (DO NOT EDIT)
│   ├── bootstrap/             # Device init scripts
│   │   ├── rtr-mikrotik-chateau/  # MikroTik bootstrap
│   │   ├── srv-gamayun/           # Proxmox bootstrap
│   │   └── srv-orangepi5/         # OPi5 cloud-init
│   ├── terraform/
│   │   ├── mikrotik/          # MikroTik Terraform
│   │   └── proxmox/           # Proxmox Terraform
│   ├── ansible/inventory/     # Raw generated inventory
│   ├── ansible/runtime/       # Assembled runtime inventory (ADR 0051)
│   └── docs/                  # Documentation
├── dist/                      # Assembled deploy packages (ADR 0052)
│   ├── control/ansible/
│   ├── control/terraform/
│   └── manifests/
├── terraform -> generated/terraform/proxmox  # Symlink
├── ansible/                   # Playbooks and roles (manual)
│   ├── playbooks/
│   └── roles/
├── manual bare-metal source assets           # Source assets for generated Proxmox bootstrap package
├── generated/bootstrap/       # Canonical bootstrap packages
├── Migrated_and_archived/     # Archived legacy bootstrap/manual flows
├── deploy/                    # Deployment orchestration
│   ├── Makefile
│   └── phases/
├── docs/                      # Manual documentation
├── configs/                   # Device configs (GL.iNet, VPN)
└── Migrated_and_archived/     # Legacy code (archived)
```

## Common Workflows

### 1. Modify Infrastructure

**ALWAYS edit layer files first, then regenerate:**

```bash
# 1. Edit the relevant layer
vim topology/L4-platform.yaml      # Add/modify VMs or LXC
vim topology/L2-network.yaml       # Add/modify networks or bridges
vim topology/L5-application.yaml   # Add/modify services

# 2. Validate and regenerate all
python3 topology-tools/regenerate-all.py

# Or step by step:
python3 topology-tools/validate-topology.py
python3 topology-tools/generate-terraform-proxmox.py
python3 topology-tools/generate-terraform-mikrotik.py
python3 topology-tools/generate-ansible-inventory.py
python3 topology-tools/assemble-ansible-runtime.py
python3 topology-tools/generate-docs.py

# Optional: assemble and validate deploy packages
python3 topology-tools/assemble-deploy.py
python3 topology-tools/validate-dist.py

# 3. Plan and apply Terraform changes
cd generated/terraform/proxmox
terraform plan && terraform apply

cd ../mikrotik
terraform plan && terraform apply

# 4. Run Ansible if needed
cd ../../../ansible
ansible-playbook playbooks/site.yml
```

### 2. Using Makefile (Recommended)

```bash
cd deploy

# Validate topology
make validate

# Generate all configs
make generate

# Assemble deploy packages
make assemble-dist

# Validate assembled dist
make validate-dist

# Full deployment
make deploy-all

# Or individual phases
make plan-mikrotik
make plan-proxmox
make apply-mikrotik
make apply-proxmox
make configure  # Ansible

# Dist-first execution (ADR 0053, opt-in)
make plan-dist
make apply-mikrotik-dist
make apply-proxmox-dist
make configure-dist
make deploy-all-dist
```

### 3. Deploy New LXC Container

```bash
# 1. Add to topology/L4-platform.yaml under 'lxc:' section
vim topology/L4-platform.yaml

# 2. Add service in L5 if needed
vim topology/L5-application.yaml

# 3. Regenerate
python3 topology-tools/regenerate-all.py

# 4. Apply Terraform (creates LXC)
cd generated/terraform/proxmox
terraform apply -target='proxmox_virtual_environment_container.new_container'

# 5. Configure with Ansible
cd ../../ansible
ansible-playbook playbooks/new-service.yml
```

### 4. Fresh Proxmox Installation

```bash
# 1. Generate the canonical bootstrap package
python3 topology-tools/generate-proxmox-bootstrap.py
cd generated/bootstrap/srv-gamayun
cp answer.toml.example answer.toml
sudo ./create-uefi-autoinstall-proxmox-usb.sh /path/to/proxmox-ve.iso answer.toml /dev/sdX

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

# 4. Copy repository and deploy
scp -r ~/home-lab root@10.0.99.1:/root/
ssh root@10.0.99.1
cd /root/home-lab
python3 topology-tools/regenerate-all.py
cd deploy && make deploy-all
```

## Code Organization Principles

### What Terraform Manages

**Proxmox (generated/terraform/proxmox/):**
- Network bridges (vmbr0-vmbr99)
- VMs and LXC containers
- Storage pools

**MikroTik (generated/terraform/mikrotik/):**
- Bridge and VLAN interfaces
- IP addresses and DHCP
- Firewall rules and NAT
- QoS (queues)
- WireGuard VPN
- Containers (AdGuard, Tailscale)

### What Ansible Manages

- OS-level configuration inside VMs/LXC
- Service installation (PostgreSQL, Redis, etc.)
- System hardening
- User management

### Layer Contents

| Layer | File | Contains |
|-------|------|----------|
| L0 | L0-meta.yaml | version, defaults, security_policy |
| L1 | L1-foundation.yaml | devices, interfaces, data links (data_links), power links (power_links), physical power devices |
| L2 | L2-network.yaml | networks, bridges, firewall, qos, ipv6 |
| L3 | L3-data.yaml | storage_pools, data_assets |
| L4 | L4-platform.yaml | vms, lxc, templates |
| L5 | L5-application.yaml | services, certificates, dns_records |
| L6 | L6-observability.yaml | healthchecks, alerts, dashboards |
| L7 | L7-operations.yaml | workflows, power_resilience, ansible_config, backup |

### Naming Conventions

Hierarchical naming ensures collision-free IDs at scale:

| Entity | Pattern | Example |
|--------|---------|---------|
| Device | `{type}-{location}-{id}` | `rtr-home-mikrotik` |
| Service | `svc-{domain}.{name}` | `svc-web.nextcloud` |
| Alert | `alert-{domain}.{service}-{type}` | `alert-web.nextcloud-down` |
| Dashboard | `dash-{layer}-{domain}` | `dash-app-web` |

Defined in: `L0-meta/_index.yaml` under `naming:` key.

## ADR Policy (Mandatory)

Architecture decisions must be documented in `adr/`.

- One architectural decision -> one ADR file.
- Naming: `adr/NNNN-short-kebab-title.md`.
- Use `adr/0000-template.md` as a starting point.
- No architecture change is considered complete without an ADR entry.
- For superseding decisions, create a new ADR and mark prior one as superseded.

## Network Architecture

### Physical Layer
- **MikroTik Chateau**: Main router with LTE, WiFi 6, 4x GbE
- **Dell XPS L701X**: Proxmox hypervisor
- **Orange Pi 5**: Docker host for media services

### Network Topology
```
Internet (LTE/WAN)
       │
       ▼
┌─────────────────────┐
│  MikroTik Chateau   │ ← Router, Firewall, VPN
│  192.168.88.1       │
└─────────────────────┘
       │
       ├── VLAN 10: Servers (10.0.10.0/24)
       │   ├── Proxmox: 10.0.10.1
       │   ├── Orange Pi 5: 10.0.10.5
       │   └── LXC containers
       │
       ├── VLAN 20: Users (192.168.20.0/24)
       ├── VLAN 30: IoT (192.168.30.0/24)
       ├── VLAN 40: Guest (192.168.40.0/24)
       └── VLAN 99: Management (10.0.99.0/24)
```

## Storage Strategy

### SSD 180GB (local-lvm)
- Production VMs and LXC root disks
- Fast access workloads

### HDD 500GB (local-hdd)
- Templates (VMID 900-919)
- Backups
- ISO images

## Secrets Management

**Never commit:**
- `terraform.tfvars`
- `terraform.tfstate`
- `.vault_pass`
- `*.pem`, `*.key`

**Use:**
- Terraform: `terraform.tfvars` (gitignored)
- Ansible: Ansible Vault
- API tokens: Environment variables

## Regenerating from Topology

### When to Regenerate

Always regenerate after editing any `topology/L*.yaml` file:
```bash
python3 topology-tools/regenerate-all.py
```

### What Gets Generated

```
generated/
├── bootstrap/                     # Device init scripts (ADR 0050)
│   ├── rtr-mikrotik-chateau/      # MikroTik bootstrap
│   │   ├── init-terraform.rsc
│   │   └── terraform.tfvars
│   ├── srv-gamayun/               # Proxmox bootstrap package
│   └── srv-orangepi5/             # OPi5 cloud-init
├── terraform/
│   ├── mikrotik/                  # MikroTik RouterOS
│   │   ├── provider.tf
│   │   ├── interfaces.tf
│   │   ├── firewall.tf
│   │   └── ...
│   └── proxmox/                   # Proxmox infrastructure
│       ├── provider.tf
│       ├── bridges.tf
│       ├── lxc.tf
│       └── ...
├── ansible/inventory/             # Ansible
│   └── production/
├── ansible/runtime/               # Assembled runtime inventory
│   └── production/
│       ├── hosts.yml
│       ├── group_vars/
│       └── host_vars/
└── docs/                          # Documentation
    ├── overview.md
    ├── network-diagram.md
    └── ...
```

## Common Pitfalls

### DON'T: Edit generated files
```bash
# Wrong:
vim generated/terraform/proxmox/bridges.tf  # Will be overwritten!
```

### DO: Edit layer files and regenerate
```bash
# Correct:
vim topology/L2-network.yaml
python3 topology-tools/regenerate-all.py
```

### DON'T: Reference higher layers from lower
```yaml
# Wrong in L4-platform.yaml:
lxc:
  - id: lxc-db
    service_ref: svc-postgresql  # L4 cannot reference L5!
```

### DO: Reference lower layers only
```yaml
# Correct in L5-application.yaml:
services:
  - id: svc-postgresql
    lxc_ref: lxc-db              # L5 can reference L4
```

## Working with Claude Code

When Claude Code helps with this repository:

1. **Always check topology layers first** - They are the source of truth
2. **Regenerate after changes** - Run `regenerate-all.py`
3. **Respect layer boundaries** - Don't create upward references
4. **Record architecture decisions in ADR** - add/update `adr/NNNN-*.md`
5. **Use Makefile** - `cd deploy && make validate generate`

**Ask Claude Code to:**
- "Add a new LXC container to L4-platform.yaml"
- "Add a service definition to L5-application.yaml"
- "Regenerate all configs"
- "Validate topology"

**Don't ask Claude Code to:**
- Edit files in `generated/` directly
- Create references from lower to higher layers
- Hardcode IPs outside topology

### Dist Assembly

ADR 0052 adds explicit deploy package assembly:

```bash
python3 topology-tools/assemble-deploy.py
python3 topology-tools/validate-dist.py
```

`dist/` is an assembled output layer, not a source-of-truth. Current package scope:
- `dist/control/ansible`
- `dist/control/terraform/mikrotik`
- `dist/control/terraform/proxmox`
- `dist/bootstrap/rtr-mikrotik-chateau`
- `dist/bootstrap/srv-gamayun`
- `dist/bootstrap/srv-orangepi5`
- `dist/manifests/*.json`
