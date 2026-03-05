# ADR 0057 Migration Plan

- Status: Active
- Date: 2026-03-05

## Purpose

Move the repository from the current MikroTik bootstrap baseline:

- generated `init-terraform.rsc`
- manual import or legacy SSH-first helper usage
- manual operator handoff into Terraform

to the ADR 0057 target state:

- `netinstall-cli` as the default supported day-0 path
- minimal bootstrap for Terraform handover
- Terraform as the unchanged post-bootstrap owner
- manual import retained only as a compatibility fallback until cutover is complete

## Current Baseline

Current repository behavior already provides:

- tracked canonical bootstrap template: `topology-tools/templates/bootstrap/mikrotik/init-terraform-minimal.rsc.j2`
- tracked compatibility templates:
  - `topology-tools/templates/bootstrap/mikrotik/backup-restore-overrides.rsc.j2`
  - `topology-tools/templates/bootstrap/mikrotik/exported-config-safe.rsc.j2`
- generated release-safe bootstrap output: `generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc`
- generated release-safe Terraform example: `generated/bootstrap/rtr-mikrotik-chateau/terraform.tfvars.example`
- manual bootstrap documentation through `deploy/phases/00-bootstrap.sh`, `deploy/Makefile`, and docs under `docs/`
- legacy SSH-first compatibility helper: `topology-tools/scripts/deployers/mikrotik_bootstrap.py`

This means the migration is not greenfield. It is a controlled cutover from a manual import path to a Netinstall-based path.

## Target End State

ADR 0057 is implemented only when all of the following are true:

1. a supported control-node workflow can run `netinstall-cli` for the intended MikroTik by MAC address
2. the workflow performs hard prerequisite checks before install begins
3. the bootstrap script remains minimal and limited to Terraform handover requirements
4. secret-bearing RouterOS scripts are rendered only into ignored execution roots
5. the first post-bootstrap step is a normal Terraform connection check, plan, or apply
6. repository docs and operator entrypoints present Netinstall as the default day-0 mechanism
7. the older manual import path is clearly marked as compatibility fallback rather than the primary workflow

## Non-Goals

This plan does not:

- replace Terraform as the desired-state system for MikroTik
- redesign repository-wide secret storage
- guarantee a remote-only recovery path
- remove all manual recovery options
- require immediate deletion of legacy helpers before the new path is proven

## Guiding Rules

1. Bootstrap remains a handover step, not a second configuration system.
2. Compatibility paths may remain during rollout, but they must be visibly downgraded.
3. Tracked sources stay reviewable and secret-free.
4. Any plaintext secret artifact must exist only in ignored execution roots.
5. No phase is complete until docs, operator entrypoints, and validation gates are aligned with the code path.

## Workstreams

The migration is easier to control if treated as five coordinated workstreams:

1. Contract
2. Rendering and secrets
3. Netinstall orchestration
4. Terraform handover validation
5. Docs and cutover

Each phase below advances one or more of those workstreams.

## Phase 0: Re-Baseline The Existing Flow

### Objective

Create an explicit inventory of what already exists, what is legacy, and what must remain compatible during rollout.

### Tasks

1. inventory all existing MikroTik bootstrap-related assets:
   - `topology-tools/templates/bootstrap/mikrotik/init-terraform-minimal.rsc.j2`
   - `topology-tools/templates/bootstrap/mikrotik/backup-restore-overrides.rsc.j2`
   - `topology-tools/templates/bootstrap/mikrotik/exported-config-safe.rsc.j2`
   - `topology-tools/scripts/generators/bootstrap/mikrotik/generator.py`
   - `generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc`
   - `generated/bootstrap/rtr-mikrotik-chateau/terraform.tfvars.example`
   - `deploy/phases/00-bootstrap.sh`
   - `deploy/Makefile`
   - `docs/guides/MIKROTIK-TERRAFORM.md`
   - `docs/guides/DEPLOYMENT-STRATEGY.md`
2. record the exact current bootstrap contract already embedded in `init-terraform-minimal.rsc.j2`
3. record which parts of `topology-tools/scripts/deployers/mikrotik_bootstrap.py` are legacy helper behavior and should not be promoted
4. capture current operator expectations around `make bootstrap-info`, manual import, and `terraform.tfvars`

### Deliverables

1. a short compatibility inventory
2. a list of files that must change before cutover
3. a written note confirming that Terraform, not Ansible, remains the post-bootstrap owner

### Exit Gate

Phase 0 completes only when the team can point to one explicit description of:

- current state
- transition state
- target state

## Phase 1: Freeze The Handover Contract

### Objective

Lock down what the day-0 script is allowed to do and what must remain Terraform-owned.

### Tasks

1. define the minimal handover contract in implementation terms:
   - management IP
   - REST API port and service state
   - Terraform automation identity
   - minimum firewall allowance for API access
   - optional SSH recovery posture
2. explicitly classify existing `init-terraform-minimal.rsc.j2` sections into:
   - required for day-0 handover
   - acceptable but optional compatibility logic
   - day-1 or day-2 logic that should move out of bootstrap if present
3. keep `init-terraform-minimal.rsc.j2` as the canonical tracked template during migration
4. keep the generated artifact name `init-terraform.rsc` for compatibility during transition

### Deliverables

1. canonical bootstrap contract for day-0
2. canonical tracked template path
3. decision note on filename compatibility for `init-terraform.rsc`

### Exit Gate

Phase 1 completes only when the allowed contents of the bootstrap script are explicit enough to review future changes against that contract.

## Phase 2: Define Rendering And Secret Inputs

### Objective

Make bootstrap rendering deterministic and consistent with the existing repository secret model.

### Tasks

1. define the exact topology-derived public inputs consumed by the bootstrap template
2. define the exact secret inputs consumed by the bootstrap template
3. define the exact execution-time parameters that are not tracked source data:
   - target MAC
   - install interface
   - install client IP
   - RouterOS package path
4. define the canonical rendering destination in `.work/native/bootstrap/rtr-mikrotik-chateau/`
5. define whether any justified `local/bootstrap/rtr-mikrotik-chateau/` bridge is required
6. ensure all rendered secret-bearing scripts remain ignored
7. ensure example values in ADR/docs are allowlisted where needed for `detect-secrets`

### Deliverables

1. documented input matrix: tracked public, tracked secret, local execution parameter
2. canonical rendered script path
3. explicit failure behavior for missing secret or missing local execution input

### Exit Gate

Phase 2 completes only when rendering can be described as a deterministic transform from approved inputs into a single ignored execution artifact.

## Phase 3: Build The Netinstall Control-Node Workflow

### Objective

Add the real day-0 execution path without yet removing the existing fallback path.

### Tasks

1. choose the primary control-node wrapper:
   - shell-first
   - Ansible-first
   - thin Python wrapper
2. implement hard preflight checks for:
   - `netinstall-cli` availability
   - RouterOS package presence
   - explicit target MAC
   - explicit install interface
   - explicit install client IP
   - rendered bootstrap script presence
3. implement the explicit `netinstall-cli` invocation shape
4. ensure failure messages are operator-readable and stop before install
5. ensure the workflow does not silently fall back to legacy SSH import behavior
6. keep `topology-tools/scripts/deployers/mikrotik_bootstrap.py` documented as recovery-only

### Deliverables

1. one supported control-node command path for Netinstall
2. operator-readable preflight output
3. reproducible invocation contract for the install step

### Exit Gate

Phase 3 completes only when the Netinstall path is runnable end-to-end on a control node up to the point of actual device installation.

## Phase 4: Validate Terraform Handover

### Objective

Prove that the new day-0 path hands over cleanly into the existing Terraform workflow.

### Tasks

1. verify the router is reachable on the intended management IP after bootstrap
2. verify the RouterOS API is reachable on the intended port after bootstrap
3. verify the Terraform bootstrap credentials work
4. verify `local/terraform/mikrotik/terraform.tfvars` and `.work/native/terraform/mikrotik/terraform.tfvars` remain the post-bootstrap contract
5. run a Terraform validation step against the bootstrapped router:
   - provider connectivity check
   - `terraform plan`
   - or a constrained first `terraform apply`
6. confirm that no required day-2 configuration remains trapped inside the bootstrap script

### Deliverables

1. a validated handover checklist
2. one documented first-step Terraform validation command
3. evidence that bootstrap stops where Terraform begins

### Exit Gate

Phase 4 completes only when a newly bootstrapped router can enter the normal Terraform workflow without undocumented manual patching.

## Phase 5: Cut Over Operator Entry Points

### Objective

Make the new path visible as the primary workflow everywhere operators actually look.

### Tasks

1. update `deploy/phases/00-bootstrap.sh` to present Netinstall as the default MikroTik day-0 workflow
2. update `deploy/Makefile` help text and `bootstrap-info` output
3. update `docs/README.md`
4. update `docs/guides/MIKROTIK-TERRAFORM.md`
5. update `docs/guides/DEPLOYMENT-STRATEGY.md`
6. keep manual import and WinBox paths documented only as fallback or compatibility paths
7. ensure all documentation references the same bootstrap artifact names and execution roots

### Deliverables

1. one consistent documented primary workflow
2. one clearly downgraded compatibility workflow
3. aligned file/path references across deploy scripts and docs

### Exit Gate

Phase 5 completes only when an operator following the repository docs will naturally choose the Netinstall path first.

## Phase 6: Compatibility Cleanup

### Objective

Reduce transition debt after the new path has proven stable.

### Tasks

1. decide whether `init-terraform.rsc` keeps its name or is renamed
2. decide whether `topology-tools/scripts/deployers/mikrotik_bootstrap.py` remains as unsupported recovery helper or moves to archive
3. remove stale wording that still implies manual import is the primary path
4. remove any duplicate instructions that disagree on ports, credentials, or file paths
5. review whether a dedicated Netinstall runbook is needed

### Deliverables

1. reduced documentation and tooling duplication
2. an explicit final status for the legacy SSH-first helper
3. final cutover note describing what remains supported

### Exit Gate

Phase 6 completes only when the repository no longer presents conflicting bootstrap models as equally current.

## Validation Matrix

Each phase should be checked against the same four questions:

1. Is the ownership boundary still `bootstrap -> Terraform`?
2. Are tracked artifacts still secret-free?
3. Can an operator identify the supported path without guessing?
4. Is the fallback path still clearly secondary?

## Suggested Execution Order

1. Phase 0: Re-baseline the existing flow
2. Phase 1: Freeze the handover contract
3. Phase 2: Define rendering and secret inputs
4. Phase 3: Build the Netinstall control-node workflow
5. Phase 4: Validate Terraform handover
6. Phase 5: Cut over operator entry points
7. Phase 6: Compatibility cleanup

## Rollback And Safety Rules

1. do not remove the manual import path before the Netinstall path is validated on real hardware
2. do not delete the legacy SSH-first helper before its remaining recovery value is assessed after cutover
3. do not require committing rendered secret-bearing bootstrap artifacts at any stage
4. do not merge documentation that presents conflicting primary workflows
5. do not broaden the bootstrap script beyond the minimal Terraform handover contract to work around Terraform issues

## Decision Snapshot

Resolved:
1. Canonical tracked template is `init-terraform-minimal.rsc.j2`.
2. Generated artifact name remains `init-terraform.rsc` during transition.
3. `backup` and `rsc` restore paths are compatibility-only, not default.

Open:
1. Which control-node wrapper is long-term canonical: current shell + Ansible split, or one unified runner?
2. Should optional SSH stay enabled in compatibility profiles by default, or move to explicit recovery profiles only?

## References

- `adr/0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md`
- `topology-tools/templates/bootstrap/mikrotik/init-terraform-minimal.rsc.j2`
- `topology-tools/scripts/generators/bootstrap/mikrotik/generator.py`
- `topology-tools/scripts/deployers/mikrotik_bootstrap.py`
- `deploy/phases/00-bootstrap.sh`
- `deploy/Makefile`
- `docs/guides/MIKROTIK-TERRAFORM.md`
