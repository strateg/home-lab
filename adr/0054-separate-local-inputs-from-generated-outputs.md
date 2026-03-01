# ADR 0054: Separate Local Operator Inputs from Generated Outputs

- Status: Proposed
- Date: 2026-03-01

## Context

ADR 0050 established `generated/` as the canonical home for generated artifacts.

ADR 0051 established deterministic Ansible runtime assembly under `generated/ansible/runtime/production/`.

ADR 0052 established deploy package assembly under `dist/`.

ADR 0053 established explicit `native` and `dist` execution modes and made package manifests part of the execution contract.

Despite that progress, the current repository still stores two fundamentally different classes of files under `generated/`:

1. reproducible generated outputs, such as:
   - `generated/ansible/inventory/production/`
   - `generated/ansible/runtime/production/`
   - `generated/docs/`
   - `generated/bootstrap/*/*.example`
   - `generated/terraform/*/*.tf`
2. operator-edited local inputs, such as:
   - `generated/terraform/mikrotik/terraform.tfvars`
   - `generated/terraform/proxmox/terraform.tfvars`
   - `generated/bootstrap/srv-gamayun/answer.toml`
   - potentially `generated/bootstrap/srv-orangepi5/cloud-init/user-data`

This creates several problems:

1. `generated/` is no longer safely disposable, because cleaning it may delete real operator inputs needed for deploy.
2. regeneration cannot safely perform aggressive cleanup, so stale files and legacy roots accumulate.
3. the same directory mixes deterministic outputs, local secrets, local non-secret inputs, and scratch/debug leftovers.
4. `native` and `dist` workflows use different materialization semantics even though both need the same class of operator-supplied inputs.

The current model therefore weakens all of the following:
- cleanup safety
- regeneration determinism
- deploy reproducibility
- operator ergonomics

The repository also lacks an explicit taxonomy for what kinds of data may live under `generated/`.
That ambiguity makes it difficult to answer basic operational questions such as:
- what may be deleted before regeneration
- what must be relocated before cleanup becomes safe
- which files are merely materialized copies versus canonical operator-owned inputs

## Decision

### 1. Operator-Edited Local Inputs Must Not Live Under `generated/`

Files that are intentionally created, edited, or owned by the operator must not use `generated/` as their canonical storage location.

This applies to:
- Terraform `terraform.tfvars`
- Proxmox bootstrap `answer.toml`
- Orange Pi cloud-init `user-data`
- any future operator-authored bootstrap answers, secrets, or local overrides that are not topology-generated

`generated/` must be reserved for deterministic outputs and release-safe examples.

### 2. Introduce A Dedicated Local-Only Root

A dedicated local-only root must be introduced for operator materialized inputs.

The preferred root is:

```text
.local/
```

Example target layout:

```text
.local/
├── terraform/
│   ├── mikrotik/terraform.tfvars
│   └── proxmox/terraform.tfvars
└── bootstrap/
    ├── srv-gamayun/answer.toml
    └── srv-orangepi5/cloud-init/user-data
```

This root is:
- local-only
- ignored by Git
- operator-owned
- outside the deterministic generation boundary

`.local/` is not a reviewable configuration layer and must not be used for tracked defaults.

Reviewable non-secret defaults must remain in Git as one of:
- `*.example` files under generated package roots
- dedicated tracked defaults documentation
- an optional future tracked non-secret defaults layer, if one is introduced explicitly

### 3. `generated/` Must Contain Only Generated Outputs And Release-Safe Examples

After migration, `generated/` may contain:
- topology-derived outputs
- assembled runtime outputs
- release-safe package payloads
- example files such as `terraform.tfvars.example`, `answer.toml.example`, `user-data.example`

`generated/` must not be the canonical home of editable local inputs.

Examples remain the canonical reviewable starting point for operator-authored local materialization.

### 4. Native And Dist Workflows Must Materialize From The Same Local-Input Source

The repository must use one consistent materialization model:

1. operator edits canonical local inputs under `.local/`
2. tooling copies those inputs into execution roots as needed

This applies to both execution modes:
- `native`: materialize `.local/...` into `generated/...`
- `dist`: materialize `.local/...` into `dist/...`

The repository must not keep two independent canonical local-input locations.

### 5. Regeneration Must Be Allowed To Clean Managed `generated/` Outputs Aggressively

Once canonical operator inputs are moved out of `generated/`, regeneration may clean managed `generated/` subtrees before rebuilding them.

This is a primary goal of the refactor.

However, cleanup must still be scoped to managed outputs and must not delete unrelated ad hoc work products unless those are also moved out of `generated/`.

### 6. Generated Output Taxonomy Must Be Explicit

Files and directories related to generation must be classified into exactly one of these categories:

1. `managed-generated`
2. `materialized-local`
3. `scratch`
4. `legacy`

Definitions:

- `managed-generated`
  Deterministic outputs owned by generators and safe to delete before regeneration.
- `materialized-local`
  Non-canonical execution copies produced from `.local/` for `native` or `dist` workflows.
- `scratch`
  Temporary debug, validation, preview, or comparison outputs that must not share the canonical `generated/` contract.
- `legacy`
  Deprecated paths kept only during migration or pending archival/removal.

After ADR 0054 is implemented:
- `generated/` should contain only `managed-generated`
- `materialized-local` may exist transiently inside execution roots but must never be treated as canonical
- `scratch` and `legacy` outputs must be relocated or removed

### 7. Managed Cleanup Contract Must Be Explicit

Managed cleanup is a specific pipeline step and is not equivalent to generic garbage collection.

Managed cleanup must obey these rules:

1. it runs before regeneration
2. it deletes only canonical `managed-generated` roots
3. it never touches `.local/`
4. it may delete stale `materialized-local` copies from execution roots, because those copies are non-canonical
5. it must not silently preserve unknown files under managed roots

This means cleanup should fail closed against unknown state inside managed roots only after the repository no longer depends on mixed-use directories there.

### 8. Canonical Managed Roots Must Be Enumerated

After refactor, the canonical managed roots under `generated/` should be:

- `generated/ansible/`
- `generated/docs/`
- `generated/bootstrap/`
- `generated/terraform/`

These roots are the intended scope of pre-regeneration cleanup.

### 9. Scratch And Legacy Roots Must Be Enumerated And Removed From The Canonical Contract

The following paths are not part of the canonical managed `generated/` contract and must be relocated, archived, or deleted:

- `generated/.fixture-matrix-debug/`
- `generated/validation/`
- `generated/tmp-answer.toml`
- `generated/migration/`
- `generated/terraform-mikrotik/`
- root-level legacy files directly under `generated/terraform/`, where they duplicate scoped roots

They must not block the eventual ability to clean canonical managed roots before regeneration.

### 10. Scratch, Validation, And Debug Outputs Must Not Share The Canonical `generated/` Root

Temporary or comparison-oriented outputs such as:
- fixture debug trees
- validation-only outputs
- migration previews
- temporary generated answer files

should move to:
- `.cache/`
- `tmp/`
- auto-cleaned temporary directories

They should not remain mixed into the main `generated/` tree.

### 11. Materialized Copies Must Not Become Hidden State

Materialization from `.local/` into execution roots is an execution convenience, not a storage contract.

Rules:

1. `.local/` is the only canonical source of operator-edited local inputs covered by ADR 0054
2. execution copies in `generated/` or `dist/` are disposable
3. if a canonical `.local/...` file is missing, preflight must fail explicitly
4. the system must not treat a stale copy under `generated/` as an acceptable substitute for a missing `.local/...` file

### 12. Preflight Checks Must Validate `.local/` Ownership Explicitly

Execution preflight must validate canonical local inputs from `.local/`, not from incidental copies inside execution roots.

Required-input checks should answer:
- which canonical `.local` file is missing
- which execution root it would be materialized into

This makes operator workflow clearer and reduces hidden state.

### 13. Out Of Scope

ADR 0054 does not:
- redesign package classes from ADR 0052
- remove `native` mode from ADR 0053
- change Ansible secret ownership from ADR 0051
- move Ansible `.vault_pass` or `ansible/group_vars/all/vault.yml` into `generated/`

Ansible local-secret handling remains governed by ADR 0051 and ADR 0053.

## Consequences

### Positive

1. `generated/` becomes safely disposable again
2. regeneration can clean managed outputs without risking operator data loss
3. stale files and legacy generated roots become easier to detect and remove
4. `native` and `dist` workflows share one local-input contract
5. operator intent becomes explicit: generated examples live in `generated/`, editable inputs live in `.local/`
6. cleanup semantics become testable because managed roots and non-managed roots are explicitly separated

### Negative / Trade-offs

1. there is one more top-level working directory for operators to understand
2. native deploy now depends on a materialization step instead of direct in-place editing under `generated/`
3. docs and runbooks must be updated to stop instructing operators to edit files under `generated/`
4. some helper scripts and preflight tooling must be rewritten to treat `.local/` as canonical
5. scratch and preview tooling will need relocation out of familiar ad hoc `generated/` paths

## Alternatives Considered

### Alternative A: Clean The Entire `generated/` Tree On Every Run

Rejected.

This is unsafe while operator-edited files still live under `generated/`.

### Alternative B: Keep Local Inputs In `generated/` But Add Preserve Lists

Rejected as a long-term model.

Preserve lists reduce accidental deletion, but they keep `generated/` semantically mixed and complicate cleanup logic indefinitely.

### Alternative C: Store Local Inputs Directly Under `dist/`

Rejected.

`dist/` is an assembled execution view, not the canonical place to author or store operator-owned local inputs.

### Alternative D: Store Local Inputs Under Existing Source Roots

Partially acceptable for Ansible secrets, already governed by ADR 0051.

Rejected for Terraform and bootstrap inputs because those files conceptually belong to operator materialization, not to canonical source or generated output.

### Alternative E: Store `.local/` In Git

Rejected.

`.local/` is intended for environment-specific operator materialization and may contain secrets or temporary execution-specific values.

Tracked reviewable artifacts should remain `*.example` files or an explicitly designed non-secret defaults layer, not `.local/` itself.

## References

- ADR 0050: Generated Directory Restructuring
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0052: Deploy Package Assembly Over Accepted Ansible Runtime
- ADR 0053: Optional Dist-First Deploy Cutover
- `topology-tools/regenerate-all.py`
- `topology-tools/materialize-dist-inputs.py`
- `deploy/Makefile`
