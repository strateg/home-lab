# ADR 0054: Local Inputs Directory

- Status: Proposed
- Date: 2026-03-01
- Supersedes: 0054-separate-local-inputs-from-generated-outputs.md (draft, never accepted)

## Context

ADR 0050 established `generated/` as the canonical home for generated artifacts.
ADR 0052 established `dist/` as the assembled deploy package root.
ADR 0053 established explicit `native` and `dist` execution modes.

Both directories are intended to be rebuildable:
- `generated/` should be restorable from topology, generators, and canonical operator local inputs
- `dist/` should be restorable from canonical source roots, `generated/`, and canonical operator local inputs

This is a fundamental property of the build pipeline. Operators should not lose canonical operator-owned state when `generated/` or `dist/` is rebuilt.

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

```text
local/
├── terraform/
│   ├── mikrotik/terraform.tfvars
│   └── proxmox/terraform.tfvars
└── bootstrap/
    ├── srv-gamayun/answer.toml
    └── srv-orangepi5/cloud-init/user-data
```

Properties:
- structure mirrors package and execution layout
- gitignored
- operator-owned
- survives `rm -rf generated/ dist/`

### 3. Native And Dist Workflows Materialize From `local/`

The same canonical local inputs must feed both execution modes:

| Canonical source | Native target | Dist target |
|--------|--------|--------|
| `local/terraform/mikrotik/terraform.tfvars` | `generated/terraform/mikrotik/terraform.tfvars` | `dist/control/terraform/mikrotik/terraform.tfvars` |
| `local/terraform/proxmox/terraform.tfvars` | `generated/terraform/proxmox/terraform.tfvars` | `dist/control/terraform/proxmox/terraform.tfvars` |
| `local/bootstrap/srv-gamayun/answer.toml` | `generated/bootstrap/srv-gamayun/answer.toml` | `dist/bootstrap/srv-gamayun/answer.toml` |
| `local/bootstrap/srv-orangepi5/cloud-init/user-data` | `generated/bootstrap/srv-orangepi5/cloud-init/user-data` | `dist/bootstrap/srv-orangepi5/cloud-init/user-data` |

Preflight checks must validate `local/`, not stale execution copies.

### 4. Native Materialization May Be Integrated, Dist Materialization Remains Explicit

For operator UX:
- `native` workflow may integrate materialization into `make generate` or equivalent generation commands
- `dist` workflow may keep materialization as an explicit step because assembled packages are already treated as execution contracts

ADR 0054 does not require both modes to expose the same UX command. It requires both modes to use the same canonical source of truth: `local/`.

### 5. Preflight Fails Explicitly On Missing Local Inputs

If a required local input is missing, preflight must fail with a clear message:

```text
ERROR: local/terraform/proxmox/terraform.tfvars not found

Create it from example:
  cp generated/terraform/proxmox/terraform.tfvars.example local/terraform/proxmox/terraform.tfvars
  vim local/terraform/proxmox/terraform.tfvars
```

The system must not fall back to stale copies or empty defaults.

### 6. Three Directories, Three Rules

| Directory | Disposable | Recovery |
|-----------|------------|----------|
| `generated/` | Rebuildable | `make generate` plus `local/` |
| `dist/` | Rebuildable | `make assemble-dist` plus `local/` |
| `local/` | No | Operator creates manually |

This is the primary mental model for operator-owned inputs.

### 7. Cleanup Safety Improves After Local Input Migration

Once operator-edited local inputs move out of `generated/`, cleanup of canonical generated roots becomes safer and more deterministic.

ADR 0054 does not fully specify scratch/debug cleanup policy, but it does establish the prerequisite for that cleanup:
- `generated/` should stop being a home for canonical operator-edited files
- future cleanup work may then safely target generated roots without risking operator state loss

Known follow-up cleanup targets still exist and should be handled separately:
- `generated/migration/`
- `generated/validation/`
- `generated/terraform-mikrotik/`
- other scratch or legacy outputs

Before implementation is considered complete, each of these paths should get an explicit disposition:
- delete as obsolete legacy output
- archive for historical reference
- relocate to `.cache/` or another non-canonical preview/debug root

### 8. Ansible Secrets Remain Governed By ADR 0051

Ansible vault files (`.vault_pass`, `vault.yml`) remain in `ansible/` as defined by ADR 0051.

ADR 0054 covers Terraform and bootstrap inputs only.

### 9. Out Of Scope

ADR 0054 does not:
- change Ansible secret ownership from ADR 0051
- redesign package classes from ADR 0052
- fully define scratch/debug output cleanup policy
- introduce multi-environment local input layouts

## Consequences

### Positive

1. after ADR 0054 is implemented, rebuilding `generated/` and `dist/` no longer risks losing canonical operator-owned inputs
2. operator edits one place (`local/`)
3. simple mental model: three directories, three rules
4. `native` and `dist` stop inventing separate canonical local-input locations
5. preflight errors are actionable

### Negative

1. one new directory to understand
2. existing operator inputs must be migrated once
3. docs must be updated to reference `local/` instead of `generated/`
4. native and dist workflows still need explicit tooling changes to consume `local/`

## Migration Plan

### Phase 0: Inventory Current References

Identify all active code paths and docs that still instruct operators to edit `generated/...`.

Minimum expected areas:
- `deploy/phases/*.sh`
- `deploy/Makefile`
- bootstrap runbooks
- Terraform guides

### Phase 1: Introduce `local/` And Update Tooling

Create the canonical `local/` structure and update:
- native preflight
- dist preflight
- native materialization
- dist materialization

### Phase 2: Update Active Docs And Scripts

Active operator-facing docs must stop teaching direct edits under `generated/...`.

This phase must happen before old instructions can drift further into the workflow.

### Phase 3: Migrate Existing Files

For existing setups, move current local inputs into `local/`:

```text
mkdir -p local/terraform/mikrotik local/terraform/proxmox
mkdir -p local/bootstrap/srv-gamayun local/bootstrap/srv-orangepi5/cloud-init
mv generated/terraform/mikrotik/terraform.tfvars local/terraform/mikrotik/terraform.tfvars
mv generated/terraform/proxmox/terraform.tfvars local/terraform/proxmox/terraform.tfvars
mv generated/bootstrap/srv-gamayun/answer.toml local/bootstrap/srv-gamayun/answer.toml
mv generated/bootstrap/srv-orangepi5/cloud-init/user-data local/bootstrap/srv-orangepi5/cloud-init/user-data
```

Windows/PowerShell instructions should be provided in active docs when implementation starts.

### Phase 4: Remove Legacy References

After tooling and docs are switched:
- remove stale guidance that edits `generated/...`
- keep rollback behavior explicit where necessary
- ensure preflight never treats old execution copies as canonical

## References

- ADR 0050: Generated Directory Restructuring
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0052: Deploy Package Assembly Over Accepted Ansible Runtime
- ADR 0053: Optional Dist-First Deploy Cutover
