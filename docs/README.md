# Home Lab Documentation

Welcome to the home lab infrastructure documentation! This directory contains all documentation organized by topic.

---

## Documentation Structure

```
docs/
├── README.md                    # You are here
├── CHANGELOG.md                 # Project changelog (v3.0.0)
├── CHANGELOG-GENERATED-DIR.md   # Generated directory changelog
├── guides/                      # Practical how-to guides
│   ├── DEPLOYMENT-STRATEGY.md   # Full deployment workflow (NEW)
│   ├── MIKROTIK-TERRAFORM.md    # MikroTik Terraform guide (NEW)
│   ├── BRIDGES.md               # Network bridges setup
│   ├── GENERATED-QUICK-GUIDE.md # Generated directory quick reference
│   ├── PROXMOX-USB-AUTOINSTALL.md # Proxmox auto-install USB
│   ├── ANSIBLE-VAULT-GUIDE.md   # Secrets management
│   └── RAM-OPTIMIZATION.md      # RAM optimization (8GB constraint)
├── architecture/                # Architecture and design decisions
│   ├── TOPOLOGY-MODULAR.md      # Modular topology structure (v3.0)
│   └── MIGRATION-V1-TO-V2.md    # Migration guide (historical)
└── archive/                     # Historical documents
```

---

## Quick Start

### Full Deployment from Scratch

```bash
# 1. Bootstrap MikroTik (one-time, manual via WinBox)
#    Import bootstrap/mikrotik/bootstrap.rsc

# 2. Configure credentials
cd generated/terraform-mikrotik
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with passwords and keys

# 3. Deploy everything
cd deploy
make deploy-all
```

See [DEPLOYMENT-STRATEGY.md](guides/DEPLOYMENT-STRATEGY.md) for the complete guide.

### For New Users

1. **Understand the architecture**: Read [TOPOLOGY-MODULAR.md](architecture/TOPOLOGY-MODULAR.md)
2. **Learn deployment strategy**: Read [DEPLOYMENT-STRATEGY.md](guides/DEPLOYMENT-STRATEGY.md)
3. **MikroTik setup**: Follow [MIKROTIK-TERRAFORM.md](guides/MIKROTIK-TERRAFORM.md)
4. **Create Proxmox USB**: Follow [PROXMOX-USB-AUTOINSTALL.md](guides/PROXMOX-USB-AUTOINSTALL.md)
5. **Manage secrets**: Read [ANSIBLE-VAULT-GUIDE.md](guides/ANSIBLE-VAULT-GUIDE.md)

---

## Infrastructure Overview

```
                    ┌─────────────────┐
                    │    Internet     │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │  MikroTik Chateau LTE7 ax   │
              │  ├─ Firewall + NAT          │
              │  ├─ DHCP + DNS (AdGuard)    │
              │  ├─ VLANs (30,40,50,99)     │
              │  ├─ WireGuard VPN           │
              │  ├─ Tailscale (container)   │
              │  └─ QoS Traffic Shaping     │
              └──────────────┬──────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
   ┌─────┴─────┐      ┌─────┴─────┐      ┌─────┴─────┐
   │ Orange Pi │      │  Proxmox  │      │   Users   │
   │    5      │      │  (Dell)   │      │  Devices  │
   ├───────────┤      ├───────────┤      └───────────┘
   │ Nextcloud │      │ PostgreSQL│
   │ Jellyfin  │      │ Redis     │
   │ Grafana   │      └───────────┘
   │ Prometheus│
   └───────────┘
```

---

## Documentation by Topic

### Deployment & Operations

| Document | Description | Status |
|----------|-------------|--------|
| [DEPLOYMENT-STRATEGY.md](guides/DEPLOYMENT-STRATEGY.md) | Full deployment workflow with phases | NEW |
| [MIKROTIK-TERRAFORM.md](guides/MIKROTIK-TERRAFORM.md) | MikroTik RouterOS automation | NEW |
| [PROXMOX-USB-AUTOINSTALL.md](guides/PROXMOX-USB-AUTOINSTALL.md) | Proxmox auto-install USB creation | STABLE |
| [BRIDGES.md](guides/BRIDGES.md) | Network bridges (Terraform + manual) | STABLE |

### Infrastructure Setup

| Document | Description | Status |
|----------|-------------|--------|
| [GENERATED-QUICK-GUIDE.md](guides/GENERATED-QUICK-GUIDE.md) | Generated directory workflow | STABLE |
| [RAM-OPTIMIZATION.md](guides/RAM-OPTIMIZATION.md) | RAM allocation for 8GB constraint | STABLE |
| [ANSIBLE-VAULT-GUIDE.md](guides/ANSIBLE-VAULT-GUIDE.md) | Secrets management | STABLE |

### Architecture

| Document | Description | Status |
|----------|-------------|--------|
| [TOPOLOGY-MODULAR.md](architecture/TOPOLOGY-MODULAR.md) | Modular topology structure | UPDATED |
| [MIGRATION-V1-TO-V2.md](architecture/MIGRATION-V1-TO-V2.md) | Migration guide v1→v2 | ARCHIVED |

---

## Deployment Phases

The infrastructure is deployed in 4 phases:

| Phase | Target | Tool | Description |
|-------|--------|------|-------------|
| 0 | MikroTik | Manual | Bootstrap REST API (one-time) |
| 1 | MikroTik | Terraform | Network, firewall, VPN, containers |
| 2 | Proxmox | Terraform | LXC containers (PostgreSQL, Redis) |
| 3 | All | Ansible | Service configuration |
| 4 | All | Script | Verification checks |

```bash
# Full deployment command
cd deploy && make deploy-all

# Or step by step
make bootstrap-info   # Show bootstrap instructions
make plan             # Preview all changes
make apply-mikrotik   # Phase 1: Network
make apply-proxmox    # Phase 2: Compute
make configure        # Phase 3: Services
make test             # Phase 4: Verify
```

---

## Generated Resources

### MikroTik Terraform (terraform-routeros)

| Resource Type | Count | Description |
|---------------|-------|-------------|
| Bridge | 1 | bridge-lan with VLAN filtering |
| Bridge Ports | 4 | LAN1-4 (ether2-ether5) |
| VLANs | 4 | 30 (servers), 40 (IoT), 50 (guest), 99 (mgmt) |
| IP Addresses | 9 | Per-network gateway addresses |
| DHCP Servers | 3 | LAN, Guest, IoT |
| DNS Records | 20 | Static records for services |
| Firewall Rules | 15+ | Filter + NAT + address lists |
| QoS Queues | 7 | Priority-based traffic shaping |
| WireGuard | 1 | VPN with dynamic peers |
| Containers | 2 | AdGuard Home, Tailscale |

### Proxmox Terraform (bpg/proxmox)

| Resource Type | Count | Description |
|---------------|-------|-------------|
| Bridges | 3 | vmbr0 (WAN), vmbr2 (servers), vmbr99 (mgmt) |
| LXC Containers | 2 | PostgreSQL, Redis |

---

## Key Concepts

### Infrastructure-as-Data

Everything is defined in `topology.yaml` (single source of truth):

```
topology.yaml (36 lines)
    ├── !include topology/physical.yaml
    ├── !include topology/logical.yaml
    ├── !include topology/compute.yaml
    ├── !include topology/services.yaml
    └── ... (13 modules total)
           ↓
    scripts/generate-*.py
           ↓
    generated/
    ├── terraform/           # Proxmox
    ├── terraform-mikrotik/  # MikroTik
    ├── ansible/inventory/
    └── docs/
```

### Generated vs. Manual Files

**Generated** (DO NOT EDIT):
- `generated/terraform/*.tf`
- `generated/terraform-mikrotik/*.tf`
- `generated/ansible/inventory/`
- `generated/docs/`

**Manual** (EDIT THESE):
- `topology.yaml` and `topology/*.yaml`
- `ansible/playbooks/*.yml`
- `ansible/roles/*/tasks/*.yml`
- `deploy/phases/*.sh`

---

## Recent Updates (2026-02)

### NEW: MikroTik Terraform Automation

- **terraform-routeros provider** v1.99.0 integration
- Full network configuration from topology.yaml
- WireGuard VPN with dynamic peers
- Container support (AdGuard, Tailscale)
- QoS traffic shaping

### NEW: Deployment Orchestration

- **deploy/Makefile** - Convenient deployment commands
- **Phase scripts** - Modular deployment (01-network, 02-compute, etc.)
- **Bootstrap scripts** - MikroTik REST API setup
- **Verification** - Automated health checks

### NEW: Topology v3.0

- Added MikroTik-specific configuration
- Enhanced firewall policies
- QoS queue definitions
- Container service definitions

---

## File Structure

```
new_system/
├── topology.yaml              # Main entry point
├── topology/                  # 13 modular YAML files
├── scripts/                   # Python generators
│   ├── generate-terraform.py          # Proxmox
│   ├── generate-terraform-mikrotik.py # MikroTik (NEW)
│   ├── generate-ansible-inventory.py
│   └── generate-docs.py
├── generated/                 # Auto-generated configs
│   ├── terraform/             # Proxmox Terraform
│   ├── terraform-mikrotik/    # MikroTik Terraform (NEW)
│   ├── ansible/inventory/
│   └── docs/
├── deploy/                    # Deployment orchestration (NEW)
│   ├── Makefile
│   └── phases/
├── bootstrap/                 # One-time setup (NEW)
│   └── mikrotik/
├── ansible/                   # Playbooks and roles
└── docs/                      # Documentation
```

---

## External References

### Terraform Providers

- [terraform-routeros](https://registry.terraform.io/providers/terraform-routeros/routeros/latest/docs) - MikroTik RouterOS
- [bpg/proxmox](https://registry.terraform.io/providers/bpg/proxmox/latest/docs) - Proxmox VE

### MikroTik

- [RouterOS Documentation](https://help.mikrotik.com/docs/display/ROS/RouterOS)
- [RouterOS Scripting](https://help.mikrotik.com/docs/display/ROS/Scripting)
- [Container Package](https://help.mikrotik.com/docs/display/ROS/Container)

### Proxmox & Ansible

- [Proxmox VE Documentation](https://pve.proxmox.com/wiki/Main_Page)
- [Ansible Documentation](https://docs.ansible.com/)

---

**Last Updated**: 2026-02-17
**Documentation Version**: 3.0.0
**Topology Version**: 3.0.0
