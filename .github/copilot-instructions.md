# GitHub Copilot Instructions

This file provides guidance when working with code in this repository.

## V5 Architecture (Current)

This is an **Infrastructure-as-Data** home lab project using a **Class -> Object -> Instance** topology model. The v5 architecture implements:

- Plugin-based compiler (ADR 0063)
- Generator architecture (ADR 0074)
- Framework/project separation (ADR 0075)

### Source of Truth

- `topology/topology.yaml` - Main entry point
- `topology/class-modules/` - Class definitions
- `topology/object-modules/` - Object definitions
- `projects/home-lab/topology/instances/` - Instance definitions

### Generated Outputs

All generators produce to `generated/<project>/`:
- Terraform configurations (Proxmox, MikroTik)
- Ansible inventory
- Bootstrap packages
- Documentation

### Key Principle

Edit topology files -> compile -> generate -> apply with Terraform/Ansible.

## Plugin Layer Contract for AI Agents (Mandatory)

Enforce a strict 4-level plugin boundary model:

1. Global infrastructure/core level.
2. Class level.
3. Object level.
4. Instance level.

All project code must follow SOLID principles.

Rules:

- Class-level plugins must not reference `obj.*` or `inst.*`.
- Object-level plugins must not reference `inst.*`.
- A plugin may call interfaces from its own level or higher only.
- Such interfaces may be implemented by higher levels (dependency inversion).
- Global plugins manage specific plugins through interfaces implemented by specific plugins or through other design patterns that preserve level boundaries.
- Applies to all plugin families (`compilers`, `validators`, `generators`, `assemblers`, `builders`).
- Runtime lifecycle has 6 stages: `discover -> compile -> validate -> generate -> assemble -> build`.
- `discover` stage is executed by discovery plugins (`base.discover.*`) in compiler family.
- Stage affinity must be preserved: `discover -> discovery plugins`, `compile -> compilers`, `validate -> validators`, `generate -> generators`, `assemble -> assemblers`, `build -> builders`.

Scope variants:

- Class level can include class-global and class-specific plugins.
- Object level can include object-global and object-specific plugins.
- If a class/object plugin contains no class/object-specific identifiers, migrate it to the global core level.

## Directory Structure

```
home-lab/
├── topology/                    # V5 topology definitions
│   ├── topology.yaml            # Main entry point
│   ├── classes/                 # Class definitions (L0-L7)
│   └── objects/                 # Object definitions
├── topology-tools/              # Compiler, validators, generators
│   ├── compile-topology.py      # Main compiler
│   ├── plugins/                 # Plugin implementations
│   │   ├── compilers/           # Compiler plugins
│   │   ├── validators/          # Validation plugins
│   │   ├── generators/          # Generator plugins
│   │   ├── assemblers/          # Assemble-stage plugins
│   │   └── builders/            # Build-stage plugins
│   ├── lib/                     # Core library
│   └── templates/               # Jinja2 templates
├── projects/home-lab/           # Project-specific data
│   ├── project.yaml             # Project manifest
│   ├── topology/instances/      # Instance definitions (L0-L7)
│   ├── secrets/                 # SOPS-encrypted secrets
│   └── framework.lock.yaml      # Framework version lock
├── scripts/                     # Orchestration scripts
│   ├── orchestration/lane.py    # Main lane orchestrator
│   └── validation/              # Validation scripts
├── tests/                       # Test suite
├── generated/                   # Generated outputs (DO NOT EDIT)
│   └── home-lab/                # Project outputs
│       ├── terraform/
│       ├── ansible/
│       ├── bootstrap/
│       └── docs/
├── build/                       # Build artifacts
├── dist/                        # Deploy packages
├── adr/                         # Architecture Decision Records
├── docs/                        # Manual documentation
├── configs/                     # Device configs (GL.iNet, VPN)
└── archive/                     # Archived v4 and legacy code
    ├── v4/                      # Complete v4 codebase
    ├── v4-generated/
    ├── v4-build/
    ├── v4-dist/
    └── migrated-and-archived/
```

## Migration Lane Guard (Synchronized)

- Active lane is repository root layout (`topology/`, `topology-tools/`, `projects/`, `tests/`, `scripts/`, `taskfiles/`).
- Legacy v4 baseline is stored under `archive/v4/` (reference and parity only).
- Do not create or use root `v4/` or root `v5/` directories.
- Do not modify `archive/v4/` unless explicitly requested for a v4 hotfix or parity investigation.
- All ongoing migration/runtime work must target root layout and ADR0080 contracts.

## Common Workflows

### 1. Compile and Generate

```bash
# Validate and compile topology
python scripts/orchestration/lane.py validate-v5

# Run full compilation
python topology-tools/compile-topology.py
# Parallel plugin execution is enabled by default.
# Use sequential mode only for troubleshooting/parity debugging.
python topology-tools/compile-topology.py --no-parallel-plugins

# Generate specific outputs
python scripts/orchestration/lane.py build-v5
```

### 2. Using Lane Orchestrator

```bash
# Full validation
V5_SECRETS_MODE=passthrough python scripts/orchestration/lane.py validate-v5

# Run specific phase
python scripts/orchestration/lane.py <phase-name>
```

### 3. Run Tests

```bash
# All tests
python -m pytest tests -q

# Specific test module
python -m pytest tests/plugin_integration/ -v
```

## Technology Stack

- **Hypervisor**: Proxmox VE 9 (Dell XPS L701X: 2 cores, 8GB RAM, SSD 180GB + HDD 500GB)
- **Router**: MikroTik Chateau LTE7 ax (ARM64, 1GB RAM, RouterOS 7.x)
- **SBC**: Orange Pi 5 (RK3588S, 16GB RAM, NVMe 256GB)
- **Infrastructure Provisioning**:
  - Terraform (bpg/proxmox provider v0.85+)
  - Terraform (terraform-routeros/routeros provider)
- **Configuration Management**: Ansible v2.14+ with cloud-init
- **Secrets**: SOPS with age encryption
- **Version Control**: Git

## ADR Policy (Mandatory)

Architecture decisions must be documented in `adr/`.

- One architectural decision -> one ADR file.
- Naming: `adr/NNNN-short-kebab-title.md`.
- Use `adr/0000-template.md` as a starting point.
- No architecture change is considered complete without an ADR entry.
- For superseding decisions, create a new ADR and mark prior one as superseded.
- Update `adr/REGISTER.md` with every new or superseded ADR.

## ADR Analysis Directories (Mandatory)

When analyzing, evaluating, or planning implementation of an ADR:

1. Create a dedicated analysis directory: `adr/NNNN-analysis/` where `NNNN` matches the ADR number (e.g., `adr/0080-analysis/`).
2. Save all analysis artifacts into that directory — **never** inline large plans into the ADR itself.
3. Standard files to create in the analysis directory:

   | File | Purpose |
   |------|---------|
   | `GAP-ANALYSIS.md` | Gap analysis: AS-IS vs TO-BE, identified issues, risk summary |
   | `IMPLEMENTATION-PLAN.md` | Detailed implementation plan: waves/phases, tasks, gates, acceptance criteria |
   | `CUTOVER-CHECKLIST.md` | Final cutover gate: checklist items grouped by concern area |

4. Additional files are allowed (e.g., `AUDIT-FIX-STATUS.md`, `OPERATOR-WORKFLOW.md`) when the ADR scope warrants them.
5. The ADR file itself (`adr/NNNN-*.md`) contains the decision and high-level migration plan only. Deep implementation detail lives in the analysis directory.

## Network Architecture

### Physical Layer
- **MikroTik Chateau**: Main router with LTE, WiFi 6, 4x GbE
- **Dell XPS L701X**: Proxmox hypervisor
- **Orange Pi 5**: Docker host for media services

### Network Topology
```
Internet (LTE/WAN)
       |
       v
+---------------------+
|  MikroTik Chateau   | <- Router, Firewall, VPN
|  192.168.88.1       |
+---------------------+
       |
       +-- VLAN 10: Servers (10.0.10.0/24)
       |   +-- Proxmox: 10.0.10.1
       |   +-- Orange Pi 5: 10.0.10.5
       |   +-- LXC containers
       |
       +-- VLAN 20: Users (192.168.20.0/24)
       +-- VLAN 30: IoT (192.168.30.0/24)
       +-- VLAN 40: Guest (192.168.40.0/24)
       +-- VLAN 99: Management (10.0.99.0/24)
```

## Secrets Management

**Never commit:**
- `terraform.tfvars`
- `terraform.tfstate`
- `.vault_pass`
- `*.pem`, `*.key`
- Unencrypted secret files

**Use:**
- SOPS with age for secrets in `projects/home-lab/secrets/`
- Environment variables for runtime secrets
- `V5_SECRETS_MODE=passthrough` for validation without decryption

## Common Pitfalls

### DON'T: Edit generated files
```bash
# Wrong:
vim generated/home-lab/terraform/proxmox/bridges.tf  # Will be overwritten!
```

### DO: Edit topology and regenerate
```bash
# Correct:
vim topology/object-modules/network/obj.network.vlan.servers.yaml
python topology-tools/compile-topology.py
```

### DON'T: Edit files outside topology hierarchy
```bash
# Wrong: direct edits to instance files for structural changes
```

### DO: Follow class -> object -> instance inheritance
```bash
# Correct: changes flow down from class through object to instance
```

## V4 Archive Reference

The v4 codebase is preserved in `archive/v4/` for reference. It used an OSI-like 8-layer architecture (L0-L7) with direct layer files. Key differences from v5:

- v4: Flat layer files (`archive/v4/topology/L*.yaml`)
- v5: Class -> Object -> Instance hierarchy
- v4: Script-based generators
- v5: Plugin-based microkernel architecture

See `archive/v4/README.md` and ADR 0062 for migration context.
