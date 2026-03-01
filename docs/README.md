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
#    Import generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc

# 2. Configure credentials
cd .work/native/terraform/mikrotik
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with passwords and keys

# 3. Deploy everything
cd deploy
make generate
make assemble-dist
make validate-dist
make deploy-all
```

See [DEPLOYMENT-STRATEGY.md](guides/DEPLOYMENT-STRATEGY.md) for the complete guide.

### For New Users

1. **Understand the architecture**: Read [TOPOLOGY-MODULAR.md](architecture/TOPOLOGY-MODULAR.md)
2. **Learn deployment strategy**: Read [DEPLOYMENT-STRATEGY.md](guides/DEPLOYMENT-STRATEGY.md)
3. **MikroTik setup**: Follow [MIKROTIK-TERRAFORM.md](guides/MIKROTIK-TERRAFORM.md)
4. **Create Proxmox USB**: Generate `generated/bootstrap/srv-gamayun/` and follow [PROXMOX-USB-AUTOINSTALL.md](guides/PROXMOX-USB-AUTOINSTALL.md)
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
| [DEPLOYMENT-STRATEGY.md](guides/DEPLOYMENT-STRATEGY.md) | Full deployment workflow with phases and dist assembly | UPDATED |
| [MIKROTIK-TERRAFORM.md](guides/MIKROTIK-TERRAFORM.md) | MikroTik RouterOS automation | NEW |
| [PROXMOX-USB-AUTOINSTALL.md](guides/PROXMOX-USB-AUTOINSTALL.md) | Proxmox auto-install USB creation from generated bootstrap package | UPDATED |
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

The infrastructure is deployed in 4 runtime phases, with an additional package-assembly layer:

| Phase | Target | Tool | Description |
|-------|--------|------|-------------|
| 0 | MikroTik | Manual | Bootstrap REST API (one-time) |
| 1 | MikroTik | Terraform | Network, firewall, VPN, containers |
| 2 | Proxmox | Terraform | LXC containers (PostgreSQL, Redis) |
| 3 | All | Ansible | Service configuration |
| 4 | All | Script | Verification checks |
| Dist | control packages | Python + Make | Assembled deploy packages and manifests |

```bash
# Full deployment command
cd deploy && make deploy-all

# Optional package assembly and validation
make assemble-dist
make validate-dist
make check-parity
make check-native-ready
make check-dist-ready
make materialize-dist-inputs
make clean-generated-managed

# Optional dist-first execution mode
make plan-dist
make deploy-all-dist

# Or step by step
make bootstrap-info   # Show bootstrap instructions
make plan             # Preview all changes
make apply-mikrotik   # Phase 1: Network
make apply-proxmox    # Phase 2: Compute
make configure        # Phase 3: Services
make test             # Phase 4: Verify
```

`native` remains the default rollback path. `dist` execution is opt-in and runs only from `dist/control/**` package roots with manifest-driven local-input checks. `make assemble-native` materializes canonical `local/` inputs into `.work/native/`, `make materialize-native-inputs` remains a compatibility alias, and `make materialize-dist-inputs` copies those same canonical local inputs into `dist/`.

Terraform also has a tracked exception layer under `terraform-overrides/`. Those files are additive reviewable overrides, not local inputs and not generated baseline.
Use `make check-terraform-override-flow` to smoke-test that override layer through native assembly, `dist/`, manifests, and parity.

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

Everything is defined in layered topology with `topology.yaml` as entry point:

```
topology.yaml
    ├── !include topology/L0-meta.yaml
    ├── !include topology/L1-foundation.yaml
    ├── !include topology/L2-network.yaml
    ├── !include topology/L3-data.yaml
    └── ... (L4-L7)
           ↓
    topology-tools/*.py
           ↓
    generated/
    ├── terraform/
    ├── ansible/inventory/
    ├── ansible/runtime/
    ├── docs/
    dist/
    ├── control/
    └── manifests/
```

### Generated vs. Manual Files

**Generated / Assembled** (DO NOT EDIT):
- `generated/terraform/*.tf`
- `generated/ansible/inventory/`
- `generated/ansible/runtime/`
- `dist/`
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
- **Generated bootstrap packages** - Device bootstrap assets under `generated/bootstrap/`
- **Verification** - Automated health checks

### NEW: Topology v3.0

- Added MikroTik-specific configuration
- Enhanced firewall policies
- QoS queue definitions
- Container service definitions

---

## File Structure

```
home-lab/
├── topology.yaml              # Main entry point
├── topology/                  # Modular YAML files
├── topology-tools/            # Python generators and validators
│   ├── validate-topology.py
│   ├── generate-terraform-proxmox.py
│   ├── generate-terraform-mikrotik.py
│   ├── generate-ansible-inventory.py
│   ├── assemble-ansible-runtime.py
│   ├── assemble-deploy.py
│   ├── validate-dist.py
│   ├── generate-docs.py
│   └── scripts/generators/
├── generated/                 # Auto-generated configs
│   ├── terraform/proxmox/
│   ├── terraform/mikrotik/
│   ├── ansible/
│   └── ...
├── dist/                      # Assembled deploy packages
│   ├── control/ansible/
│   ├── control/terraform/
│   ├── bootstrap/
│   └── manifests/
├── deploy/                    # Deployment orchestration (NEW)
│   ├── Makefile
│   └── phases/
├── bootstrap/                 # Legacy manual bootstrap assets
├── Migrated_and_archived/     # Archived legacy flows and assets
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

**Last Updated**: 2026-03-01
**Documentation Version**: 3.0.0
**Topology Version**: 3.0.0
