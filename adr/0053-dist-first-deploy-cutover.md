# ADR 0053: Optional Dist-First Deploy Cutover

- Status: Superseded
- Date: 2026-03-01
- Superseded By: ADR 0085

## Supersession Notice (2026-04-03)

This ADR is superseded by ADR 0085 (`Deploy Bundle and Runner Workspace Contract`).

Reason:

1. ADR 0053 modeled deploy cutover as `native` vs `dist` execution roots.
2. ADR 0085 established a stronger, backend-neutral contract where deploy execution consumes immutable bundles (`.work/deploy/bundles/<bundle_id>`) and runner workspaces.
3. Bundle-based execution replaces `dist` as the primary deploy execution boundary while preserving inspectable generated artifacts.

Therefore ADR 0053 is retained for historical context only and is no longer an active decision target.

## Context

ADR 0051 is accepted and implemented:
- Ansible runtime inventory is assembled deterministically under `generated/ansible/runtime/production/`
- deploy entrypoints already use the accepted runtime contract

ADR 0052 is accepted and implemented:
- deploy-ready packages are assembled under `dist/`
- `dist/` manifests and package classes are validated locally and in CI
- bootstrap packages for `rtr-mikrotik-chateau`, `srv-gamayun`, and `srv-orangepi5` are explicit package roots

That leaves one remaining architectural choice unresolved:
- operators still deploy primarily from native roots such as `generated/terraform/*` and `ansible/`
- `dist/` is assembled and validated, but it is not yet the primary execution root for deploy commands

This is intentionally unresolved by ADR 0052. Moving the operator workflow from native roots to `dist/` changes runtime execution semantics and should not be bundled with package assembly itself.

## Decision

### 1. ADR 0053 Depends On Accepted ADR 0051 And ADR 0052

ADR 0053 does not revisit:
- Ansible runtime ownership and secret boundaries from ADR 0051
- deploy package assembly and validation contracts from ADR 0052

It only decides whether deploy commands should execute from `dist/`.

### 2. Deploy Execution Modes Must Be Explicit

The repository must support two explicit execution modes:
- `native`
- `dist`

`native` means deploy commands use canonical source and generated roots directly.

`dist` means deploy commands execute from assembled packages under `dist/`.

The two modes must not be mixed implicitly inside one deploy command.

### 3. Dist-First Cutover Must Be Opt-In First

The first implementation of ADR 0053 must introduce `dist` execution as an opt-in workflow, not as an immediate replacement for `native`.

Examples of acceptable operator interfaces:
- dedicated `make *-dist` targets
- a single explicit `DEPLOY_MODE=dist`
- separate wrapper scripts for `dist` execution

The key requirement is that the chosen mode is visible and intentional.

### 4. Dist Execution Must Consume Assembled Packages As-Is

When deploy execution runs in `dist` mode:
- Terraform must run from `dist/control/terraform/mikrotik/`
- Terraform must run from `dist/control/terraform/proxmox/`
- Ansible must run from `dist/control/ansible/`

`dist` execution must not silently fall back to native roots.

If a required package or local input is missing, the workflow must fail explicitly.

### 5. Native Workflow Remains The Rollback Path Until Parity Is Proven

During the migration period:
- `native` remains supported
- `dist` must prove parity through side-by-side execution and validation
- rollback means returning operators to the existing `native` workflow without changing source ownership

ADR 0053 is not complete when `dist` merely exists. It is complete when operators can intentionally choose `dist` execution with confidence and revert to `native` if needed.

### 6. Package Manifests Become Execution Inputs, Not Just Validation Metadata

For `dist` execution, package manifests are no longer only informational.

They must be treated as execution contracts that declare:
- package class
- required local inputs
- validation commands
- source provenance

Operator workflows must respect those manifests instead of bypassing them with ad hoc assumptions.

### 7. Out Of Scope

ADR 0053 does not:
- remove canonical native source roots
- move manual source into `src/`
- redesign package classes from ADR 0052
- change bootstrap package ownership
- change runtime inventory assembly from ADR 0051

## Consequences

### Positive

1. `dist/` can become a real execution boundary instead of a documentation-only output
2. operator workflows become closer to CI-validated package contracts
3. deploy execution becomes more reproducible and easier to reason about
4. rollback remains available through the explicit `native` mode

### Negative / Trade-offs

1. deploy orchestration gets another execution mode to maintain during transition
2. phase scripts and Make targets will need mode-aware path handling
3. local input handling becomes more visible and may feel stricter to operators

## References

- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0052: Deploy Package Assembly Over Accepted Ansible Runtime
- `deploy/Makefile`
- `topology-tools/assemble-deploy.py`
- `topology-tools/validate-dist.py`
