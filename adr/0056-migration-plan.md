# ADR 0056: Migration Plan

- Status: Draft
- Date: 2026-03-01
- Related ADR: [0056-native-execution-workspace.md](0056-native-execution-workspace.md)

## Goal

Move native execution copies out of `generated/` and into `.work/native/` without changing ownership of:
- `generated/`
- `local/`
- `terraform-overrides/`
- `dist/`

## Preconditions

1. ADR 0054 is accepted and implemented
2. ADR 0055 is accepted and implemented
3. native and dist parity checks are already working on the current architecture

## Phase 0: Inventory Native Mutation Paths

Identify every place that still assumes native execution mutates `generated/`:
- `deploy/Makefile`
- `deploy/phases/01-network.sh`
- `deploy/phases/02-compute.sh`
- `deploy/phases/00-bootstrap.sh`
- `topology-tools/materialize-native-inputs.py`
- `topology-tools/check-native-inputs.py`
- operator docs and onboarding notes

## Phase 1: Introduce `.work/native/` Contract

Add a dedicated native workspace root:

```text
.work/native/
```

and make it gitignored.

Define canonical assembled targets:
- `.work/native/terraform/mikrotik/`
- `.work/native/terraform/proxmox/`
- `.work/native/bootstrap/srv-gamayun/`
- `.work/native/bootstrap/srv-orangepi5/`

Explicit workspace policy:
- `.work/native/` is disposable
- `.work/native/` is never a source of truth
- native assembly overwrites or rebuilds the workspace on demand
- preflight validates canonical roots, not stale workspace residue

## Phase 2: Replace Native Materialization With Native Assembly

Refactor current native materialization tooling so that it assembles execution roots under `.work/native/` from:
- `generated/`
- `terraform-overrides/`
- `local/`

At this phase, do not change `dist`.

Compatibility note:
- `make materialize-native-inputs` may temporarily remain as an alias
- the target behavior must still become native workspace assembly
- after cutover, a clearer name such as `make assemble-native` should be preferred

## Phase 2.5: Terraform State Strategy

Before the native cutover is considered complete, decide how native Terraform state is handled:
- configure a remote backend, or
- explicitly accept workspace-local state under `.work/native/terraform/<target>/`

This decision must be reflected in:
- native operator docs
- cleanup commands
- rollback guidance

If remote backend setup is required for the environment, complete it before relying on `.work/native/` as the main operator path.

## Phase 3: Switch Native Deploy Paths

Update native deploy commands to use `.work/native/`:
- Terraform phase scripts
- native Makefile plan/apply targets
- bootstrap helper flows that need execution-ready files

Native commands must stop reading execution copies from `generated/`.

Target operator behavior after cutover:
- `make generate` performs generation plus native assembly
- `make assemble-native` becomes the explicit native workspace assembly command
- `make materialize-native-inputs` may remain temporarily as a compatibility alias only

## Phase 3.5: Update CI And Operator Diagnostics

Update automation and helper commands to reflect the new native workspace:
- CI checks that reason about native execution
- parity checks, if they inspect native paths directly
- operator diagnostics such as `make status`

The intent is that `.work/native/` becomes visible as an execution workspace rather than an implicit internal detail.

## Phase 4: Update Docs And Examples

Update operator-facing docs and examples together with the path switch:
- `README.md`
- `CLAUDE.md`
- deployment strategy guides
- bootstrap guides

Operators should no longer be shown `generated/bootstrap/...` as the execution-ready location once `.work/native/bootstrap/...` becomes canonical for native execution.

## Phase 5: Update Preflight And Cleanup

Update:
- native readiness checks
- cleanup commands
- regeneration commands

Rules:
- `generated/` may be cleaned independently
- `.work/native/` may be deleted independently
- stale `.work/native/` must never be treated as canonical

## Phase 6: Rollback Contract

If the `.work/native/` cutover introduces regressions:
- native phase scripts may be switched back to `generated/...` execution roots
- `.work/native/` remains disposable and can be removed entirely
- `generated/`, `local/`, `terraform-overrides/`, and `dist/` ownership does not change during rollback

Rollback must never reintroduce `generated/` as a canonical source for local inputs or tracked overrides.

## Phase 7: Docs And Onboarding

Update:
- `README.md`
- `CLAUDE.md`
- deployment strategy docs
- bootstrap guides

Add a simple operator mental model:
- `generated/` = baseline
- `.work/native/` = native execution copy
- `dist/` = dist execution copy

## Phase 8: Remove Legacy Native-In-Generated Assumptions

After the cutover:
- remove old docs that point operators at native execution copies under `generated/`
- remove compatibility code that writes native execution copies back into `generated/`

## Completion Criteria

ADR 0056 is complete when:
1. native Terraform and bootstrap execution use `.work/native/`
2. `generated/` contains no native execution copies
3. `dist` behavior remains unchanged
4. docs consistently describe the new workspace model
5. native state handling is explicit: remote backend or accepted workspace-local state
6. operator UX reflects the new contract, including `generate -> assemble-native`
