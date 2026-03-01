# ADR 0051: Migration Plan

План миграции к `src/` + `dist/` без поломки текущего workflow.

## Цели

1. Разделить manual source, generated output и assembled deploy artifacts
2. Не ломать текущие entrypoint'ы по пути миграции
3. Не смешивать файловую реструктуризацию с отдельными семантическими миграциями
4. Ввести validation gate после каждой фазы

## Что не входит в этот план

Этот план не делает:
- переименование device ID `mikrotik-chateau -> rtr-mikrotik-chateau`
- удаление topology alias'ов
- публикацию secret-bearing артефактов в CI
- немедленный перенос `deploy/Makefile` в корень репозитория

Если понадобится cleanup device identity, это отдельная миграция.

## Принципы

1. Использовать `git mv` там, где реально переносится tracked file
2. Делать атомарные коммиты с рабочим состоянием после каждого коммита
3. Сначала добавлять совместимость, потом переключать runtime, потом удалять legacy
4. Не принимать ADR как `Accepted`, пока assembler и validation не реализованы полностью
5. Не полагаться на пустые директории как на результат коммита

## Базовый validation gate

Перед началом миграции нужно зафиксировать baseline:

```bash
git status
python3 topology-tools/regenerate-all.py
cd deploy && make validate
ansible-inventory -i generated/ansible/inventory/production --list > /dev/null
```

Если что-то из baseline уже не работает, сначала надо стабилизировать текущее состояние, потом мигрировать.

---

## Phase 0: Подготовка

### Что делаем

1. Создаем ветку миграции
2. Проверяем baseline
3. Фиксируем список runtime-зависимостей, которые нельзя ломать промежуточными коммитами

### Runtime-контракты, которые должны остаться рабочими до cutover

- `deploy/phases/*.sh`
- `deploy/Makefile`
- `ansible/ansible.cfg`
- `topology/L7-operations.yaml`
- `topology-tools/regenerate-all.py`

### Команды

```bash
git checkout -b refactor/adr-0051-build-pipeline
python3 topology-tools/regenerate-all.py
cd deploy && make validate
```

### Коммит

На этой фазе коммит не обязателен.

---

## Phase 1: Создать `src/` и перенести manual source без cutover runtime

### Что делаем

1. Создаем `src/`
2. Переносим manual source в `src/`
3. Оставляем совместимые точки входа, если runtime все еще ожидает старые пути

### Важно

- Не удалять `ansible/` целиком на этой фазе
- Не удалять `bootstrap/` целиком на этой фазе
- Не удалять `manual-scripts/`, если на них еще ссылаются runbook'и, docs или post-install скрипты
- Для директорий, которые должны появиться в git до наполнения, использовать `.gitkeep`

### Рекомендуемый scope переноса

Переносить только manual source:
- `ansible/playbooks -> src/ansible/playbooks`
- `ansible/roles -> src/ansible/roles`
- `ansible/group_vars -> src/ansible/group_vars`
- `ansible/requirements.yml -> src/ansible/requirements.yml`
- `ansible/vault-helper.sh -> src/ansible/vault-helper.sh`
- `ansible/README.md -> src/ansible/README.md`
- `bootstrap/mikrotik -> src/bootstrap/mikrotik`
- `manual-scripts/bare-metal -> src/bootstrap/proxmox`
- `manual-scripts/opi5 -> src/bootstrap/opi5`
- `manual-scripts/openwrt -> src/bootstrap/openwrt`
- `configs -> src/configs`
- `scripts -> src/scripts`

### Что не переносить как manual source

- `generated/**`
- production `terraform.tfvars`
- `.vault_pass`
- production `answer.toml` с реальными секретами

### Особый случай: Ansible inventory override

Не удалять сразу `ansible/inventory/production/group_vars/all.yml`.

Сначала:
1. скопировать или перенести manual-overrides в `src/ansible/inventory-overrides/`
2. убедиться, что assembler умеет их корректно собирать
3. только потом убирать legacy-path

### Validation gate

После этой фазы должно оставаться рабочим:

```bash
python3 topology-tools/regenerate-all.py
cd deploy && make validate
```

### Коммит

```text
refactor(adr-0051): move manual sources to src with legacy runtime intact
```

---

## Phase 2: Реализовать assembler и release-safe validation

### Что делаем

1. Создаем `topology-tools/assemble-deploy.py`
2. Собираем `dist/` по execution scope:
   - `dist/bootstrap/<device-id>/`
   - `dist/control/terraform/{mikrotik,proxmox}/`
   - `dist/control/ansible/`
   - `dist/manifests/targets/*.md`
3. Добавляем deterministic overlay для Ansible без custom deep merge
4. Добавляем проверку release-safe содержимого

### Ansible strategy

Assembler должен:
- брать `generated/ansible/inventory/production/hosts.yml` как source of truth
- копировать generated `group_vars/all.yml` в `group_vars/all/10-generated.yml`
- копировать manual override в `group_vars/all/90-manual.yml`
- копировать manual `host_vars/*.yml` как overlay

### Что считать ошибкой assembler

Assembler должен падать, если:
- отсутствует обязательный generated input
- отсутствует обязательный manual input для target manifest
- в release-safe `dist/` попали `*.tfvars`, `.vault_pass`, private keys или production `answer.toml`

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
python3 topology-tools/assemble-deploy.py
ansible-inventory -i dist/control/ansible/inventory/production --list > /dev/null
cd dist/control/terraform/mikrotik && terraform validate
cd dist/control/terraform/proxmox && terraform validate
```

### Коммит

```text
feat(adr-0051): add deploy assembler and dist validation
```

---

## Phase 3: Подключить `deploy/` к assembled output

### Что делаем

1. Обновляем `deploy/Makefile`
2. Обновляем `deploy/phases/*.sh`
3. Переводим runtime на `dist/`, но при необходимости оставляем временный fallback

### Правило cutover

Все runtime entrypoint'ы должны переключаться в одном батче:
- `deploy/Makefile`
- `deploy/phases/03-services.sh`
- другие `deploy/phases/*.sh`, если они читают старые пути

Нельзя:
- сначала удалить `ansible/`
- потом в следующем коммите чинить `deploy/phases/03-services.sh`

### Канонические команды после этой фазы

```bash
cd deploy && make generate
cd deploy && make assemble
cd deploy && make validate-dist
```

### Validation gate

```bash
cd deploy && make generate
cd deploy && make assemble
cd deploy && make validate-dist
```

### Коммит

```text
refactor(adr-0051): switch deploy runtime to assembled dist packages
```

---

## Phase 4: Обновить orchestration и документацию

### Что делаем

Обновляем все документы и runbook'и, которые описывают старые пути:
- `topology/L7-operations.yaml`
- `topology-tools/regenerate-all.py`
- `CLAUDE.md`
- `README.md`
- `docs/**`
- `.github/workflows/**`

### Важно

CI в этом репозитории сейчас ставит зависимости через:

```bash
python -m pip install -e .[dev]
```

Поэтому новый workflow не должен переходить на несуществующий `topology-tools/requirements.txt`, пока такой файл реально не введен в проект.

### Validation gate

1. Локальные команды из runbook'ов соответствуют реальным путям
2. CI workflow использует реальный способ установки зависимостей
3. `topology/L7-operations.yaml` больше не ссылается на legacy path

### Коммит

```text
docs(adr-0051): update runbooks and CI to src/dist workflow
```

---

## Phase 5: Удалить legacy path после cutover

### Условия входа в фазу

Эту фазу можно делать только если:

1. assembler реализован полностью
2. `deploy/` уже работает с `dist/`
3. docs и runbook'и уже обновлены
4. validation gate предыдущей фазы пройден

### Что можно удалять

Только реально deprecated path:
- legacy manual inventory path
- legacy duplicate bootstrap files
- compatibility shims
- старые директории, на которые больше нет runtime-ссылок

### Что нельзя удалять в рамках этой фазы

- `topology/L1-foundation/devices/owned/network/mikrotik-chateau.yaml`

Это не cleanup path, а изменение topology identity.

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
python3 topology-tools/assemble-deploy.py
cd deploy && make validate-dist
git grep -n "ansible/|manual-scripts/|bootstrap/" -- . ":(exclude)Migrated_and_archived"
```

Последняя команда используется как ручная проверка оставшихся ссылок. Каждое совпадение надо просмотреть, а не удалять автоматически.

### Коммит

```text
refactor(adr-0051): remove legacy paths after src/dist cutover
```

---

## Phase 6: Принять ADR

ADR можно переводить в `Accepted` только после того, как:

1. все validation gate пройдены
2. assembler не skeleton, а рабочий инструмент
3. `deploy/` реально использует `dist/`
4. documentation и CI соответствуют реальному workflow

### Коммит

```text
docs(adr-0051): accept ADR after successful cutover
```

---

## Рекомендуемая последовательность коммитов

1. `refactor(adr-0051): move manual sources to src with legacy runtime intact`
2. `feat(adr-0051): add deploy assembler and dist validation`
3. `refactor(adr-0051): switch deploy runtime to assembled dist packages`
4. `docs(adr-0051): update runbooks and CI to src/dist workflow`
5. `refactor(adr-0051): remove legacy paths after src/dist cutover`
6. `docs(adr-0051): accept ADR after successful cutover`

## Критерии завершения

Миграция считается завершенной, когда:

1. manual source живет в `src/`
2. generated output живет в `generated/`
3. assembled runtime output живет в `dist/`
4. `deploy/` работает через `dist/`
5. CI публикует только release-safe артефакты
6. legacy path удалены
7. отдельные semantic migration не были случайно смешаны с этой файловой реструктуризацией
