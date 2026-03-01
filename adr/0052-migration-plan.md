# ADR 0052: Migration Plan

План миграции к explicit `dist/` assembly поверх уже принятого ADR 0051.

## Preconditions

Перед началом этого плана должны быть выполнены условия ADR 0051:

1. `ansible.cfg` использует assembled runtime inventory
2. tracked inventory source не содержит raw secrets
3. `deploy/` не зависит от legacy manual inventory coupling
4. assembled Ansible runtime inventory валидируется отдельно

Если эти условия не выполнены, ADR 0052 начинать нельзя.

## Цели

1. Ввести explicit deploy assembly в `dist/`
2. Не ломать уже стабилизированный Ansible runtime из ADR 0051
3. Отделить release-safe packages от local-input-required material
4. Зафиксировать operator-facing package manifests

## Non-Goals

В рамках этого плана не выполняется:

1. перенос manual source в `src/`
2. изменение ownership-модели inventory из ADR 0051
3. topology identity cleanup
4. redesign secret management beyond existing ADR 0051 boundaries

## Phase 0: Baseline

Зафиксировать реальные inputs для будущего `dist/`:

- `ansible/`
- `generated/ansible/runtime/production/`
- `generated/terraform/mikrotik/`
- `generated/terraform/proxmox/`
- `generated/bootstrap/**`
- `bootstrap/`, `manual-scripts/`, `configs/`, `scripts/` только если они действительно нужны для assembled package

Validation gate:

```text
python3 topology-tools/regenerate-all.py
cd deploy && make validate
```

Результат:
- список canonical input roots для assembler
- список файлов, которые являются `release-safe`
- список required local inputs, которые нельзя публиковать

## Phase 1: Define `dist/` Contract

Определить целевой layout:

```text
dist/
├── bootstrap/
│   └── <device-id>/
├── control/
│   ├── ansible/
│   │   ├── ansible.cfg
│   │   ├── playbooks/
│   │   ├── roles/
│   │   ├── inventory/
│   │   └── manifest.json
│   └── terraform/
│       ├── mikrotik/
│       ├── proxmox/
│       └── manifest.json
└── manifests/
    ├── local-inputs.json
    ├── release-safe.json
    └── sources.json
```

Правила:

1. `dist/` - assembled output only
2. `dist/control/ansible/inventory/` копируется из `generated/ansible/runtime/production/`
3. Terraform packages собираются из `generated/terraform/**`
4. bootstrap packages собираются из generated bootstrap output и scrubbed templates/examples only
5. assembler не должен встраивать `local-secret` или operator-local credentials
6. assembler должен выпускать manifests с source provenance и required local inputs

Validation gate:
- contract review completed
- каждый planned package path имеет один явный source owner

## Phase 2: Реализовать `assemble-deploy.py`

Assembler должен:
- собирать `dist/bootstrap/<device-id>/`
- собирать `dist/control/terraform/{mikrotik,proxmox}/`
- собирать `dist/control/ansible/` из `ansible/` и assembled runtime inventory
- выпускать package manifests и top-level manifests
- падать при попадании `local-secret` файлов в release-safe output
- сообщать о missing required local inputs через manifest, а не через silent omission

Validation gate:

```text
python3 topology-tools/assemble-deploy.py
```

Результат:
- assembler работает side-by-side
- existing source layout не меняется
- `dist/` собирается детерминированно

## Phase 3: Validate `dist/` Side-by-Side

Проверить packaged outputs без немедленного cutover runtime:

Validation gate:

```text
python3 topology-tools/regenerate-all.py
python3 topology-tools/assemble-deploy.py
ansible-inventory -i dist/control/ansible/inventory --list
cd dist/control/ansible && ansible-playbook --syntax-check playbooks/common.yml
cd dist/control/ansible && ansible-playbook --syntax-check playbooks/postgresql.yml
cd dist/control/ansible && ansible-playbook --syntax-check playbooks/redis.yml
cd dist/control/terraform/mikrotik && terraform init -backend=false && terraform validate
cd dist/control/terraform/proxmox && terraform init -backend=false && terraform validate
```

Дополнительно:
- secret scan по `dist/`
- проверка, что `release-safe` package manifests не перечисляют запрещенные файлы
- проверка, что `local-inputs.json` покрывает все непубликуемые operator-local dependencies

## Phase 4: Add Dist-Aware Deploy Targets

Обновить `deploy/Makefile`, не переключая весь operator workflow автоматически.

Добавить цели:
- `make assemble-dist`
- `make validate-dist`

Правила:
- новый workflow должен быть opt-in на этом этапе
- существующий runtime workflow из ADR 0051 должен продолжать работать без `dist/`

Validation gate:
- `cd deploy && make assemble-dist`
- `cd deploy && make validate-dist`

## Phase 5: Optional Deploy Cutover

Обновить:
- `deploy/Makefile`
- `deploy/phases/*.sh`
- operator runbooks

Правило:
- cutover выполняется единым батчем
- нельзя сначала удалить native source-based workflow, а потом чинить runtime
- cutover делается только после стабильного side-by-side validation

Validation gate:

```text
cd deploy && make generate
cd deploy && make assemble-dist
cd deploy && make validate-dist
```

## Phase 6: Обновить документацию и CI

Обновить:
- `README.md`
- `CLAUDE.md`
- `docs/**`
- `.github/workflows/**`
- `topology/L7-operations.yaml`

Validation gate:
- команды в документации соответствуют реальному pipeline
- CI публикует только release-safe artifacts

## Phase 7: Cleanup

Удалять только после успешного cutover, если cutover действительно принят как основной operator workflow.

Удалять можно:
- temporary compatibility shims for `dist/`
- deprecated duplicate assembly helpers
- obsolete docs that describe pre-`dist/` packaging workflow

Нельзя удалять:
- canonical source roots только потому, что появился `dist/`
- файлы, которые всё ещё остаются source-of-truth для assembler
- anything tied to future `src/` migration without a separate ADR

Не смешивать cleanup с topology identity changes или source layout migration.

## Критерии завершения

1. deploy-ready output живет в `dist/`
2. `dist/control/ansible/` собирается из `ansible/` и assembled runtime inventory ADR 0051
3. `dist/control/terraform/` собирается из generated Terraform roots
4. package manifests описывают release-safe contents и required local inputs
5. `deploy/` при необходимости умеет работать с `dist/`
6. release-safe policy enforced
7. repository source layout не меняется в рамках ADR 0052
