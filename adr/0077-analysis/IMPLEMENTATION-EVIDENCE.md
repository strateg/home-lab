# ADR0077 Implementation Evidence

**Date:** 2026-03-28
**ADR:** `adr/0077-go-task-developer-orchestration.md`

## 1. Legacy Command -> Task Target Mapping (Root Layout)

| Legacy command / chain | Task target |
|---|---|
| `python scripts/orchestration/lane.py validate-v5` | `task validate:v5` |
| `V5_SECRETS_MODE=passthrough python scripts/orchestration/lane.py validate-v5` | `task validate:v5-passthrough` |
| `python scripts/orchestration/lane.py validate-v5-layers` | `task validate:v5-layers` |
| `python scripts/orchestration/lane.py phase1-gate` | `task validate:phase1-gate` |
| `python scripts/orchestration/lane.py build-v5` | `task build` |
| `python scripts/phase1/reconcile_phase1_mapping.py` | `task build:phase1-reconcile` |
| `python scripts/phase1/refresh_phase1_backlog.py` | `task build:phase1-backlog` |
| `python scripts/model/sync_v5_model_lock.py` | `task build:sync-lock` |
| `python scripts/model/export_v5_instance_bindings.py` | `task build:export-bindings` |
| `black --check ... && isort --check-only ...` | `task validate:lint` |
| `mypy --config-file pyproject.toml topology-tools` | `task validate:typecheck` |
| `pylint topology-tools` | `task validate:pylint` |
| Full strict framework chain (`verify-lock`, `rollback`, `compatibility`, `audit`) | `task framework:strict` |
| Root layout + v5 lane validation chain | `task validate:default` |
| Root tests | `task test` |
| v4/v5 parity suite | `task test:parity-v4-v5` |
| Plugin API/contract/integration/regression test lanes | `task test:plugin-api`, `task test:plugin-contract`, `task test:plugin-integration`, `task test:plugin-regression` |
| Plugin manifests schema/path validation | `task validate:plugin-manifests` |
| Generated/runtime cleanup before lanes | `task clean` / `task build:clean-generated` |
| Local pre-push gate | `task ci:local` |
| Local pre-push + legacy checks | `task ci:local-with-legacy` |
| `python-checks` strict lane | `task ci:python-checks-core` |
| `lane-validation` lane | `task ci:lane-v5` |
| `topology-matrix` strict mainline lane | `task ci:topology-mainline` |
| Legacy maintenance lane (archive v4 parity + acceptance) | `task ci:legacy-maintenance` |

## 2. CI Fallback Contract State

Primary repository workflows are now **Task-first without inline fallback chains**:

1. `.github/workflows/python-checks.yml`
2. `.github/workflows/lane-validation.yml`
3. `.github/workflows/topology-matrix.yml`
4. `.github/workflows/plugin-validation.yml`

Historical fallback env switches (`USE_TASK_ORCHESTRATION`, `ALLOW_TASK_FALLBACK`) were used during migration waves and are now retired from active primary workflows after parity stabilization.

## 3. Toolchain Version Policy Evidence

- Minimum supported local `go-task` version: `3.45.4`.
- CI pin: `arduino/setup-task@v2` with `version: 3.45.4`.

## 4. KPI Evidence Source Definition

Stabilization evidence is collected from:

1. CI telemetry/log sampling:
   - task invocation success in migrated workflows (`task ci:*`, `task validate:*`, `task test:*`).
   - absence of inline fallback execution chains in primary workflows.
2. Workflow usage report:
   - count of jobs using `task` entrypoints as primary execution path.
   - count of jobs still using duplicated inline orchestration logic.
3. Local command-surface sampling:
   - weekly review of documented/automated entrypoints (`README.md`, `Taskfile.yml`, `taskfiles/*`) for Task-first consistency.

Review cadence:

- End of stabilization window: parity summary + drift incidents.
- Acceptance condition for cleanup: no critical parity mismatches and no orchestration drift across mandatory CI paths.
