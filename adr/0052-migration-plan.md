# ADR 0052: Migration Plan

План миграции к `src/` и `dist/` после завершения ADR 0051.

## Preconditions

Перед началом этого плана должны быть выполнены условия ADR 0051:

1. `ansible.cfg` использует assembled runtime inventory
2. tracked inventory source не содержит raw secrets
3. `deploy/` не зависит от legacy manual inventory coupling
4. assembled Ansible runtime inventory валидируется отдельно

Если эти условия не выполнены, ADR 0052 начинать нельзя.

## Цели

1. Перенести manual source в `src/`
2. Ввести explicit deploy assembly в `dist/`
3. Не ломать уже стабилизированный Ansible runtime
4. Отделить release-safe packages от local-only secret material

## Phase 0: Baseline

```bash
python3 topology-tools/regenerate-all.py
python3 topology-tools/assemble-ansible-runtime.py
cd deploy && make validate
```

## Phase 1: Перенести manual source в `src/`

Переносить только manual source:
- `ansible/` source files -> `src/ansible/`
- `bootstrap/` manual files -> `src/bootstrap/`
- `manual-scripts/` -> `src/bootstrap/` и `src/scripts/`
- `configs/` -> `src/configs/`
- `scripts/` -> `src/scripts/`

Нельзя переносить:
- `generated/**`
- local-only secrets
- production secret-bearing outputs

Validation gate:

```bash
python3 topology-tools/regenerate-all.py
python3 topology-tools/assemble-ansible-runtime.py
```

## Phase 2: Реализовать `assemble-deploy.py`

Assembler должен:
- собирать `dist/bootstrap/<device-id>/`
- собирать `dist/control/terraform/{mikrotik,proxmox}/`
- собирать `dist/control/ansible/` из `src/ansible/` и assembled runtime inventory
- выпускать target manifests
- падать при попадании secret-local файлов в release-safe output

Validation gate:

```bash
python3 topology-tools/assemble-deploy.py
ansible-inventory -i dist/control/ansible/inventory --list > /dev/null
cd dist/control/terraform/mikrotik && terraform init -backend=false && terraform validate
cd dist/control/terraform/proxmox && terraform init -backend=false && terraform validate
```

## Phase 3: Переключить `deploy/` на `dist/`

Обновить:
- `deploy/Makefile`
- `deploy/phases/*.sh`
- operator runbooks

Правило:
- cutover выполняется единым батчем
- нельзя сначала удалить старые пути, а потом чинить runtime

Validation gate:

```bash
cd deploy && make generate
cd deploy && make assemble
cd deploy && make validate-dist
```

## Phase 4: Обновить документацию и CI

Обновить:
- `README.md`
- `CLAUDE.md`
- `docs/**`
- `.github/workflows/**`
- `topology/L7-operations.yaml`

Validation gate:
- команды в документации соответствуют реальному pipeline
- CI публикует только release-safe artifacts

## Phase 5: Cleanup

Удалять только после успешного cutover:
- legacy source paths
- temporary compatibility shims
- deprecated duplicate manual files

Не смешивать cleanup с topology identity changes.

## Критерии завершения

1. manual source живет в `src/`
2. generated output живет в `generated/`
3. deploy-ready output живет в `dist/`
4. `deploy/` использует `dist/`
5. release-safe policy enforced
