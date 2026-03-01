# ADR 0054: Local Inputs Directory

- Status: Proposed
- Date: 2026-03-01
- Supersedes: 0054-separate-local-inputs-from-generated-outputs.md (draft, never accepted)

## Context

ADR 0050 established `generated/` as the canonical home for generated artifacts.
ADR 0052 established `dist/` as the assembled deploy package root.

Both directories are **disposable by design**:
- `rm -rf generated/` followed by `make generate` must restore full state
- `rm -rf dist/` followed by `make assemble-dist` must restore full state

This is a fundamental property of the build pipeline. Operators may delete these directories at any time without breaking the workflow.

However, the current repository stores operator-edited local inputs inside `generated/`:
- `generated/terraform/mikrotik/terraform.tfvars`
- `generated/terraform/proxmox/terraform.tfvars`
- `generated/bootstrap/srv-gamayun/answer.toml`
- `generated/bootstrap/srv-orangepi5/cloud-init/user-data`

This violates the disposability rule: deleting `generated/` loses operator inputs that cannot be regenerated.

## Decision

### 1. Operator Inputs Must Live Outside Disposable Roots

Operator-edited inputs must not live in `generated/` or `dist/`.

These directories must remain safely deletable at any time.

### 2. Introduce `local/` Directory

A dedicated `local/` directory holds all operator-edited inputs:

```
local/
├── mikrotik.tfvars
├── proxmox.tfvars
├── gamayun.toml
└── orangepi5-user-data
```

Properties:
- flat structure (no nesting)
- gitignored
- operator-owned
- survives `rm -rf generated/ dist/`

### 3. Generation Copies Local Inputs Into Execution Roots

`make generate` (via `regenerate-all.py`) copies local inputs into execution roots:

| Source | Target |
|--------|--------|
| `local/mikrotik.tfvars` | `generated/terraform/mikrotik/terraform.tfvars` |
| `local/proxmox.tfvars` | `generated/terraform/proxmox/terraform.tfvars` |
| `local/gamayun.toml` | `generated/bootstrap/srv-gamayun/answer.toml` |
| `local/orangepi5-user-data` | `generated/bootstrap/srv-orangepi5/cloud-init/user-data` |

This is not a separate "materialization" step. It is part of the standard generation workflow.

### 4. Preflight Fails Explicitly On Missing Local Inputs

If a required local input is missing, preflight must fail with a clear message:

```
ERROR: local/proxmox.tfvars not found

Create it from example:
  cp generated/terraform/proxmox/terraform.tfvars.example local/proxmox.tfvars
  vim local/proxmox.tfvars
```

The system must not fall back to stale copies or empty defaults.

### 5. Three Directories, Three Rules

| Directory | Disposable | Recovery |
|-----------|------------|----------|
| `generated/` | Yes | `make generate` |
| `dist/` | Yes | `make assemble-dist` |
| `local/` | No | Operator creates manually |

This is the complete mental model. No additional taxonomy required.

### 6. Ansible Secrets Remain Governed By ADR 0051

Ansible vault files (`.vault_pass`, `vault.yml`) remain in `ansible/` as defined by ADR 0051.

ADR 0054 covers Terraform and bootstrap inputs only.

### 7. Out Of Scope

ADR 0054 does not:
- change Ansible secret ownership from ADR 0051
- redesign package classes from ADR 0052
- address scratch/debug output cleanup (separate concern)
- introduce multi-environment local input layouts

## Consequences

### Positive

1. `rm -rf generated/ dist/` is always safe
2. operator edits one place (`local/`)
3. simple mental model: three directories, three rules
4. no separate materialization step in workflow
5. preflight errors are actionable

### Negative

1. one new directory to understand
2. existing operator inputs must be migrated once
3. docs must be updated to reference `local/` instead of `generated/`

## Migration

One-time migration for existing setups:

```bash
mkdir -p local
mv generated/terraform/mikrotik/terraform.tfvars local/mikrotik.tfvars
mv generated/terraform/proxmox/terraform.tfvars local/proxmox.tfvars
mv generated/bootstrap/srv-gamayun/answer.toml local/gamayun.toml
mv generated/bootstrap/srv-orangepi5/cloud-init/user-data local/orangepi5-user-data
```

## References

- ADR 0050: Generated Directory Restructuring
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0052: Deploy Package Assembly Over Accepted Ansible Runtime
- ADR 0053: Optional Dist-First Deploy Cutover
