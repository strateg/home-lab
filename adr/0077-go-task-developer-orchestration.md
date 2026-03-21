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

### Normative rules

1. `Taskfile.yml` becomes the canonical command catalog for developer workflows.
2. Root `Makefile` remains as a compatibility shim during migration and delegates to `task` where applicable.
3. CI migration is staged:
   - initial phase: CI keeps current direct commands;
   - migration phase: CI switches selected jobs to `task` targets;
   - final phase: duplicated direct command chains are removed once parity is proven.
4. Task naming uses explicit namespaces:
   - `validate:*`
   - `build:*`
   - `test:*`
   - `framework:*`
   - `project:*`
   - `ci:*`
5. ADR0076 strict gates must have first-class targets (`framework:verify-lock`, `framework:compile`, rollback/matrix/audit gates).

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

### Trade-offs

1. Additional dependency: `go-task` binary in developer and CI environments.
2. Transition period with dual surfaces (`Taskfile.yml` + compatibility `Makefile`).
3. Requires naming/governance discipline to avoid Taskfile sprawl.

---

## Migration Plan

### Stage 1: Bootstrap

1. Add root `Taskfile.yml` with minimum parity targets for existing root `Makefile`.
2. Add `task --list` onboarding docs and install instructions.

### Stage 2: Coverage

1. Add strict framework/project targets for ADR0076 flows.
2. Add aggregate local gate (`ci:local`) mirroring mandatory checks.

### Stage 3: CI Alignment

1. Migrate selected workflows to `task` execution.
2. Remove duplicate inline command chains after evidence parity.

### Stage 4: Compatibility Cleanup

1. Keep or retire root `Makefile` shim based on adoption and platform needs.
2. If retained, limit it to thin aliases only.

---

## Acceptance Criteria

1. `Taskfile.yml` covers all current root `Makefile` commands.
2. `Taskfile.yml` includes ADR0076 strict gates and new project bootstrap flow.
3. At least one primary CI workflow executes through `task` targets without regressions.
4. Developer docs reference `task` as canonical local orchestrator.

---

## References

- `README.md`
- `Makefile`
- `v5/scripts/lane.py`
- `.github/workflows/lane-validation.yml`
- `.github/workflows/python-checks.yml`
