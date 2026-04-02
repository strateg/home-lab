# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Plugin Contract for AI Agents (Mandatory)

ADR0086 supersedes the old runtime 4-level visibility policy from ADR0063 Section 4B.
Plugin safety is enforced by stage/contract checks, deterministic discovery order, and ownership tests.

Rules:

- Runtime lifecycle is fixed: `discover -> compile -> validate -> generate -> assemble -> build`.
- Stage affinity must be preserved by plugin kind:
  - `discoverers -> discover`
  - `compilers -> compile`
  - `validators -> validate`
  - `generators -> generate`
  - `assemblers -> assemble`
  - `builders -> build`
- Manifest contracts are mandatory:
  - valid `depends_on` targets
  - valid `consumes.from_plugin` targets
  - valid stage/order ranges
- Discovery order is mandatory and test-enforced:
  1. framework manifest
  2. class manifests
  3. object manifests
  4. project manifests (`project_plugins_root`)
- Class/object module placement is an ownership convention, not runtime ACL.
  Shared standalone plugins should live under `topology-tools/plugins/<family>/`.

## Directory Structure

```
home-lab/
├── topology/                    # V5 topology definitions
│   ├── topology.yaml            # Main entry point
│   ├── class-modules/           # Class definitions
│   └── object-modules/          # Object definitions
├── topology-tools/              # Plugin runtime and toolchain
│   ├── compile-topology.py      # Main compiler
│   ├── plugins/                 # Plugin implementations
│   │   ├── discoverers/         # Discover-stage plugins
│   │   ├── compilers/           # Compile-stage plugins
│   │   ├── validators/          # Validation plugins
│   │   ├── generators/          # Generator plugins
│   │   ├── assemblers/          # Assemble-stage plugins
│   │   └── builders/            # Build-stage plugins
│   ├── kernel/                  # Runtime microkernel APIs
│   └── templates/               # Jinja2 templates
├── projects/home-lab/           # Project-specific data
│   ├── project.yaml             # Project manifest
│   ├── topology/instances/      # Instance definitions (L0-L7)
│   ├── secrets/                 # SOPS-encrypted secrets
│   └── framework.lock.yaml      # Framework version lock
├── scripts/                     # Orchestration scripts
│   ├── orchestration/
│   │   ├── lane.py              # Main lane orchestrator
│   │   └── deploy/              # Deploy domain (ADR 0083-0085)
│   │       ├── runner.py        # DeployRunner backends
│   │       ├── bundle.py        # Bundle create/list/inspect/delete
│   │       ├── init_node.py     # Node initialization orchestrator
│   │       ├── adapters/        # Bootstrap mechanism adapters
│   │       ├── state.py         # State machine helpers
│   │       └── logging.py       # Structured audit logging
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
├── schemas/                     # JSON schemas
│   ├── deploy-bundle-manifest.schema.json
│   ├── deploy-profile.schema.json
│   └── initialization-contract.schema.json
├── adr/                         # Architecture Decision Records
├── docs/                        # Manual documentation
├── configs/                     # Device configs (GL.iNet, VPN)
└── archive/                     # Archived v4 and legacy code
    ├── v4/                      # Complete v4 codebase
    ├── v4-build/
    ├── tests-deprecated/
    └── migrated-and-archived/
```

## Migration Lane Guard (Synchronized with Codex)

- Active lane is repository root layout (`topology/`, `topology-tools/`, `projects/`, `tests/`, `scripts/`, `taskfiles/`).
- Legacy v4 baseline is stored under `archive/v4/` (reference and parity only).
- Do not create or use root `v4/` or root `v5/` directories.
- Do not modify `archive/v4/` unless the user explicitly requests a v4 hotfix or parity investigation.
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

### 2.1 Deploy Domain Architecture (ADR 0083/0084/0085)

The deploy domain implements a layered architecture:

| ADR | Scope | Status |
|-----|-------|--------|
| 0085 | Deploy bundle contract | ✅ Complete |
| 0084 | Cross-platform dev / Linux deploy plane | ✅ Complete |
| 0083 | Node initialization contract | ✅ Scaffold (hardware pending) |

**Key concepts:**

- **Deploy bundle** — immutable execution input at `.work/deploy/bundles/<bundle_id>/`
- **Deploy runner** — workspace-aware execution backend (native/wsl/docker/remote)
- **Init-node** — orchestrator for device bootstrap lifecycle

**Deploy bundle workflow:**

```bash
# Build immutable deploy bundle from generated artifacts
task framework:deploy-bundle-create
task framework:deploy-bundle-list

# Execute service-chain lanes from selected bundle
task framework:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id>
task framework:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=<bundle_id>
```

**Node initialization (scaffold):**

```bash
# Check init state
task framework:deploy-init-status

# Plan node initialization
task framework:deploy-init-node-plan -- BUNDLE=<bundle_id> NODE=<node_id>
```

**State file locations:**

| Path | Purpose |
|------|---------|
| `.work/deploy/bundles/<id>/` | Immutable deploy bundles |
| `.work/deploy-state/<project>/nodes/` | Initialization state |
| `.work/deploy-state/<project>/logs/` | Audit logs (JSONL) |

**References:**
- `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md`
- `docs/guides/NODE-INITIALIZATION.md`
- `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md`

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

## Working with Claude Code

When Claude Code helps with this repository:

1. **Always check topology files first** - They are the source of truth
2. **Run validation after changes** - Use `lane.py validate-v5`
3. **Respect plugin contracts** - Follow stage affinity + manifest/discovery contract checks
4. **Record architecture decisions in ADR** - add/update `adr/NNNN-*.md`
5. **Run tests** - `python -m pytest tests -q`

**Ask Claude Code to:**
- "Add a new instance to L4-platform"
- "Add a service definition"
- "Run validation"
- "Check test coverage"

**Don't ask Claude Code to:**
- Edit files in `generated/` directly
- Break plugin stage/manifest/discovery contracts
- Skip validation steps

## V4 Archive Reference

The v4 codebase is preserved in `archive/v4/` for reference. It used an OSI-like 8-layer architecture (L0-L7) with direct layer files. Key differences from v5:

- v4: Flat layer files (`archive/v4/topology/L*.yaml`)
- v5: Class -> Object -> Instance hierarchy
- v4: Script-based generators
- v5: Plugin-based microkernel architecture

See `archive/v4/README.md` and ADR 0062 for migration context.
