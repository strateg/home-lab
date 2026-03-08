# ADR 0056: Native Execution Workspace Outside Generated Roots

- Status: Accepted
- Date: 2026-03-01
- Harmonized With: ADR 0064 (Firmware + OS Two-Entity Model)

## Context

Harmonization note (2026-03-09):
- This ADR defines execution workspace boundaries and remains valid.
- For v5 topology semantics, software stack entities are modeled separately (`firmware`, `os`) and bound at instance level via `firmware_ref` and `os_refs[]` (ADR 0064).

ADR 0054 is accepted and implemented:
- canonical operator local inputs live under `local/`
- local inputs are materialized into execution roots
- `generated/` cleanup is now safe for managed roots

ADR 0055 is accepted and implemented:
- tracked Terraform exceptions live under `terraform-overrides/`
- native and `dist` execution both assemble:
  - generated baseline
  - tracked Terraform overrides
  - canonical local inputs

ADR 0053 is implemented in opt-in form:
- `native` remains the default operator workflow
- `dist` is a separate explicit execution mode

That leaves one architectural compromise in place:
- `native` execution still materializes local inputs and tracked Terraform overrides back into `generated/terraform/*`
- Proxmox and Orange Pi bootstrap execution copies are also materialized back into `generated/bootstrap/*`

This works, but it weakens the long-term model of `generated/` as a purely deterministic, disposable tree.

Today the repository effectively has two meanings for `generated/`:
1. canonical topology-derived outputs
2. native execution workspace after layering local and manual inputs

That dual role is the last remaining inconsistency after ADR 0054 and ADR 0055.

## Decision

### 1. Native Execution Must Move To `.work/native/`

`native` execution roots must no longer be assembled in-place under `generated/`.

Instead, native execution will use a dedicated workspace:

```text
.work/
└── native/
    ├── terraform/
    │   ├── mikrotik/
    │   └── proxmox/
    └── bootstrap/
        ├── srv-gamayun/
        └── srv-orangepi5/
```

This workspace is:
- disposable
- gitignored
- assembled from canonical sources
- never treated as source of truth

Deleting `.work/native/` must always be safe.

### 2. `generated/` Returns To A Pure Baseline Role

After ADR 0056:
- `generated/` contains only topology-derived generated outputs and generated examples
- `generated/` must not receive native execution copies
- `generated/` remains safe to delete and rebuild without also reconstructing native execution state

This restores a single meaning for `generated/`.

### 3. Native Terraform Execution Uses A Three-Layer Workspace

Native Terraform execution roots become:

```text
generated/terraform/<target>/              # generated baseline
        +
terraform-overrides/<target>/              # tracked exception layer
        +
local/terraform/<target>/terraform.tfvars  # canonical local input
        =
.work/native/terraform/<target>/           # native execution root
```

Operators still reason about the same three layers from ADR 0055.

ADR 0056 changes only the destination of the assembled native execution copy.

### 4. Native Bootstrap Execution Uses A Workspace Too

Native bootstrap materialization also moves out of `generated/`:

```text
generated/bootstrap/srv-gamayun/answer.toml.example
        +
local/bootstrap/srv-gamayun/answer.override.toml
        =
.work/native/bootstrap/srv-gamayun/answer.toml
```

and:

```text
generated/bootstrap/srv-orangepi5/cloud-init/user-data.example
        +
local/bootstrap/srv-orangepi5/cloud-init/user-data
        =
.work/native/bootstrap/srv-orangepi5/cloud-init/user-data
```

Generated bootstrap packages remain the canonical baseline and example source.

The execution-ready files used by operators must come from `.work/native/bootstrap/...`, not from mutating `generated/bootstrap/...`.

### 5. Native Deploy Tooling Must Execute From `.work/native/`

After ADR 0056:
- `deploy/phases/01-network.sh` runs Terraform from `.work/native/terraform/mikrotik/`
- `deploy/phases/02-compute.sh` runs Terraform from `.work/native/terraform/proxmox/`
- bootstrap operator docs and helper commands use `.work/native/bootstrap/...` as the execution copy

The operator workflow may still expose the same commands:
- `make generate`
- `make plan-mikrotik`
- `make plan-proxmox`
- `make deploy-all`

But those commands must assemble `.work/native/` before execution instead of mutating `generated/`.

Target behavior after cutover:

```text
make generate -> generate-all + assemble-native
```

One operator command may still remain responsible for:
- rebuilding deterministic baselines under `generated/`
- assembling `.work/native/`

That keeps the current operator ergonomics while changing the execution destination.

### 6. Native Materialization Becomes Native Assembly

The current notion of `materialize-native-inputs.py` is too narrow for the target architecture.

The follow-up implementation should shift from:
- "copy local inputs into generated roots"

to:
- "assemble native execution workspace from generated baseline, tracked overrides, and local inputs"

Temporary compatibility is acceptable:
- `make materialize-native-inputs` may remain as a compatibility alias during migration

Canonical target naming after cutover should become explicit:
- `make assemble-native`
- or an equivalent clearly named native workspace assembly command

The important requirement is that native assembly semantics become workspace assembly, not in-place mutation of `generated/`.

Repository UX should also gain a simple status command, for example:

```text
make status

Source roots:
  topology/              - layer definitions
  terraform-overrides/   - tracked exceptions
  local/                 - operator inputs

Workspaces:
  .work/native/          - native execution
  dist/                  - dist execution
```

This is not a source-of-truth command.
It is an operator onboarding and diagnostics helper.

### 7. Preflight Checks Validate Canonical Inputs, Not Workspace Residue

Preflight must continue to validate:
- canonical `local/`
- tracked `terraform-overrides/`
- generated baselines

It must not treat stale files under `.work/native/` as canonical.

Regeneration and explicit clean commands may delete `.work/native/` freely.

Native workspace assembly should be overwrite-in-place or full rebuild on demand.
Tooling must not trust stale `.work/native/` contents as canonical.

### 8. Dist And Native Stay Symmetric

After ADR 0056:
- `native` executes from `.work/native/`
- `dist` executes from `dist/`

Both become assembled execution views over canonical roots for Terraform and bootstrap flows, rather than one mode mutating the generated baseline while the other does not.

That is architecturally cleaner and easier to explain.

### 9. Out Of Scope

ADR 0056 does not:
- change `dist/` package structure from ADR 0052
- remove `native` mode in favor of `dist`
- move Ansible playbooks or roles
- redesign Ansible secret ownership from ADR 0051
- change the `local/` or `terraform-overrides/` ownership model from ADR 0054/0055

Ansible remains governed by ADR 0051:
- playbooks and roles remain under `ansible/`
- runtime inventory remains under `generated/ansible/runtime/production/`
- ADR 0056 does not move Ansible native execution into `.work/native/`

Rationale:
- Ansible does not currently use the same in-place mutable execution-root pattern as Terraform and bootstrap
- ADR 0056 addresses the specific inconsistency introduced by native execution mutating generated Terraform and bootstrap roots
- any future move for Ansible should be a separate decision with its own trade-offs

### 10. Terraform State Is Workspace-Local

Terraform state under `.work/native/terraform/<target>/` is workspace-local.

That means:
- it is disposable
- it may be removed by explicit native cleanup
- it must not be treated as canonical state for the repository

Operators must choose one of two models:
- use a remote backend for persistent state, or
- accept that cleaning `.work/native/` also removes local state

ADR 0056 does not require remote state immediately, but it makes the workspace-local nature of native state explicit.

### 11. Directory Role Matrix

After ADR 0056, the intended directory roles are:

| Directory | Tracked | Disposable | Purpose |
|-----------|---------|------------|---------|
| `topology/` | Yes | No | source of truth |
| `local/` | No | No | operator inputs |
| `terraform-overrides/` | Yes | No | tracked exceptions |
| `generated/` | No | Yes | pure baseline |
| `.work/native/` | No | Yes | native execution |
| `dist/` | No | Yes | dist execution |

Rule of thumb:
- three persistent roots: `topology/`, `local/`, `terraform-overrides/`
- three disposable roots: `generated/`, `.work/native/`, `dist/`

## Consequences

### Positive

1. `generated/` becomes a single-purpose deterministic tree again
2. native and dist execution models become symmetric
3. cleanup semantics become easier to reason about
4. stale execution copies stop polluting generated baselines
5. onboarding gets clearer: source roots, generated baselines, and execution workspaces are distinct

### Negative / Trade-offs

1. one more directory appears: `.work/native/`
2. native tooling must be updated to assemble a workspace before execution
3. some docs and scripts will need path changes
4. temporary dual-compatibility may be needed during migration

## References

- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0052: Deploy Package Assembly Over Accepted Ansible Runtime
- ADR 0053: Optional Dist-First Deploy Cutover
- ADR 0054: Local Inputs Directory
- ADR 0055: Manual Terraform Extension Layer
