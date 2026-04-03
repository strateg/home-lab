# Home Lab Infrastructure

Infrastructure-as-Data home lab with Class-Object-Instance topology model.

## Architecture

**V5 Plugin-based microkernel** with layered deploy domain:

| Layer | ADR | Description |
|-------|-----|-------------|
| Topology | 0062, 0063 | Class → Object → Instance hierarchy |
| Compilation | 0074, 0080 | Plugin-based discover → compile → validate → generate → assemble → build |
| Secrets | 0072 | SOPS + age encryption |
| Deploy Bundle | 0085 | Immutable execution input |
| Deploy Runner | 0084 | Cross-platform dev / Linux deploy plane |
| Node Init | 0083 | Unified bootstrap contract (scaffold) |

## Repository Layout

```
home-lab/
├── topology/                    # Source of truth
│   ├── topology.yaml            # Main entry point
│   ├── class-modules/           # Class definitions
│   └── object-modules/          # Object definitions
├── projects/home-lab/           # Project-specific data
│   ├── topology/instances/      # Instance definitions
│   ├── secrets/                 # SOPS-encrypted secrets
│   └── deploy/                  # Deploy profile
├── topology-tools/              # Plugin runtime
│   └── plugins/                 # Compiler/validator/generator plugins
├── scripts/orchestration/       # Orchestration
│   └── deploy/                  # Deploy domain (runner, bundle, init-node)
├── generated/<project>/         # Generated outputs (DO NOT EDIT)
├── schemas/                     # JSON schemas
├── tests/                       # Test suite (822 tests)
└── adr/                         # Architecture Decision Records
```

## Quick Start

### 1. Validate and Build

```bash
# Validate topology
task validate:v5-passthrough

# Compile and generate all artifacts
task build:default

# Run tests
task test
```

### 2. Deploy Bundle Workflow (ADR 0085)

```bash
# Create immutable deploy bundle
task bundle:create

# List available bundles
task bundle:list

# Execute from bundle
task deploy:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id>
task deploy:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=<bundle_id>
```

### 3. Node Initialization (ADR 0083)

```bash
# Check initialization state
task deploy:init-status

# Plan node bootstrap
task deploy:init-node-plan -- BUNDLE=<bundle_id> NODE=<node_id>

# Execute (scaffold - hardware validation pending)
task deploy:init-node-run -- BUNDLE=<bundle_id> NODE=<node_id>
```

## Deploy Domain

### Runner Backends (ADR 0084)

| Runner | Platform | Use Case |
|--------|----------|----------|
| `native` | Linux | Default on Linux hosts |
| `wsl` | Windows | WSL-backed execution |
| `docker` | Any | Containerized CI/reproducibility |
| `remote` | Any | SSH to control node |

```bash
# Specify runner explicitly
task deploy:service-chain-evidence-check-bundle -- BUNDLE=<id> DEPLOY_RUNNER=wsl
```

### State Locations

| Path | Purpose |
|------|---------|
| `.work/deploy/bundles/<id>/` | Immutable deploy bundles |
| `.work/deploy-state/<project>/nodes/` | Initialization state |
| `.work/deploy-state/<project>/logs/` | Audit logs (JSONL) |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Hypervisor | Proxmox VE 8 (Dell XPS L701X) |
| Router | MikroTik Chateau LTE7 ax (RouterOS 7.x) |
| SBC | Orange Pi 5 (RK3588S, Debian) |
| IaC | Terraform (bpg/proxmox, terraform-routeros) |
| Config | Ansible 2.14+ |
| Secrets | SOPS + age |
| Tasks | Go-Task |

## Key Documentation

### Deploy Operations
- [DEPLOY-BUNDLE-WORKFLOW.md](docs/guides/DEPLOY-BUNDLE-WORKFLOW.md)
- [NODE-INITIALIZATION.md](docs/guides/NODE-INITIALIZATION.md)
- [OPERATOR-ENVIRONMENT-SETUP.md](docs/guides/OPERATOR-ENVIRONMENT-SETUP.md)

### Architecture
- [CLAUDE.md](CLAUDE.md) — AI agent instructions
- [ADR Register](adr/REGISTER.md) — All architecture decisions
- [PLUGIN_AUTHORING_GUIDE.md](docs/PLUGIN_AUTHORING_GUIDE.md)

### Runbooks
- [docs/runbooks/](docs/runbooks/)

## Development

### Run Tests

```bash
# All tests (822 pass, 4 skip)
task test

# Specific module
.venv/bin/python -m pytest tests/orchestration/ -v
```

### Plugin Development

```bash
# Validate plugin manifests
task validate:plugin-manifests

# Run with trace
python topology-tools/compile-topology.py --trace-execution
```

## Project Bootstrap

### From Distribution

```bash
task project:init-from-dist -- \
  PROJECT_ROOT=/path/to/new-project \
  PROJECT_ID=my-lab \
  FRAMEWORK_DIST_ZIP=/path/to/framework.zip \
  FRAMEWORK_DIST_VERSION=1.0.8
```

### From Submodule

```bash
task project:init -- \
  PROJECT_ROOT=/path/to/new-project \
  PROJECT_ID=my-lab \
  FRAMEWORK_SUBMODULE_URL=https://github.com/org/infra-topology-framework.git
```

## License

Private infrastructure repository.
