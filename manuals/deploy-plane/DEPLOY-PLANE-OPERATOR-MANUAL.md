# Deploy Plane Operator Manual

**Version:** 1.0
**ADR Reference:** 0083, 0084, 0085
**Last Updated:** 2026-04-01

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Phases and Lifecycle](#phases-and-lifecycle)
4. [Runner Backends](#runner-backends)
5. [Deploy Bundle Operations](#deploy-bundle-operations)
6. [Node Initialization](#node-initialization)
7. [Service Chain Execution](#service-chain-execution)
8. [State Management](#state-management)
9. [Deploy Profile Configuration](#deploy-profile-configuration)
10. [Environment Verification](#environment-verification)

---

## Overview

Deploy Plane is the execution layer for Infrastructure-as-Data home lab operations. It provides:

- **Immutable deploy bundles** - Reproducible execution inputs (ADR 0085)
- **Cross-platform runners** - Linux-backed execution on any dev machine (ADR 0084)
- **Node initialization** - Unified bootstrap contract for all node types (ADR 0083)
- **Service chain execution** - Terraform/Ansible orchestration with evidence

### Key Principles

1. **Bundle-first execution** - All deploy operations use immutable bundles
2. **Linux deploy plane** - Canonical execution is always Linux-backed
3. **State machine integrity** - Node lifecycle has strict state transitions
4. **Audit trail** - All operations logged to JSONL for compliance

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Operator Workstation                          │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Windows   │   │    Linux    │   │    macOS    │               │
│  │   + WSL     │   │   Native    │   │  + Docker   │               │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘               │
└─────────┼─────────────────┼─────────────────┼───────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Deploy Runner Abstraction                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │  native  │  │   wsl    │  │  docker  │  │     remote       │    │
│  │  Linux   │  │  Ubuntu  │  │ container│  │ SSH control node │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Deploy Bundle                                 │
│  .work/deploy/bundles/<bundle_id>/                                  │
│  ├── manifest.yaml          # Node list, mechanisms, artifacts      │
│  ├── metadata.yaml          # Build provenance                      │
│  ├── checksums.sha256       # Integrity verification                │
│  └── artifacts/                                                      │
│      ├── generated/         # Terraform, Ansible, Bootstrap         │
│      └── secrets/           # Decrypted secrets (optional)          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Target Infrastructure                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   MikroTik   │  │   Proxmox    │  │  Orange Pi   │              │
│  │  (netinstall)│  │ (cloud_init) │  │ (ansible)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phases and Lifecycle

### Complete Deploy Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1: Build                                                       │
│ ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐             │
│ │ Topology│ → │ Compile │ → │Validate │ → │Generate │             │
│ │  YAML   │   │         │   │         │   │Artifacts│             │
│ └─────────┘   └─────────┘   └─────────┘   └─────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 2: Bundle                                                      │
│ ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│ │   Create    │ → │   Verify    │ → │   Stage     │               │
│ │   Bundle    │   │  Checksums  │   │ to Runner   │               │
│ └─────────────┘   └─────────────┘   └─────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 3: Initialize (per node)                                       │
│ ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐             │
│ │Preflight│ → │ Execute │ → │Handover │ → │ Verify  │             │
│ │ Checks  │   │Bootstrap│   │ Checks  │   │  State  │             │
│ └─────────┘   └─────────┘   └─────────┘   └─────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 4: Service Chain                                               │
│ ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│ │  Terraform  │ → │   Ansible   │ → │  Evidence   │               │
│ │ plan/apply  │   │  playbooks  │   │   Report    │               │
│ └─────────────┘   └─────────────┘   └─────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

### Node State Machine

```
                    ┌─────────────────────────┐
                    │        pending          │
                    │   (initial discovery)   │
                    └───────────┬─────────────┘
                                │
                    bootstrap-start
                                │
                                ▼
                    ┌─────────────────────────┐
              ┌─────│      bootstrapping      │─────┐
              │     │   (executing adapter)   │     │
              │     └─────────────────────────┘     │
              │                                     │
    bootstrap-complete                    bootstrap-failed
              │                                     │
              ▼                                     ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│      initialized        │           │         failed          │
│  (ready for handover)   │           │  (requires remediation) │
└───────────┬─────────────┘           └───────────┬─────────────┘
            │                                     │
   handover-verified                     retry (bootstrap-start)
            │                                     │
            ▼                                     │
┌─────────────────────────┐                       │
│        verified         │◄──────────────────────┘
│   (handover complete)   │
└─────────────────────────┘
```

### Legal State Transitions

| From State | Allowed Transitions |
|------------|---------------------|
| `pending` | `bootstrapping` |
| `bootstrapping` | `initialized`, `failed` |
| `initialized` | `verified`, `failed` |
| `verified` | `bootstrapping`, `pending`, `failed` |
| `failed` | `bootstrapping` |

---

## Runner Backends

### Runner Selection

```bash
# Auto-detect (default)
task bundle:create

# Explicit runner override
task deploy:init-node-run -- BUNDLE=<id> NODE=<node> DEPLOY_RUNNER=wsl
task deploy:service-chain-evidence-check-bundle -- BUNDLE=<id> DEPLOY_RUNNER=docker
```

### Native Runner (Linux)

**Platform:** Linux only
**Use case:** Direct execution on Linux dev machine or CI

```bash
# Capabilities
- interactive_confirmation: true
- host_network_access: true
- path_translation: false
- persistent_workspace: true
```

### WSL Runner (Windows)

**Platform:** Windows with WSL2
**Use case:** Windows developer workstation

```bash
# Check available distros
wsl -l -q

# Configure in deploy-profile.yaml
runners:
  wsl:
    distro: Ubuntu  # Default
```

**Path Translation:**
```
C:\Users\user\project → /mnt/c/Users/user/project
```

### Docker Runner

**Platform:** Any with Docker
**Use case:** CI/CD, reproducible builds, isolated execution

```bash
# Build toolchain image
task deploy:docker-toolchain-build

# Smoke test
task deploy:docker-toolchain-smoke

# Configure
runners:
  docker:
    image: homelab-toolchain:latest
    network: host  # For Terraform/Ansible access to infra
```

### Remote Runner

**Platform:** Any with SSH access
**Use case:** Execute from dedicated control node

```bash
# Configure
runners:
  remote:
    host: control.example.com
    user: deploy
    sync_method: rsync  # or scp
```

**Bundle sync methods:**
- `rsync` - Incremental sync (faster for updates)
- `scp` - Full copy (simpler, no rsync required)

---

## Deploy Bundle Operations

### Create Bundle

```bash
# Standard bundle from generated artifacts
task bundle:create

# With secrets injection (for air-gapped deploy)
task bundle:create -- INJECT_SECRETS=true

# Custom paths
task bundle:create -- \
  GENERATED_ROOT=/path/to/generated \
  SECRETS_ROOT=/path/to/secrets
```

**Output:**
```json
{
  "bundle_id": "b-a1b2c3d4e5f6",
  "bundle_path": ".work/deploy/bundles/b-a1b2c3d4e5f6"
}
```

### List Bundles

```bash
task bundle:list
```

**Output:**
```json
{
  "bundles": [
    {
      "bundle_id": "b-a1b2c3d4e5f6",
      "created_at": "2026-04-01T10:30:00Z",
      "path": ".work/deploy/bundles/b-a1b2c3d4e5f6",
      "project": "home-lab"
    }
  ]
}
```

### Inspect Bundle

```bash
# Full inspection with checksum verification
task bundle:inspect -- BUNDLE=b-a1b2c3d4e5f6

# Skip checksum verification (faster)
task bundle:inspect -- BUNDLE=b-a1b2c3d4e5f6 SKIP_CHECKSUMS=true
```

**Output includes:**
- `manifest` - Node list with mechanisms and artifacts
- `metadata` - Build provenance (source paths, hashes)
- `checksums_ok` - Integrity verification result
- `files_count` - Total files in bundle

### Delete Bundle

```bash
task bundle:delete -- BUNDLE=b-a1b2c3d4e5f6
```

### Bundle Layout

```
.work/deploy/bundles/<bundle_id>/
├── manifest.yaml           # Execution manifest
├── metadata.yaml           # Build provenance
├── checksums.sha256        # Integrity hashes
└── artifacts/
    ├── generated/
    │   ├── terraform/
    │   │   ├── proxmox/
    │   │   └── mikrotik/
    │   ├── ansible/
    │   ├── bootstrap/
    │   │   ├── rtr-mikrotik-chateau/
    │   │   ├── pve-gamayun/
    │   │   └── sbc-orangepi5/
    │   └── docs/
    └── secrets/              # Only with INJECT_SECRETS=true
        └── decrypted.yaml
```

---

## Node Initialization

### Status Overview

```bash
task deploy:init-status
```

**Output:**
```json
{
  "status": "ok",
  "state_path": ".work/deploy-state/home-lab/nodes/INITIALIZATION-STATE.yaml",
  "total_nodes": 3,
  "by_status": {
    "pending": 2,
    "verified": 1
  },
  "updated_at": "2026-04-01T10:30:00Z"
}
```

### Plan Node Initialization

```bash
# Single node
task deploy:init-node-plan -- BUNDLE=b-123 NODE=rtr-mikrotik-chateau

# All pending nodes
task deploy:init-all-pending-plan -- BUNDLE=b-123
```

**Output:**
```json
{
  "status": "planned",
  "project_id": "home-lab",
  "bundle": ".work/deploy/bundles/b-123",
  "mode": "node",
  "selected_nodes": ["rtr-mikrotik-chateau"],
  "verify_only": false,
  "force": false,
  "plan_only": true
}
```

### Execute Node Initialization

```bash
# Single node
task deploy:init-node-run -- BUNDLE=b-123 NODE=rtr-mikrotik-chateau

# All pending nodes
task deploy:init-all-pending-run -- BUNDLE=b-123

# With flags
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=pve-gamayun \
  DEPLOY_RUNNER=wsl \
  IMPORT_EXISTING=true
```

### Verify Node Handover

```bash
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=rtr-mikrotik-chateau \
  VERIFY_ONLY=true
```

### Reset Node State

```bash
# Reset requires confirmation
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=rtr-mikrotik-chateau \
  RESET=true \
  CONFIRM_RESET=true
```

### Initialization Mechanisms

| Mechanism | Node Types | Bootstrap Artifacts |
|-----------|------------|---------------------|
| `netinstall` | MikroTik routers | `*.rsc` scripts |
| `cloud_init` | Proxmox VMs | `user-data`, `meta-data`, `network-config` |
| `unattended_install` | Proxmox host | `answer.toml`, `post-install-minimal.sh` |
| `ansible_bootstrap` | SBCs, containers | Ansible playbooks |

### Init-Node CLI Flags

| Flag | Description |
|------|-------------|
| `--bundle` | Bundle ID or absolute path (required) |
| `--node` | Single node ID to process |
| `--all-pending` | Process all nodes in pending state |
| `--plan-only` | Show execution plan without mutation |
| `--verify-only` | Run handover checks only |
| `--force` | Override state machine guards |
| `--import-existing` | Mark node as imported (pre-existing) |
| `--reset` | Reset node to pending state |
| `--confirm-reset` | Required with --reset |
| `--acknowledge-drift` | Accept topology/state drift |
| `--deploy-runner` | Override runner (native/wsl/docker/remote) |
| `--skip-environment-check` | Skip deploy environment validation |

---

## Service Chain Execution

### Dry Run

```bash
# Without bundle (uses generated/ directly)
task deploy:service-chain-evidence-dry

# With bundle (strict immutable execution)
task deploy:service-chain-evidence-dry-bundle -- BUNDLE=b-123
```

### Maintenance Check (Plan)

```bash
# Terraform plan + Ansible check
task deploy:service-chain-evidence-check-bundle -- BUNDLE=b-123

# With backend configs
task deploy:service-chain-evidence-check-bundle -- \
  BUNDLE=b-123 \
  PROXMOX_BACKEND_CONFIG=configs/proxmox-backend.tfbackend \
  MIKROTIK_BACKEND_CONFIG=configs/mikrotik-backend.tfbackend
```

### Maintenance Apply

```bash
# Requires explicit approval
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-123

# With auto-approve for Terraform
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=b-123 \
  TERRAFORM_AUTO_APPROVE=true
```

### Service Chain Flags

| Flag | Description |
|------|-------------|
| `BUNDLE` | Bundle ID (required for *-bundle variants) |
| `ALLOW_APPLY` | Must be `YES` for apply operations |
| `CONTINUE_ON_FAILURE` | Don't stop on first error |
| `DEPLOY_RUNNER` | Override runner |
| `ANSIBLE_VIA_WSL` | Force Ansible through WSL |
| `TERRAFORM_AUTO_APPROVE` | Skip Terraform confirmation |
| `INJECT_SECRETS` | Use decrypted secrets from bundle |
| `PROXMOX_BACKEND_CONFIG` | Terraform backend config for Proxmox |
| `MIKROTIK_BACKEND_CONFIG` | Terraform backend config for MikroTik |
| `PROXMOX_VAR_FILE` | Variable file for Proxmox |
| `MIKROTIK_VAR_FILE` | Variable file for MikroTik |

---

## State Management

### State File Locations

| Path | Purpose |
|------|---------|
| `.work/deploy/bundles/<id>/` | Immutable deploy bundles |
| `.work/deploy-state/<project>/nodes/INITIALIZATION-STATE.yaml` | Node initialization state |
| `.work/deploy-state/<project>/logs/` | Audit logs (JSONL) |

### Initialization State Format

```yaml
version: "1.0"
updated_at: "2026-04-01T10:30:00Z"
nodes:
  - id: rtr-mikrotik-chateau
    mechanism: netinstall
    status: verified
    last_action: handover-verified
    last_action_at: "2026-04-01T10:30:00Z"
    last_error: null
    attempt_count: 1
    imported: false
    history:
      - timestamp: "2026-04-01T10:25:00Z"
        from_state: pending
        to_state: bootstrapping
        action: bootstrap-start
      - timestamp: "2026-04-01T10:28:00Z"
        from_state: bootstrapping
        to_state: initialized
        action: bootstrap-complete
      - timestamp: "2026-04-01T10:30:00Z"
        from_state: initialized
        to_state: verified
        action: handover-verified
```

### Audit Log Format

```jsonl
{"timestamp":"2026-04-01T10:30:00Z","level":"info","event":"node-execute-success","message":"Bootstrap execution completed.","node":"rtr-mikrotik-chateau","mechanism":"netinstall","status":"initialized"}
{"timestamp":"2026-04-01T10:30:05Z","level":"info","event":"node-verify-success","message":"Handover checks passed.","node":"rtr-mikrotik-chateau","mechanism":"netinstall","status":"verified"}
```

---

## Deploy Profile Configuration

### File Location

```
projects/<project>/deploy/deploy-profile.yaml
```

### Full Configuration Example

```yaml
schema_version: "1.0"
project: home-lab

# Default runner selection (native|wsl|docker|remote)
default_runner: wsl

runners:
  wsl:
    distro: Ubuntu
  docker:
    image: homelab-toolchain:latest
    network: host
  remote:
    host: control.example.com
    user: deploy
    sync_method: rsync  # or scp

timeouts:
  handover_total: 300      # Total handover check time (seconds)
  handover_check: 30       # Individual check timeout
  terraform_plan: 120      # Terraform plan timeout
  ansible_playbook: 600    # Ansible playbook timeout

bundle:
  retention_count: 5       # Keep last N bundles
  auto_cleanup: true       # Auto-delete old bundles
```

### Default Values

| Setting | Default |
|---------|---------|
| `default_runner` | Auto-detect |
| `runners.wsl.distro` | `Ubuntu` |
| `runners.docker.image` | `homelab-toolchain:latest` |
| `runners.docker.network` | `host` |
| `runners.remote.user` | `deploy` |
| `runners.remote.sync_method` | `rsync` |
| `timeouts.handover_total` | `300` |
| `timeouts.handover_check` | `30` |
| `timeouts.terraform_plan` | `120` |
| `timeouts.ansible_playbook` | `600` |
| `bundle.retention_count` | `5` |
| `bundle.auto_cleanup` | `true` |

---

## Environment Verification

### Check Deploy Environment

The init-node orchestrator automatically verifies the deploy environment before execution. To skip this check:

```bash
task deploy:init-node-run -- \
  BUNDLE=b-123 \
  NODE=rtr-mikrotik-chateau \
  SKIP_ENVIRONMENT_CHECK=true
```

### Environment Report

```json
{
  "ready": true,
  "platform": "Windows",
  "runner": "wsl:Ubuntu",
  "issues": [],
  "warnings": [],
  "tools": {
    "bash": true,
    "terraform": true,
    "ansible": true
  }
}
```

### Common Environment Issues

| Issue | Resolution |
|-------|------------|
| WSL not available | `wsl --install -d Ubuntu` |
| Required tool missing | Install tool in runner environment |
| Runner not available | Check runner configuration in deploy-profile.yaml |
| Remote host unreachable | Verify SSH access and credentials |

---

## Quick Reference

### Complete Workflow

```bash
# 1. Build topology
task build:default

# 2. Create bundle
task bundle:create

# 3. Check status
task deploy:init-status

# 4. Plan initialization
task deploy:init-all-pending-plan -- BUNDLE=<bundle_id>

# 5. Execute initialization
task deploy:init-all-pending-run -- BUNDLE=<bundle_id>

# 6. Run service chain (check)
task deploy:service-chain-evidence-check-bundle -- BUNDLE=<bundle_id>

# 7. Run service chain (apply)
task deploy:service-chain-evidence-apply-bundle -- \
  ALLOW_APPLY=YES \
  BUNDLE=<bundle_id>
```

### Emergency Operations

```bash
# Reset stuck node
task deploy:init-node-run -- \
  BUNDLE=<bundle_id> \
  NODE=<node_id> \
  RESET=true \
  CONFIRM_RESET=true

# Force re-initialization
task deploy:init-node-run -- \
  BUNDLE=<bundle_id> \
  NODE=<node_id> \
  FORCE=true

# Skip environment checks
task deploy:init-node-run -- \
  BUNDLE=<bundle_id> \
  NODE=<node_id> \
  SKIP_ENVIRONMENT_CHECK=true
```

---

## See Also

- [COMMAND-REFERENCE.md](COMMAND-REFERENCE.md) - Quick command reference
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Error codes and solutions
- [SCENARIOS.md](SCENARIOS.md) - Use case scenarios
- [ADR 0083](../../adr/0083-unified-node-initialization-contract.md) - Node initialization
- [ADR 0084](../../adr/0084-cross-platform-dev-plane-and-linux-deploy-plane.md) - Cross-platform runners
- [ADR 0085](../../adr/0085-deploy-bundle-and-runner-workspace-contract.md) - Deploy bundles
