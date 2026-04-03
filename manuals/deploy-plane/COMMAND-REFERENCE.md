# Deploy Plane Command Reference

Quick reference for all deploy plane commands.

---

## Bundle Commands

### Create Bundle

```bash
task bundle:create
task bundle:create -- INJECT_SECRETS=true
task bundle:create -- GENERATED_ROOT=/path SECRETS_ROOT=/path
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `INJECT_SECRETS` | Include decrypted secrets in bundle | `false` |
| `GENERATED_ROOT` | Path to generated artifacts | `generated/<project>` |
| `SECRETS_ROOT` | Path to secrets directory | `projects/<project>/secrets` |
| `BUNDLES_ROOT` | Custom bundles directory | `.work/deploy/bundles` |

### List Bundles

```bash
task bundle:list
task bundle:list -- BUNDLES_ROOT=/custom/path
```

### Inspect Bundle

```bash
task bundle:inspect -- BUNDLE=b-123456
task bundle:inspect -- BUNDLE=b-123456 SKIP_CHECKSUMS=true
task bundle:inspect -- BUNDLE=/absolute/path/to/bundle
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `BUNDLE` | Bundle ID or absolute path | **required** |
| `SKIP_CHECKSUMS` | Skip checksum verification | `false` |

### Delete Bundle

```bash
task bundle:delete -- BUNDLE=b-123456
```

---

## Init-Node Commands

### Status

```bash
task deploy:init-status
```

### Plan (Single Node)

```bash
task deploy:init-node-plan -- BUNDLE=b-123 NODE=rtr-mikrotik-chateau
```

### Plan (All Pending)

```bash
task deploy:init-all-pending-plan -- BUNDLE=b-123
```

### Run (Single Node)

```bash
task deploy:init-node-run -- BUNDLE=b-123 NODE=rtr-mikrotik-chateau
```

### Run (All Pending)

```bash
task deploy:init-all-pending-run -- BUNDLE=b-123
```

### Init-Node Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `BUNDLE` | Bundle ID or path | **required** |
| `NODE` | Node ID to process | required for single-node |
| `DEPLOY_RUNNER` | Runner override | auto-detect |
| `VERIFY_ONLY` | Only run handover checks | `false` |
| `FORCE` | Override state guards | `false` |
| `IMPORT_EXISTING` | Mark as imported | `false` |
| `RESET` | Reset to pending | `false` |
| `CONFIRM_RESET` | Required with RESET | `false` |
| `ACKNOWLEDGE_DRIFT` | Accept topology drift | `false` |
| `SKIP_ENVIRONMENT_CHECK` | Skip env validation | `false` |

---

## Service Chain Commands

### Dry Run

```bash
# Without bundle
task deploy:service-chain-evidence-dry

# With bundle (strict mode)
task deploy:service-chain-evidence-dry-bundle -- BUNDLE=b-123
```

### Maintenance Check

```bash
# Without bundle
task deploy:service-chain-evidence-check

# With bundle (strict mode)
task deploy:service-chain-evidence-check-bundle -- BUNDLE=b-123
```

### Maintenance Apply

```bash
# Without bundle
task deploy:service-chain-evidence-apply -- ALLOW_APPLY=YES

# With bundle (strict mode)
task deploy:service-chain-evidence-apply-bundle -- ALLOW_APPLY=YES BUNDLE=b-123
```

### Service Chain Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `BUNDLE` | Bundle ID (required for *-bundle) | - |
| `ALLOW_APPLY` | Must be `YES` for apply | **required for apply** |
| `DEPLOY_RUNNER` | Runner override | auto-detect |
| `CONTINUE_ON_FAILURE` | Don't stop on error | `false` |
| `ANSIBLE_VIA_WSL` | Force Ansible via WSL | `false` |
| `TERRAFORM_AUTO_APPROVE` | Skip Terraform confirm | `false` |
| `INJECT_SECRETS` | Use bundle secrets | `false` |
| `PROXMOX_BACKEND_CONFIG` | Terraform backend file | - |
| `MIKROTIK_BACKEND_CONFIG` | Terraform backend file | - |
| `PROXMOX_VAR_FILE` | Terraform var file | - |
| `MIKROTIK_VAR_FILE` | Terraform var file | - |

---

## Docker Toolchain Commands

### Build Toolchain Image

```bash
task deploy:docker-toolchain-build
task deploy:docker-toolchain-build -- DOCKER_IMAGE=my-toolchain:v1
```

### Smoke Test

```bash
task deploy:docker-toolchain-smoke
task deploy:docker-toolchain-smoke -- DOCKER_IMAGE=my-toolchain:v1
```

---

## Python CLI Direct Usage

### bundle.py

```bash
# Create
python scripts/orchestration/deploy/bundle.py create \
  --repo-root . \
  --project-id home-lab \
  --inject-secrets \
  --secrets-root projects/home-lab/secrets

# List
python scripts/orchestration/deploy/bundle.py list --repo-root .

# Inspect
python scripts/orchestration/deploy/bundle.py inspect \
  --repo-root . \
  --bundle b-123456 \
  --skip-checksums

# Delete
python scripts/orchestration/deploy/bundle.py delete \
  --repo-root . \
  --bundle b-123456
```

### init-node.py

```bash
# Status
python scripts/orchestration/deploy/init-node.py \
  --repo-root . \
  --project-id home-lab \
  --status

# Plan single node
python scripts/orchestration/deploy/init-node.py \
  --repo-root . \
  --project-id home-lab \
  --bundle b-123 \
  --node rtr-mikrotik-chateau \
  --plan-only

# Execute
python scripts/orchestration/deploy/init-node.py \
  --repo-root . \
  --project-id home-lab \
  --bundle b-123 \
  --node rtr-mikrotik-chateau \
  --deploy-runner wsl

# All pending with verify
python scripts/orchestration/deploy/init-node.py \
  --repo-root . \
  --project-id home-lab \
  --bundle b-123 \
  --all-pending \
  --verify-only
```

---

## Runner Selection

### Auto-Detection Priority

1. Check deploy-profile.yaml `default_runner`
2. On Windows: Use WSL
3. On Linux: Use Native
4. Fallback: Error

### Override Runner

```bash
# Task command
task deploy:init-node-run -- BUNDLE=b-123 NODE=node1 DEPLOY_RUNNER=docker

# Python CLI
python scripts/orchestration/deploy/init-node.py \
  --bundle b-123 --node node1 --deploy-runner docker
```

### Available Runners

| Runner | Platform | Command |
|--------|----------|---------|
| `native` | Linux | Direct execution |
| `wsl` | Windows | `wsl -d Ubuntu -- <cmd>` |
| `docker` | Any | `docker run --rm <image> <cmd>` |
| `remote` | Any | `ssh user@host <cmd>` |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PROJECT_ID` | Project identifier (default: `home-lab`) |
| `V5_SECRETS_MODE` | Secrets handling (`passthrough`, `decrypt`) |
| `DEPLOY_RUNNER` | Runner preference override |

---

## File Paths

| Path | Purpose |
|------|---------|
| `.work/deploy/bundles/` | Deploy bundles |
| `.work/deploy-state/<project>/nodes/` | Init state |
| `.work/deploy-state/<project>/logs/` | Audit logs |
| `projects/<project>/deploy/deploy-profile.yaml` | Profile |
| `generated/<project>/` | Generated artifacts |
| `generated/<project>/bootstrap/` | Bootstrap artifacts |

---

## Output Formats

All commands output JSON for machine parsing:

```bash
# Parse with jq
task bundle:list | jq '.bundles[0].bundle_id'

# Get node status
task deploy:init-status | jq '.by_status'
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Validation/argument error |
