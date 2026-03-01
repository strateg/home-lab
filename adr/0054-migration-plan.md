# ADR 0054: Migration Plan

План для отделения operator-owned local inputs от deterministic `generated/` outputs.

## Goal

Сделать `generated/` безопасно очищаемым и воспроизводимым, а operator-edited inputs перенести в отдельный canonical local-only root.

## Preconditions

Перед началом:

1. ADR 0051 accepted and implemented
2. ADR 0052 accepted and implemented
3. ADR 0053 current opt-in execution workflow remains working
4. current local-input files are inventoried

## Current Problem Statement

Сейчас canonical `generated/` tree смешивает:

1. deterministic outputs
2. operator local inputs
3. scratch/debug artifacts

Из-за этого:
- нельзя безопасно делать aggressive cleanup
- stale files копятся между запусками
- preflight checks проверяют execution copies, а не canonical local ownership

Для cleanup нужно различать два разных действия:

1. `managed pre-clean`
   Очистка canonical managed outputs перед regeneration.
2. `garbage cleanup`
   Удаление или перенос scratch/legacy outputs, которые вообще не должны жить в canonical `generated/`.

Эти действия нельзя смешивать в одну неявную операцию.

## Non-Goals

В рамках этого плана не выполняется:

1. отказ от `native` mode
2. пересмотр Ansible vault strategy из ADR 0051
3. перенос manual source layout
4. redesign `dist/` package classes

## Phase 0: Inventory And Classification

Зафиксировать все текущие файлы под `generated/` и классифицировать их по типу:

1. `managed-generated`
2. `local-input`
3. `scratch/debug`
4. `legacy-generated`

Также зафиксировать canonical managed roots и non-canonical roots отдельными списками.

Minimum expected local-input inventory:
- `generated/terraform/mikrotik/terraform.tfvars`
- `generated/terraform/proxmox/terraform.tfvars`
- `generated/bootstrap/srv-gamayun/answer.toml`
- `generated/bootstrap/srv-orangepi5/cloud-init/user-data`

Validation gate:

```text
rg -n "terraform.tfvars|answer.toml|user-data" generated/ docs/ deploy/ topology-tools/
```

Результат:
- явная migration map
- список docs/scripts, которые ещё указывают оператору редактировать `generated/...`
- список путей для `managed pre-clean`
- список путей для `garbage cleanup`

## Phase 1: Introduce Canonical `.local/` Contract

Создать и задокументировать canonical local-only roots:

```text
.local/terraform/mikrotik/terraform.tfvars
.local/terraform/proxmox/terraform.tfvars
.local/bootstrap/srv-gamayun/answer.toml
.local/bootstrap/srv-orangepi5/cloud-init/user-data
```

Требования:
- `.local/` must be gitignored
- `.local/` must be documented as operator-owned
- examples remain in `generated/`
- reviewable non-secret defaults remain tracked outside `.local/`

Allowed tracked sources for operator bootstrap:
- `terraform.tfvars.example`
- `answer.toml.example`
- `user-data.example`
- future explicit non-secret defaults layer, if introduced by a separate ADR or follow-up change

## Phase 2: Materialization Helpers

Ввести unified materialization tooling:

1. `materialize-native-inputs.py`
2. update `materialize-dist-inputs.py`

Rules:
- source of truth is `.local/`
- native execution roots receive copies into `generated/...`
- dist execution roots receive copies into `dist/...`
- missing `.local` files are reported explicitly
- stale execution copies are non-canonical and may be deleted by cleanup/materialization logic

Validation gate:

```text
python topology-tools/materialize-native-inputs.py
python topology-tools/materialize-dist-inputs.py
```

## Phase 3: Update Preflight And Execution Flow

Обновить:
- `deploy/Makefile`
- `deploy/phases/00-bootstrap.sh`
- `deploy/phases/01-network.sh`
- `deploy/phases/02-compute.sh`
- `topology-tools/check-dist-package.py`

Новый contract:
- preflight validates canonical `.local/...`
- execution still consumes copied files in `generated/...` or `dist/...`
- operator is told to edit `.local/...`, not execution copies
- missing `.local/...` must fail explicitly even if a stale copy still exists in an execution root

## Phase 4: Move Scratch And Legacy Outputs Out Of `generated/`

Перенести или удалить:
- `generated/.fixture-matrix-debug/`
- `generated/validation/`
- `generated/tmp-answer.toml`
- `generated/migration/`
- legacy roots like `generated/terraform-mikrotik/`
- root-level legacy files under `generated/terraform/`, when duplicated by scoped roots

Target locations:
- temp directories
- `.cache/`
- archived legacy locations when historically useful

Результат:
- canonical `generated/` no longer contains scratch or legacy roots that would interfere with managed cleanup

## Phase 5: Enable Managed Cleanup Before Regeneration

После того как operator local inputs больше не canonical under `generated/`:

1. add a managed cleanup step before `regenerate-all.py`
2. clean canonical generated roots aggressively
3. do not clean `.local/`
4. treat stale execution copies as disposable

Recommended cleanup scope:
- `generated/ansible/`
- `generated/docs/`
- `generated/bootstrap/`
- `generated/terraform/`

Only after legacy roots and scratch outputs are no longer colocated there.

Managed pre-clean must not be used as a substitute for Phase 4 garbage cleanup.

Validation expectations:
- after pre-clean, regeneration must fully restore canonical managed roots
- missing `.local/...` files must not be masked by old copies inside `generated/...`

Validation gate:

```text
python topology-tools/regenerate-all.py --skip-mermaid-validate
python topology-tools/assemble-deploy.py
python topology-tools/validate-dist.py
python topology-tools/check-deploy-parity.py
```

## Phase 6: Documentation Cutover

Обновить все operator-facing docs так, чтобы они учили:

1. review tracked `*.example` or documented defaults
2. materialize/edit `.local/...`
3. materialize into execution roots
4. run deploy

Нельзя оставлять active docs, instructing direct edits in `generated/...`.

## Completion Criteria

1. canonical operator-edited local inputs live under `.local/`
2. `generated/` contains only generated payloads, examples, and managed outputs
3. native and dist workflows both materialize from `.local/`
4. regeneration can clean managed `generated/` roots safely
5. active docs no longer instruct editing operator inputs directly inside `generated/`
6. scratch and legacy outputs no longer share the canonical `generated/` contract
