# ADR 0055: Manual Terraform Extension Layer

- Status: Proposed
- Date: 2026-03-01

## Context

ADR 0052 established generated Terraform roots as canonical topology-derived outputs:
- `generated/terraform/mikrotik/`
- `generated/terraform/proxmox/`

ADR 0053 established explicit `native` and `dist` execution modes.

ADR 0054 separates operator local inputs from generated outputs:
- `terraform.tfvars` and bootstrap materialization belong in `local/`
- local inputs are untracked and environment-specific

That still leaves one legitimate operational need unresolved:
- topology and generators may not yet cover every Terraform use case
- operators may need a reviewable, tracked way to add exceptional `.tf` files
- those files must not be confused with untracked local inputs

The repository therefore needs an explicit exception layer for manual Terraform additions.

## Decision

### 1. Manual Terraform Extensions Are Separate From Local Inputs

Tracked manual Terraform additions are not operator local inputs.

They must not live under `local/`, and they must not be modeled as `terraform.tfvars`.

This ADR covers tracked manual Terraform extension files only.

### 2. Introduce `terraform-overrides/`

A dedicated tracked extension root is introduced:

```text
terraform-overrides/
├── mikrotik/
└── proxmox/
```

This root is:
- tracked in Git
- reviewable
- intended for rare exceptions
- separate from generated outputs
- separate from untracked local inputs

### 3. Extensions Layer On Top Of Generated Baselines

Terraform execution roots are assembled from three layers:

1. generated baseline from topology
2. tracked manual extensions from `terraform-overrides/`
3. untracked local inputs from `local/`

Conceptually:

```text
generated baseline + terraform-overrides + local inputs -> execution root
```

This applies to both `native` and `dist` execution modes.

### 4. Generated Files Remain Canonical For Topology-Owned Intent

`terraform-overrides/` is an exception layer, not a second equal source of truth.

Rules:
- generated Terraform remains canonical for topology-owned intent
- operators must not manually edit files under `generated/terraform/*`
- if an override becomes stable and generally applicable, it should be folded back into topology/generator logic

### 5. Extension Files Must Be Reviewable And Narrow In Scope

Allowed extension content:
- additional `.tf`
- additional `.tf.json`
- module calls
- extra resources
- data sources
- locals
- narrowly scoped outputs that support the manual extension
- extension-specific documentation such as `README.md`

Forbidden extension content:
- `terraform.tfvars`
- `.tfstate`
- `.terraform/`
- secrets embedded in tracked files
- copies of generated baseline files

### 6. Extensions Should Add Or Narrowly Refine, Not Replace The Baseline

The preferred use of the extension layer is additive.

Examples:
- add an exceptional resource not yet modeled in topology
- add a temporary compatibility resource for a provider gap
- add a targeted data source used by a manual workaround

The extension layer should not become the long-term home for:
- baseline network layout
- baseline VM/LXC definitions
- provider-wide defaults already owned by generated templates

### 7. Assembly Must Make Layering Explicit

When execution roots are assembled:
- generated baseline is copied first
- `terraform-overrides/<target>/` is layered next
- `local/terraform/<target>/terraform.tfvars` is materialized last

The assembler must not silently source manual `.tf` files from arbitrary locations.

### 8. Parity And Validation Must Include Extensions

Parity and validation logic must treat `terraform-overrides/` as part of the execution contract.

That means:
- execution parity must compare assembled roots, not generated baseline only
- validation must run against the fully layered execution root
- docs must explain that `generated/terraform/*` alone is not the whole story once overrides exist

### 9. Out Of Scope

ADR 0055 does not:
- redefine operator local-input handling from ADR 0054
- move Ansible manual extensions
- redesign topology ownership
- guarantee that every current manual exception is justified

## Consequences

### Positive

1. Terraform gains the same kind of controlled escape hatch that Ansible already has
2. generated baselines remain disposable and generator-owned
3. local secrets and tracked manual logic stop being mixed together
4. exceptional manual `.tf` files become reviewable and auditable

### Negative / Trade-offs

1. Terraform now has another layer to reason about
2. execution assembly becomes slightly more complex
3. there is risk that overrides become a dumping ground if not reviewed strictly

## Guardrails

1. every new override should explain why topology/generator cannot express the need yet
2. overrides should be revisited periodically and folded into generators when practical
3. overrides must never be used as a secret storage mechanism
4. adding an override is an exception, not the default implementation path

## References

- ADR 0052: Deploy Package Assembly Over Accepted Ansible Runtime
- ADR 0053: Optional Dist-First Deploy Cutover
- ADR 0054: Local Inputs Directory
- `generated/terraform/`
