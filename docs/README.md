# Home Lab Documentation

Welcome to the home lab infrastructure documentation.

**Architecture:** V5 Infrastructure-as-Data with Class-Object-Instance topology model
**Last Updated:** 2026-04-01

---

## Quick Start

### For Operators

```bash
# 1. Validate topology
task validate:passthrough

# 2. Compile and generate
task build:default

# 3. Create deploy bundle
task bundle:create
task bundle:list

# 4. Execute from bundle
task deploy:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id>
```

### For New Users

1. **Understand v5 architecture:** Read [CLAUDE.md](../CLAUDE.md)
2. **Learn plugin system:** Read [PLUGIN_AUTHORING_GUIDE.md](PLUGIN_AUTHORING_GUIDE.md)
3. **Deploy workflow:** Read [guides/DEPLOY-BUNDLE-WORKFLOW.md](guides/DEPLOY-BUNDLE-WORKFLOW.md)
4. **Secrets management:** Read [secrets-management.md](secrets-management.md)

---

## Documentation Structure

```
docs/
├── README.md                    # You are here
├── PLUGIN_AUTHORING_GUIDE.md    # Plugin development guide (v5)
├── PLUGIN_IMPLEMENTATION_EXAMPLES.md  # Plugin examples
├── secrets-management.md        # SOPS+age secrets (ADR 0072)
├── diagnostics-catalog.md       # Compiler error codes
├── guides/                      # Operational guides
│   ├── DEPLOY-BUNDLE-WORKFLOW.md    # Bundle-based deploy (ADR 0085)
│   ├── NODE-INITIALIZATION.md       # Init-node scaffold (ADR 0083)
│   ├── OPERATOR-ENVIRONMENT-SETUP.md # Runner setup (ADR 0084)
│   ├── DOCKER-RUNNER-SETUP.md       # Docker runner guide
│   ├── REMOTE-RUNNER-SETUP.md       # Remote runner guide
│   ├── MIKROTIK-TERRAFORM.md        # MikroTik automation
│   └── ...
├── framework/                   # Framework documentation
│   ├── FRAMEWORK-V5.md              # Framework contract
│   └── ...
├── runbooks/                    # Operational runbooks
│   ├── DEPLOY-RUNBOOK.md            # Deploy operations
│   └── ...
├── architecture/                # Architecture docs
└── archive/                     # Historical documents
    └── v5-superseded/           # Docs superseded by v5
```

---

## Key ADRs for Deploy Domain

| ADR | Title | Status |
|-----|-------|--------|
| [0083](../adr/0083-unified-node-initialization-contract.md) | Unified Node Initialization Contract | Scaffold complete |
| [0084](../adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md) | Cross-Platform Dev / Linux Deploy Plane | Complete |
| [0085](../adr/0085-deploy-bundle-and-runner-workspace-contract.md) | Deploy Bundle and Runner Workspace | Complete |

---

## Documentation by Topic

### Deploy Operations (ADR 0083-0085)

| Document | Description |
|----------|-------------|
| [DEPLOY-BUNDLE-WORKFLOW.md](guides/DEPLOY-BUNDLE-WORKFLOW.md) | Bundle create/inspect/execute workflow |
| [NODE-INITIALIZATION.md](guides/NODE-INITIALIZATION.md) | Init-node CLI and state management |
| [OPERATOR-ENVIRONMENT-SETUP.md](guides/OPERATOR-ENVIRONMENT-SETUP.md) | WSL/Docker/Remote runner setup |

### Plugin Development (ADR 0063-0080)

| Document | Description |
|----------|-------------|
| [PLUGIN_AUTHORING_GUIDE.md](PLUGIN_AUTHORING_GUIDE.md) | How to write v5 plugins |
| [PLUGIN_IMPLEMENTATION_EXAMPLES.md](PLUGIN_IMPLEMENTATION_EXAMPLES.md) | Real plugin examples |
| [diagnostics-catalog.md](diagnostics-catalog.md) | Error and warning codes |

### Secrets Management (ADR 0072)

| Document | Description |
|----------|-------------|
| [secrets-management.md](secrets-management.md) | SOPS+age encryption workflow |

### MikroTik Bootstrap (ADR 0057)

| Document | Description |
|----------|-------------|
| [NETINSTALL-CLI-INDEX.md](NETINSTALL-CLI-INDEX.md) | Netinstall documentation index |
| [guides/MIKROTIK-TERRAFORM.md](guides/MIKROTIK-TERRAFORM.md) | Terraform automation guide |

### Framework & Multi-Project (ADR 0075-0081)

| Document | Description |
|----------|-------------|
| [framework/FRAMEWORK-V5.md](framework/FRAMEWORK-V5.md) | Framework/project contract |
| [framework/PROJECT-BOOTSTRAP-AND-FRAMEWORK-INTEGRATION.md](framework/PROJECT-BOOTSTRAP-AND-FRAMEWORK-INTEGRATION.md) | New project setup guide |
| [framework/OPERATOR-WORKFLOWS.md](framework/OPERATOR-WORKFLOWS.md) | Framework lock and update workflows |
| [framework/SUPPLY-CHAIN-SECURITY.md](framework/SUPPLY-CHAIN-SECURITY.md) | Supply chain security (signatures, SBOM, provenance) |
| [framework/FRAMEWORK-RELEASE-GUIDE.md](framework/FRAMEWORK-RELEASE-GUIDE.md) | Framework release process |

---

## For External Adopters (New Projects)

Quick path to create a new project using the framework:

### Option 1: Using Distribution Artifact (Recommended)

```bash
# Initialize new project from framework zip
python topology-tools/utils/init-project-repo.py \
  --output-root /path/to/new-project \
  --project-id my-home-lab \
  --framework-dist-zip /path/to/infra-topology-framework-1.0.8.zip \
  --framework-dist-version 1.0.8 \
  --force

# Verify and compile
cd /path/to/new-project
python framework/topology-tools/verify-framework-lock.py --strict
python framework/topology-tools/compile-topology.py --secrets-mode passthrough
```

### Option 2: Using Git Submodule

```bash
# Create new project
mkdir my-home-lab && cd my-home-lab
git init

# Add framework as submodule
git submodule add https://github.com/<org>/infra-topology-framework.git framework
git submodule update --init --recursive

# Bootstrap project structure
python framework/topology-tools/utils/bootstrap-project-repo.py \
  --framework-root ./framework \
  --output-root . \
  --project-id my-home-lab \
  --force
```

**Full guide:** [framework/PROJECT-BOOTSTRAP-AND-FRAMEWORK-INTEGRATION.md](framework/PROJECT-BOOTSTRAP-AND-FRAMEWORK-INTEGRATION.md)

---

## Development Workflow

### Quick Commands

| Task | Description |
|------|-------------|
| `task build:compile-dev` | Compile with dev profile (auto-regenerates lock) |
| `task build:compile-validate` | Quick validation only |
| `task framework:lock-refresh-all` | Regenerate locks for all projects |
| `task framework:security-status` | Show security status for all projects |

### Runtime Profiles

| Profile | Lock Behavior | Use Case |
|---------|---------------|----------|
| `production` | Strict (E7824 blocks) | CI/CD, releases |
| `dev` | Auto-regenerate | Development iteration |
| `modeled` | Strict | Model testing |
| `test-real` | Strict | Integration tests |

**Full guide:** [framework/OPERATOR-WORKFLOWS.md](framework/OPERATOR-WORKFLOWS.md)

---

## V5 Architecture Overview

```
topology/
├── topology.yaml              # Main entry point
├── class-modules/             # Class definitions
└── object-modules/            # Object definitions
         ↓
topology-tools/plugins/        # Plugin-based compilation
         ↓
generated/<project>/           # Generated outputs
├── terraform/proxmox/
├── terraform/mikrotik/
├── ansible/
├── bootstrap/
└── docs/
         ↓
.work/deploy/bundles/<id>/     # Immutable deploy bundles (ADR 0085)
         ↓
DeployRunner                   # Execution backend (ADR 0084)
```

---

## State File Locations

| Path | Purpose |
|------|---------|
| `.work/deploy/bundles/<id>/` | Immutable deploy bundles |
| `.work/deploy-state/<project>/nodes/` | Initialization state |
| `.work/deploy-state/<project>/logs/` | Audit logs (JSONL) |
| `generated/<project>/` | Generated artifacts |
| `build/` | Compilation artifacts |

---

## External References

### Terraform Providers

- [terraform-routeros](https://registry.terraform.io/providers/terraform-routeros/routeros/latest/docs) - MikroTik RouterOS
- [bpg/proxmox](https://registry.terraform.io/providers/bpg/proxmox/latest/docs) - Proxmox VE

### Tools

- [SOPS](https://github.com/getsops/sops) - Secrets management
- [age](https://github.com/FiloSottile/age) - Encryption
- [Go-Task](https://taskfile.dev/) - Task runner

---

## Archived Documentation

Documents superseded by v5 architecture are in `archive/v5-superseded/`:

- `ANSIBLE-VAULT-GUIDE.md` → Use `secrets-management.md` (SOPS+age)
- `DEPLOYMENT-STRATEGY.md` → Use `guides/DEPLOY-BUNDLE-WORKFLOW.md`
- `DEVELOPERS_GUIDE_GENERATORS.md` → Use `PLUGIN_AUTHORING_GUIDE.md`
