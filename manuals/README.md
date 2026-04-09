# Infrastructure-as-Data Operator Manuals

Comprehensive documentation for operating and developing the home lab infrastructure.

**ADR Reference:** 0062, 0063, 0072, 0074, 0080, 0082, 0083, 0084, 0085, 0086, 0092, 0093, 0094, 0095
**Last Updated:** 2026-04-09

---

## Documentation Overview

This manual set covers four operational planes:

| Plane | Purpose | Audience |
|-------|---------|----------|
| **Quality & CI Plane** | Validation, test lanes, CI and acceptance gates | Developers, Maintainers |
| **Deploy Plane** | Runtime execution and infrastructure deployment | Operators |
| **Development Plane** | Topology authoring and artifact generation | Developers |
| **Distribution Plane** | Framework distribution, trust verification, project bootstrap/upgrade | Release Engineers, Maintainers |

---

## Deploy Plane (Operations)

Runtime execution layer for infrastructure deployment.

| Document | Description |
|----------|-------------|
| [DEPLOY-PLANE-OPERATOR-MANUAL.md](deploy-plane/DEPLOY-PLANE-OPERATOR-MANUAL.md) | Complete operator guide with architecture, phases, state machine |
| [COMMAND-REFERENCE.md](deploy-plane/COMMAND-REFERENCE.md) | Quick reference for all deploy commands |
| [TROUBLESHOOTING.md](deploy-plane/TROUBLESHOOTING.md) | Error codes, diagnostics, recovery procedures |
| [SCENARIOS.md](deploy-plane/SCENARIOS.md) | Step-by-step operational scenarios |
| [SECRETS-OPERATOR-GUIDE.md](deploy-plane/SECRETS-OPERATOR-GUIDE.md) | ADR 0072 secrets workflow for operators |

**Key Concepts:**
- Deploy Bundle - Immutable execution input
- Runner Backends - native, wsl, docker, remote
- Init-Node - Node bootstrap orchestrator
- State Machine - pending → bootstrapping → initialized → verified

---

## Development Plane (Developers)

Build-time layer for topology compilation and artifact generation.

| Document | Description |
|----------|-------------|
| [DEVELOPMENT-PLANE-MANUAL.md](dev-plane/DEVELOPMENT-PLANE-MANUAL.md) | Complete developer guide with architecture, pipeline, plugins |
| [DEV-COMMAND-REFERENCE.md](dev-plane/DEV-COMMAND-REFERENCE.md) | Quick reference for all development commands |
| [DEV-TESTING-GUIDE.md](dev-plane/DEV-TESTING-GUIDE.md) | Testing patterns, fixtures, best practices |
| [DEV-TOPOLOGY-GUIDE.md](dev-plane/DEV-TOPOLOGY-GUIDE.md) | Topology authoring: classes, objects, instances |

**Key Concepts:**
- Pipeline Stages - discover → compile → validate → generate → assemble → build
- Plugin Microkernel - Extensible compilation architecture
- Class-Object-Instance - Three-level topology hierarchy
- Artifact Contracts - `ArtifactPlan` / `ArtifactGenerationReport` for migrated generators (ADR0093)

---

## Quality & CI Plane (Validation/Testing)

Quality and verification layer for local and CI gates.

| Command Group | Purpose |
|---------------|---------|
| `validate:*` | Topology and quality checks |
| `test:*` | Unit/integration/regression test suites |
| `ci:*` | Composed CI lanes |
| `acceptance:*` | Acceptance scenarios and quality gates |

---

## Distribution Plane (Release/Packaging)

Artifact-first release and consumption flow for framework distribution.

| Document | Description |
|----------|-------------|
| [DISTRIBUTION-PLANE-MANUAL.md](distribution-plane/DISTRIBUTION-PLANE-MANUAL.md) | End-to-end distribution, trust verification, bootstrap and upgrade |

**Key Concepts:**
- Distribution artifact - framework zip archive built from `topology/framework.yaml`
- Trust metadata - signature/provenance/SBOM enforced in strict verification
- Framework lock - `framework.lock.yaml` binds project to release artifact

---

## Recent Validation (ADR0093)

- `pytest` по релевантным наборам (контракты/интеграции): 23 passed, затем 75 passed.
- `pytest tests/plugin_contract/test_artifact_generation_contract.py tests/plugin_integration/test_ansible_inventory_generator.py`: 14 passed.
- `task framework:package-trust-gate`: PASS.
- `task framework:verify-lock-package-trust-signature`: PASS.
- `task ci:phase13-gate`: PASS (GO).
- `verify-framework-lock --strict`: OK.
- `compile-topology --strict-model-lock --secrets-mode passthrough`: errors=0.

---

## Quick Start

### For Operators

```bash
# Optional: preview operator cleanup
task deploy:clean-bundles DRY_RUN=true KEEP=5

# Build and create deploy bundle
task build:default
task bundle:create

# Check and apply changes
task deploy:service-chain-evidence-check-bundle BUNDLE=<id>
task deploy:service-chain-evidence-apply-bundle ALLOW_APPLY=YES BUNDLE=<id>

# Initialize new node
task deploy:init-node-run BUNDLE=<id> NODE=<node>
```

### For Developers

```bash
# Optional: reset generated/runtime artifacts before rebuild
task clean

# Validate topology
task validate:passthrough

# Build all artifacts
task build:default

# Run tests
task test

# Check diagnostics
cat build/diagnostics/report.txt
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Development Plane                             │
│                                                                  │
│  Topology YAML → Plugin Pipeline → Generated Artifacts          │
│                                                                  │
│  Stages: discover → compile → validate → generate → assemble    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Deploy Plane                                │
│                                                                  │
│  Generated Artifacts → Deploy Bundle → Runner → Infrastructure  │
│                                                                  │
│  Operations: bundle-create → init-node → service-chain          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Document Map

```
manuals/
├── README.md                        # This file
│
├── Deploy Plane (Operations)
│   ├── DEPLOY-PLANE-OPERATOR-MANUAL.md   # Complete operator guide
│   ├── COMMAND-REFERENCE.md              # Deploy commands
│   ├── TROUBLESHOOTING.md                # Error codes & recovery
│   └── SCENARIOS.md                      # Operational scenarios
│
└── Development Plane (Developers)
    ├── DEVELOPMENT-PLANE-MANUAL.md       # Complete developer guide
    ├── DEV-COMMAND-REFERENCE.md          # Development commands
    ├── DEV-TESTING-GUIDE.md              # Testing patterns
    └── DEV-TOPOLOGY-GUIDE.md             # Topology authoring
```

---

## Related Documentation

### Architecture Decision Records

| ADR | Title | Plane |
|-----|-------|-------|
| [0062](../adr/0062-class-object-instance-hierarchy.md) | Class-Object-Instance Hierarchy | Development |
| [0063](../adr/0063-plugin-microkernel.md) | Plugin Microkernel | Development |
| [0074](../adr/0074-generator-architecture.md) | Generator Architecture | Development |
| [0080](../adr/0080-stage-phase-lifecycle.md) | Stage/Phase Lifecycle | Development |
| [0083](../adr/0083-unified-node-initialization-contract.md) | Node Initialization | Deploy |
| [0084](../adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md) | Cross-Platform Runners | Deploy |
| [0085](../adr/0085-deploy-bundle-and-runner-workspace-contract.md) | Deploy Bundles | Deploy |
| [0072](../adr/0072-unified-secrets-management-sops-age.md) | Unified Secrets Management | Deploy |

### Other Documentation

- [CLAUDE.md](../CLAUDE.md) - AI agent instructions
- [PLUGIN_AUTHORING_GUIDE.md](../docs/PLUGIN_AUTHORING_GUIDE.md) - Full plugin guide
- [docs/guides/](../docs/guides/) - Operational guides
- [docs/runbooks/](../docs/runbooks/) - Operational runbooks

---

## File Locations

### State Files

| Path | Purpose |
|------|---------|
| `.work/deploy/bundles/<id>/` | Deploy bundles |
| `.work/deploy-state/<project>/nodes/` | Node init state |
| `.work/deploy-state/<project>/logs/` | Audit logs |
| `build/diagnostics/` | Compilation diagnostics |

### Source Files

| Path | Purpose |
|------|---------|
| `topology/topology.yaml` | Entry point |
| `topology/class-modules/` | Class definitions |
| `topology/object-modules/` | Object definitions |
| `projects/<project>/topology/instances/` | Instance bindings |

### Generated Files

| Path | Purpose |
|------|---------|
| `generated/<project>/terraform/` | Terraform configs |
| `generated/<project>/ansible/` | Ansible inventory |
| `generated/<project>/bootstrap/` | Bootstrap packages |

---

## Support

- **ADR Documentation:** `adr/*.md`
- **Error Codes:** See [TROUBLESHOOTING.md](deploy-plane/TROUBLESHOOTING.md)
- **Issues:** GitHub repository issues
