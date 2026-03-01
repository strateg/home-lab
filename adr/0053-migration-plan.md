# ADR 0053: Migration Plan

План для опционального `dist`-first cutover поверх уже принятых ADR 0051 и ADR 0052.

## Preconditions

Перед началом этого плана должны быть выполнены условия:

1. ADR 0051 accepted and implemented
2. ADR 0052 accepted and implemented
3. `python3 topology-tools/assemble-deploy.py` passes
4. `python3 topology-tools/validate-dist.py` passes
5. package manifests correctly declare required local inputs

## Goal

Сделать `dist` полноценным execution mode для deploy workflow без потери rollback path через текущий `native` mode.

## Non-Goals

В рамках этого плана не выполняется:

1. удаление canonical source roots
2. перенос manual source в `src/`
3. изменение inventory ownership из ADR 0051
4. redesign package classes из ADR 0052

## Phase 0: Baseline Native Workflow

Зафиксировать текущий `native` workflow как known-good baseline.

Validation gate:

```text
cd deploy && make generate
cd deploy && make plan
```

Результат:
- documented rollback path
- список native roots, от которых зависит deploy

## Phase 1: Introduce Explicit Dist Execution Mode

Добавить явный `dist` execution mode в deploy tooling.

Варианты реализации:
- `make plan-dist`
- `make apply-mikrotik-dist`
- `make apply-proxmox-dist`
- `make configure-dist`
- `make deploy-all-dist`

Или один mode flag:
- `DEPLOY_MODE=dist`

Требования:
- mode должен быть явным
- `dist` mode не должен silently fallback на native roots

## Phase 2: Side-by-Side Parity Validation

Для каждого deploy phase сравнить `native` и `dist` mode.

Проверки:
- Terraform init/plan из native roots
- Terraform init/plan из `dist/control/terraform/*`
- Ansible syntax/inventory checks из native root
- Ansible syntax/inventory checks из `dist/control/ansible`

Результат:
- documented parity gaps
- decision whether `dist` is operator-ready

## Phase 3: Opt-In Operator Workflow

Сделать `dist` mode доступным оператору, но не default.

Обновить:
- `deploy/Makefile`
- `deploy/phases/*.sh`
- `docs/**`

Требования:
- `native` remains available
- operator can choose `dist` intentionally
- local input requirements are surfaced before execution

## Phase 4: Optional Default Switch

Только если `dist` mode стабилен:
- сделать `dist` default
- оставить explicit `native` fallback

Этот шаг не обязателен для завершения ADR 0053.

## Phase 5: Cleanup

Только после стабильного `dist` execution mode:
- убрать temporary mode shims
- убрать deprecated path branching
- сократить documentation drift between native and dist workflows

Нельзя:
- удалять native roots
- ломать rollback path без нового ADR

## Completion Criteria

1. deploy tooling supports explicit `native` and `dist` modes
2. `dist` mode runs from assembled package roots only
3. rollback to `native` remains documented and working
4. local inputs required by package manifests are surfaced before deploy
5. operator docs describe both modes unambiguously
