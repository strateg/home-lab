# ADR 0051: Migration Plan

План миграции к безопасной Ansible-first модели без преждевременного перехода к `src/` и `dist/`.

## Цели

1. Стабилизировать Ansible runtime до широкой реструктуризации репозитория
2. Разделить topology-derived inventory, manual overrides и secret-bearing values
3. Сохранить рабочий `deploy/` workflow на всем пути миграции
4. Подготовить базу для ADR 0052 без смешивания решений

## Что не входит в этот план

Этот план не делает:
- перенос manual source в `src/`
- ввод `dist/` deploy packages
- переименование device ID
- Terraform/bootstrap package assembly

## Принципы

1. Не ломать `ansible/` как runtime root, пока cutover не завершен
2. Сначала определить ownership inventory данных, потом менять путь исполнения
3. Не переносить секреты механически вместе с inventory файлами
4. Не принимать ADR как `Accepted`, пока assembled runtime inventory не станет каноническим

## Базовый validation gate

```bash
git status
python3 topology-tools/regenerate-all.py
cd deploy && make validate
ansible-inventory -i generated/ansible/inventory/production --list > /dev/null
```

---

## Phase 0: Подготовка

### Что делаем

1. Создаем ветку миграции
2. Проверяем baseline
3. Фиксируем текущие runtime-контракты

### Runtime-контракты

- `deploy/phases/*.sh`
- `deploy/Makefile`
- `ansible/ansible.cfg`
- `topology-tools/regenerate-all.py`

### Команды

```bash
git checkout -b refactor/adr-0051-ansible-runtime
python3 topology-tools/regenerate-all.py
cd deploy && make validate
```

---

## Phase 1: Аудит inventory и секретов

### Что делаем

1. Инвентаризируем значения в `ansible/inventory/production/`
2. Делим их на три класса:
   - topology-derived
   - manual non-secret override
   - secret-local / vault-managed
3. Фиксируем список tracked secret violations

### Важно

- не менять `ansible.cfg`
- не переносить playbooks и roles
- не трогать `deploy/phases/*.sh`
- не смешивать эту фазу с `src/` migration

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
cd deploy && make validate
```

### Коммит

```text
docs(adr-0051): classify ansible inventory ownership and secret boundaries
```

---

## Phase 2: Ввести `ansible/inventory-overrides/` и вынести секреты

### Что делаем

1. Создаем `ansible/inventory-overrides/production/`
2. Переносим туда tracked manual non-secret vars
3. Переносим secret-bearing values в vault-managed local files или `.example` шаблоны
4. Оставляем legacy inventory переходным источником только до cutover

### Правила

1. topology-derived host structure не копируется вручную в overrides
2. tracked overrides не содержат raw secrets
3. секреты допускаются только в local-only или vault-managed путях

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
ansible-inventory -i generated/ansible/inventory/production --list > /dev/null
git grep -n "password\\|token\\|private_key\\|root_password_hash" ansible/inventory/production ansible/inventory-overrides
```

### Коммит

```text
refactor(adr-0051): separate ansible overrides from tracked secret values
```

---

## Phase 3: Реализовать assembled runtime inventory

### Что делаем

1. Создаем `topology-tools/assemble-ansible-runtime.py`
2. Собираем effective runtime inventory в `generated/ansible/runtime/production/`
3. Используем layered files:
   - `10-generated.yml`
   - `90-manual.yml`
4. Копируем manual `host_vars/*.yml` как overlays

### Assembler обязан падать, если

- нет generated inventory input
- нет обязательного override input, объявленного как required
- runtime inventory содержит raw secret values из tracked source

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
python3 topology-tools/assemble-ansible-runtime.py
ansible-inventory -i generated/ansible/runtime/production --list > /dev/null
```

### Коммит

```text
feat(adr-0051): add ansible runtime inventory assembler
```

---

## Phase 4: Переключить runtime на assembled inventory

### Что делаем

1. Обновляем `ansible/ansible.cfg`
2. Обновляем `deploy/phases/03-services.sh`
3. Обновляем runbook'и, которые ссылаются на raw inventory path
4. Делаем assembled runtime inventory каноническим для операторов

### Validation gate

```bash
python3 topology-tools/assemble-ansible-runtime.py
ansible-inventory -i generated/ansible/runtime/production --list > /dev/null
cd deploy && make validate
```

### Коммит

```text
refactor(adr-0051): switch ansible runtime to assembled inventory
```

---

## Phase 5: Удалить legacy manual inventory coupling

### Условия входа

1. assembled runtime inventory работает
2. `ansible.cfg` и `deploy/` уже используют его
3. documentation уже обновлена

### Что можно удалять

- tracked manual inventory files, замененные override/source split
- временные compatibility shims вокруг inventory

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
python3 topology-tools/assemble-ansible-runtime.py
cd deploy && make validate
git grep -n "ansible/inventory/production" -- . ":(exclude)Migrated_and_archived"
```

### Коммит

```text
refactor(adr-0051): remove legacy manual inventory coupling
```

---

## Phase 6: Принять ADR

ADR можно переводить в `Accepted` только после того, как:

1. assembled runtime inventory реально используется
2. tracked inventory больше не несет raw secrets
3. documentation соответствует реальному workflow
4. репозиторий готов к ADR 0052

### Коммит

```text
docs(adr-0051): accept ADR after successful cutover
```

## Критерии завершения

1. topology-derived inventory отделен от manual overrides
2. tracked secrets выведены из inventory source
3. effective runtime inventory собирается детерминированно
4. `deploy/` и `ansible.cfg` используют assembled runtime inventory
5. репозиторий готов к ADR 0052
