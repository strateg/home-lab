# ADR 0077: Go-Task as Developer Orchestration Layer

**Date:** 2026-03-21
**Status:** Proposed
**Depends on:** ADR 0074, ADR 0075, ADR 0076

---

## Context

Developer orchestration is currently split across:

1. root `Makefile` (limited migration wrappers);
2. direct Python entrypoints (`v5/scripts/lane.py`, `v5/topology-tools/*.py`);
3. CI workflows that mostly duplicate command chains directly.

Current pain points:

1. no single local entrypoint for compile/test/build/lint/lock-gates;
2. drift risk between local commands and CI steps;
3. Windows ergonomics are weak when `make`/shell behavior differs across environments;
4. new external project bootstrap flow (ADR0076) needs stable, reusable task composition.

---

## Decision

Adopt **go-task** (`Taskfile.yml`) as the primary developer orchestration layer for repository-local workflows.

### Architecture boundary (normative)

1. `Taskfile.yml` is orchestration-only: sequencing, dependency graph, defaults, environment wiring.
2. Python scripts remain execution-only: business logic, compilation, validation, generation.
3. Task targets MUST call existing entrypoints (`v5/scripts/lane.py`, `v5/topology-tools/*.py`) instead of re-implementing logic in Task commands.
4. Root `Makefile` remains a compatibility shim during migration and delegates to `task` where applicable.

### Task topology (normative)

Root `Taskfile.yml` includes modular task catalogs:

1. `taskfiles/validate.yml`
2. `taskfiles/build.yml`
3. `taskfiles/test.yml`
4. `taskfiles/framework.yml`
5. `taskfiles/project.yml`
6. `taskfiles/ci.yml`

### Naming and graph policy (normative)

1. Task naming uses explicit namespaces:
   - `validate:*`
   - `build:*`
   - `test:*`
   - `framework:*`
   - `project:*`
   - `ci:*`
2. Mandatory baseline dependency order: `validate -> test -> build`.
3. `framework:strict` is the canonical strict local gate and includes ADR0076 lock/matrix/audit requirements.
4. `ci:local` mirrors mandatory CI checks and is the canonical local pre-push verification target.

### CI migration policy (normative)

1. Initial phase: CI keeps current direct commands.
2. Migration phase: selected jobs switch to `task` targets.
3. Final phase: duplicated inline command chains are removed after parity evidence is recorded.
4. CI fallback switch MUST be explicit and reversible per workflow/job (for example: workflow input or env flag), not by ad-hoc manual edits.

### Toolchain policy (normative)

1. Repository defines and documents a minimum supported `go-task` version for local and CI execution.
2. CI runners pin `go-task` version to avoid behavioral drift.
3. Local onboarding docs include installation steps for Windows/Linux/macOS and verification via `task --version`.

### Governance policy (normative)

1. New developer command flows MUST be added through `Taskfile` namespaces.
2. No new legacy ad-hoc orchestration scripts are introduced for developer workflows.
3. Namespace owners are responsible for target naming consistency and documentation updates.

### Non-goals

1. Replacing Python tooling (`lane.py`, compiler scripts, validators).
2. Changing runtime contracts from ADR0074/0075/0076.
3. Rewriting `v4/deploy/Makefile` deployment orchestration in this ADR.

---

## Consequences

### Positive

1. One discoverable entrypoint for local developer workflows.
2. Better cross-platform consistency (especially Windows) for task orchestration.
3. Lower drift risk between local and CI execution paths.
4. Cleaner onboarding for new project repository bootstrap and strict compile flows.
5. Clear separation between orchestration concerns and execution/business logic.

### Trade-offs

1. Additional dependency: `go-task` binary in developer and CI environments.
2. Transition period with dual surfaces (`Taskfile.yml` + compatibility `Makefile`).
3. Requires naming/governance discipline to avoid Taskfile sprawl.
4. Requires temporary CI dual-mode support during cutover.

---

## Implementation and Migration Plan

### Wave 0: Baseline inventory

1. Inventory all current developer and CI command chains.
2. Build mapping table `legacy command -> task target`.
3. Identify critical workflows and define rollback switches.

### Wave 1: Parity bootstrap

1. Add root `Taskfile.yml` and modular includes under `taskfiles/`.
2. Implement parity targets for current root `Makefile` commands.
3. Publish `task --list` onboarding and install docs.

### Wave 2: Strict gate coverage

1. Add ADR0076 strict targets under `framework:*` and `project:*`.
2. Implement `framework:strict` aggregate gate.
3. Implement `ci:local` aggregate gate mirroring mandatory checks.

### Wave 3: CI cutover

1. Migrate selected CI workflows to `task ci:*` entrypoints.
2. Keep temporary fallback path to legacy direct commands.
3. Remove duplicated inline CI chains after parity evidence.

### Wave 4: Legacy cleanup

1. Keep or retire root `Makefile` shim based on adoption and platform needs.
2. If retained, limit it to thin aliases only.
3. Enforce policy: all new developer workflows are Task-first.

---

## Rollback Strategy

1. During Waves 2-3, CI jobs retain a switchable fallback to legacy commands using an explicit switch contract (workflow input/env flag).
2. If parity regressions are detected, affected jobs revert to legacy path while preserving Task targets for remediation.
3. Roll-forward requires documented parity evidence for the reverted scope.

---

## Acceptance Criteria

1. `Taskfile.yml` covers mandatory developer workflows: `validate`, `test`, `build`, `lint/typecheck`, `framework strict gates`, and `project init/bootstrap`.
2. Root `Makefile` compatibility aliases are mapped to Task targets for transition period workflows.
3. `Taskfile.yml` includes ADR0076 strict gates and new project bootstrap flow.
4. At least one primary CI workflow executes through `task` targets without regressions.
5. Developer docs reference `task` as canonical local orchestrator.
6. `framework:strict` and `ci:local` targets are documented and reproducible locally.

---

## Success Metrics (KPI)

1. At least 90% of local developer orchestration commands run through `task` targets during the stabilization window.
2. Zero critical parity mismatches between `ci:local` and mandatory CI checks over the stabilization window.
3. Reduced command-surface drift incidents after CI/workflow changes.
4. Onboarding documentation contains a single canonical local orchestration path.
5. KPI evidence source is defined (CI telemetry/log sampling + workflow usage reports) and reviewed at end of Wave 3.

---

## References

- `README.md`
- `Makefile`
- `v5/scripts/lane.py`
- `.github/workflows/lane-validation.yml`
- `.github/workflows/python-checks.yml`
