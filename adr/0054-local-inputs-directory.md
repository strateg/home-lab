# ADR 0054: Local Inputs Directory

- Status: Accepted (secret-bearing inputs superseded by ADR 0072)
- Date: 2026-03-01
- Supersedes: 0054-separate-local-inputs-from-generated-outputs.md (draft, never accepted)
- Harmonized With: ADR 0064 (Firmware + OS Two-Entity Model)
- Partially Superseded By: ADR 0072 (Unified Secrets Management with SOPS + age)

## Context

Harmonization note (2026-03-09):
- This ADR defines operator local-input placement and remains valid.
- In v5 model terms, deployable device software stack is represented by firmware/OS instance references (`firmware_ref`, `os_refs[]`) according to ADR 0064.

ADR 0050 established `generated/` as the canonical home for generated artifacts.
ADR 0052 established `dist/` as the assembled deploy package root.
ADR 0053 historically introduced explicit `native` and `dist` execution modes.
Current deploy execution contract is governed by ADR 0085 bundle-based model.

Manual tracked Terraform extensions are a separate concern from operator local inputs.
That exception layer is decided by ADR 0055 and is intentionally not modeled through `local/`.

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

This ADR covers only operator local inputs such as:
- `terraform.tfvars`
- `answer.toml` overrides
- `user-data`

It does not define tracked manual `.tf` extension files.

### 2. Introduce `local/` Directory

A dedicated `local/` directory holds all operator-edited inputs:

```text
local/
├── terraform/
│   ├── mikrotik/terraform.tfvars
│   └── proxmox/terraform.tfvars
└── bootstrap/
    ├── srv-gamayun/answer.override.toml
    └── srv-orangepi5/cloud-init/user-data
```

Properties:
- structure mirrors package and execution layout
- gitignored
- operator-owned
- survives `rm -rf generated/ dist/`
- contains local inputs only, not tracked extension code

### 3. Native And Dist Workflows Materialize From `local/`

The same canonical local inputs must feed both execution modes:

| Canonical source | Native target | Dist target |
|--------|--------|--------|
| `local/terraform/mikrotik/terraform.tfvars` | `generated/terraform/mikrotik/terraform.tfvars` | `dist/control/terraform/mikrotik/terraform.tfvars` |
| `local/terraform/proxmox/terraform.tfvars` | `generated/terraform/proxmox/terraform.tfvars` | `dist/control/terraform/proxmox/terraform.tfvars` |
| `local/bootstrap/srv-gamayun/answer.override.toml` | `generated/bootstrap/srv-gamayun/answer.toml` | `dist/bootstrap/srv-gamayun/answer.toml` |
| `local/bootstrap/srv-orangepi5/cloud-init/user-data` | `generated/bootstrap/srv-orangepi5/cloud-init/user-data` | `dist/bootstrap/srv-orangepi5/cloud-init/user-data` |

Preflight checks must validate `local/`, not stale execution copies.

Tracked manual Terraform extensions, when present, are layered separately and are not sourced from `local/`.

For `srv-gamayun`, the canonical generated baseline remains:
- `generated/bootstrap/srv-gamayun/answer.toml.example`

The local file is not a full replacement of the generated answer.
It is an override input used to materialize the final execution copy.

### 4. Native Materialization May Be Integrated, Dist Materialization Remains Explicit

For operator UX:
- `native` workflow may integrate materialization into `make generate` or equivalent generation commands
- `dist` workflow may keep materialization as an explicit step because assembled packages are already treated as execution contracts

ADR 0054 does not require both modes to expose the same UX command. It requires both modes to use the same canonical source of truth: `local/`.

### 5. `answer.toml` Is A Special Case: Generated Baseline Plus Local Override

Unlike `terraform.tfvars`, `answer.toml` is mostly topology-derived and should not become a fully operator-owned canonical file.

For Proxmox bootstrap:

1. the generated baseline remains `generated/bootstrap/srv-gamayun/answer.toml.example`
2. the canonical local file is `local/bootstrap/srv-gamayun/answer.override.toml`
3. tooling materializes the final `answer.toml` for execution from:
   - generated baseline
   - local override

This preserves topology ownership for the baseline while still allowing required local customization.

The intended use of `answer.override.toml` is narrow. It should only cover fields that genuinely must remain operator-local, such as:
- root password hash
- other explicitly allowlisted bootstrap-time overrides, if such fields are introduced intentionally

Operator workflows must not treat `answer.toml` as a long-lived hand-maintained source file.

#### Override Policy

`answer.override.toml` must follow an explicit allowlist-based merge policy.

Rules:
- the generated baseline remains authoritative for topology-owned fields
- the override file may change only explicitly allowlisted keys
- non-allowlisted keys in the override must fail validation
- the materializer must generate a final `answer.toml` from baseline plus allowed overrides, not accept a full replacement file

Initial allowlist:
- `global.root_password`

Any additional allowed keys must be added intentionally and documented in the ADR or follow-up implementation docs.

### 6. Preflight Fails Explicitly On Missing Local Inputs

If a required local input is missing, preflight must fail with a clear message:

```text
ERROR: local/terraform/proxmox/terraform.tfvars not found

Create it from example:
  cp generated/terraform/proxmox/terraform.tfvars.example local/terraform/proxmox/terraform.tfvars
  vim local/terraform/proxmox/terraform.tfvars
```

The system must not fall back to stale copies or empty defaults.

For Proxmox bootstrap, preflight should guide the operator differently:

```text
ERROR: local/bootstrap/srv-gamayun/answer.override.toml not found

Create it from the generated baseline:
  cp generated/bootstrap/srv-gamayun/answer.toml.example local/bootstrap/srv-gamayun/answer.override.toml
  vim local/bootstrap/srv-gamayun/answer.override.toml
```

### 7. Three Directories, Three Rules

| Directory | Disposable | Recovery |
|-----------|------------|----------|
| `generated/` | Rebuildable | `make generate` plus `local/` |
| `dist/` | Rebuildable | `make assemble-dist` plus `local/` |
| `local/` | No | Operator creates manually |

This is the primary mental model for operator-owned inputs.

### 8. Dist Materialization Uses The Same Canonical Local Source

`dist` materialization must source canonical operator inputs from `local/`, not from prior native execution copies.

That keeps `native` and `dist` aligned on one source of truth even though their operator UX remains different:
- `native` may integrate materialization into generation-oriented commands
- `dist` remains an explicit assembly-and-materialization workflow

### 9. Cleanup Safety Improves After Local Input Migration

Once operator-edited local inputs move out of `generated/`, cleanup of canonical generated roots becomes safer and more deterministic.

ADR 0054 does not fully specify scratch/debug cleanup policy, but it does establish the prerequisite for that cleanup:
- `generated/` should stop being a home for canonical operator-edited files
- future cleanup work may then safely target generated roots without risking operator state loss

Tracked manual Terraform extensions do not weaken this cleanup boundary as long as they remain outside `generated/`.

Known follow-up cleanup targets still exist and should be handled separately:
- `generated/validation/`
- `generated/terraform-mikrotik/`
- other scratch or legacy outputs

Before implementation is considered complete, each of these paths should get an explicit disposition:
- delete as obsolete legacy output
- archive for historical reference
- relocate to `.cache/` or another non-canonical preview/debug root

### 10. `manual-scripts/bare-metal/` Remains A Source-Assets Layer

`manual-scripts/bare-metal/` remains the home of reusable bootstrap scripts and source assets.

It must not become the canonical home of operator-local Proxmox `answer.toml` state.

That would mix:
- reusable source assets
- generated baseline material
- operator-local runtime input

ADR 0054 keeps those concerns separate.

### 11. Ansible Secrets Remain Governed By ADR 0051

Ansible vault files (`.vault_pass`, `vault.yml`) remain in `ansible/` as defined by ADR 0051.

ADR 0054 covers Terraform and bootstrap inputs only.

### 12. Out Of Scope

ADR 0054 does not:
- change Ansible secret ownership from ADR 0051
- redesign package classes from ADR 0052
- fully define scratch/debug output cleanup policy
- introduce multi-environment local input layouts
- define tracked manual Terraform extension layers

## Consequences

### Positive

1. after ADR 0054 is implemented, rebuilding `generated/` and `dist/` no longer risks losing canonical operator-owned inputs
2. operator edits one place (`local/`)
3. simple mental model: three directories, three rules
4. `native` and `dist` stop inventing separate canonical local-input locations
5. preflight errors are actionable
6. Proxmox bootstrap keeps topology ownership for baseline answer structure instead of drifting to a fully manual file

### Negative

1. one new directory to understand
2. existing operator inputs must be migrated once
3. docs must be updated to reference `local/` instead of `generated/`
4. native and dist workflows need to keep their materialization logic aligned on `local/`
5. `answer.toml` materialization is slightly more complex than plain file copying

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

For Proxmox bootstrap, implement generated-baseline-plus-override materialization rather than direct file copying.

That implementation must also validate:
- only allowlisted keys are present in `answer.override.toml`
- the final `answer.toml` is always produced from baseline plus override, never accepted as a standalone local source file

Do not use this phase to introduce tracked manual Terraform exceptions.
Those belong to the separate extension contract from ADR 0055.

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
mv generated/bootstrap/srv-orangepi5/cloud-init/user-data local/bootstrap/srv-orangepi5/cloud-init/user-data
```

For `srv-gamayun`, do not migrate the full `answer.toml` as the new canonical local file.
Instead:

```text
mkdir -p local/bootstrap/srv-gamayun
cp generated/bootstrap/srv-gamayun/answer.toml local/bootstrap/srv-gamayun/answer.override.toml
```

Then reduce that file to the intended local override surface during implementation.

Windows/PowerShell instructions should be provided in active docs when implementation starts.

### Phase 4: Remove Legacy References

After tooling and docs are switched:
- remove stale guidance that edits `generated/...`
- keep rollback behavior explicit where necessary
- ensure preflight never treats old execution copies as canonical

### Phase 5: Post-Acceptance Documentation Alignment

After ADR 0054 is accepted and implementation is stable:
- update `CLAUDE.md` directory structure to include `local/`
- update operator onboarding docs to explain that `local/` is the canonical home of untracked operator inputs
- keep this documentation focused on local inputs only, not tracked Terraform overrides

## References

- ADR 0050: Generated Directory Restructuring
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0052: Deploy Package Assembly Over Accepted Ansible Runtime
- ADR 0053: Optional Dist-First Deploy Cutover (superseded by ADR 0085)
- ADR 0085: Deploy Bundle and Runner Workspace Contract
- ADR 0055: Manual Terraform Extension Layer
