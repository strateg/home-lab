# ADR0077 Implementation Evidence

**Date:** 2026-03-21
**ADR:** `adr/0077-go-task-developer-orchestration.md`

## 1. Legacy Command -> Task Target Mapping

| Legacy command / chain | Task target |
|---|---|
| `python v5/scripts/orchestration/lane.py validate-v4` | `task validate:v4` |
| `python v5/scripts/orchestration/lane.py validate-v5` | `task validate:v5` |
| `V5_SECRETS_MODE=passthrough python v5/scripts/orchestration/lane.py validate-v5` | `task validate:v5-passthrough` |
| `python v5/scripts/orchestration/lane.py validate-v5-layers` | `task validate:v5-layers` |
| `python v5/scripts/orchestration/lane.py phase1-gate` | `task validate:phase1-gate` |
| `python v5/scripts/orchestration/lane.py build-v4` | `task build:v4` |
| `python v5/scripts/orchestration/lane.py build-v5` | `task build:v5` |
| `python v5/scripts/phase1/reconcile_phase1_mapping.py` | `task build:phase1-reconcile` |
| `python v5/scripts/phase1/refresh_phase1_backlog.py` | `task build:phase1-backlog` |
| `python v5/scripts/model/sync_v5_model_lock.py` | `task build:phase4-sync-lock` |
| `python v5/scripts/model/export_v5_instance_bindings.py` | `task build:phase4-export` |
| `black --check . && isort --check-only .` | `task validate:lint` |
| `mypy --config-file pyproject.toml v4/topology-tools` | `task validate:typecheck` |
| `pylint v4/topology-tools` | `task validate:pylint` |
| `python v4/topology-tools/check-adr-consistency.py --strict-titles` | `task validate:adr-consistency` |
| Full local quality chain | `task validate:quality` |
| `python v5/topology-tools/verify-framework-lock.py --strict && python v5/topology-tools/rehearse-framework-rollback.py && python v5/topology-tools/validate-framework-compatibility-matrix.py && python v5/topology-tools/audit-strict-runtime-entrypoints.py` | `task framework:strict` |
| `python -m pytest -o addopts= v4/tests -q` | `task test:v4` |
| `python -m pytest -o addopts= v5/tests -q` | `task test:v5` |
| `python v4/topology-tools/run-fixture-matrix.py` | `task test:fixture-matrix-v4` |
| Mandatory local pre-push chain | `task ci:local` |
| `python-checks` strict chain | `task ci:python-checks-core` |
| `lane-validation` strict v5 inject chain | `task ci:lane-v5-inject` |
| `lane-validation` strict v5 passthrough chain | `task ci:lane-v5-passthrough` |
| `topology-matrix` strict mainline inject chain | `task ci:topology-mainline-inject` |
| `topology-matrix` strict mainline passthrough chain | `task ci:topology-mainline-passthrough` |
| `topology-matrix` fixture chain | `task ci:topology-fixture-matrix` |

## 2. CI Fallback Switch Contract

All migrated workflows use the same explicit and reversible contract:

- `USE_TASK_ORCHESTRATION=1` enables task-first execution.
- `ALLOW_TASK_FALLBACK=1` allows fallback to legacy inline commands when task execution fails.
- `ALLOW_TASK_FALLBACK=0` makes task failure blocking (no legacy fallback).

## 3. Toolchain Version Policy Evidence

- Minimum supported local `go-task` version: `3.45.4`.
- CI pin: `arduino/setup-task@v2` with `version: 3.45.4`.
- Local setup script default: `TASK_VERSION=3.45.4` in `v5/scripts/environment/setup-dev-environment.sh`.

## 4. KPI Evidence Source Definition

Stabilization evidence is collected from:

1. CI telemetry/log sampling:
   - task invocation success in migrated workflows (`task ci:*`, `task validate:*`).
   - fallback events (`Task orchestration failed; executing legacy fallback chain.`).
2. Workflow usage report:
   - count of jobs with `USE_TASK_ORCHESTRATION=1`.
   - count of jobs still running direct non-task chains.
3. Local command-surface sampling:
   - weekly review of documented/automated entrypoints (`README`, `Taskfile.yml`, `taskfiles/*`) to ensure Task-first growth.

Review cadence:

- End of Wave 3 stabilization window: compile parity summary and mismatch count.
- Acceptance condition for cleanup: no critical parity mismatches across mandatory CI paths in the window.
