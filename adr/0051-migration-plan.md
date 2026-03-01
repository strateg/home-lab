# ADR 0051: Migration Plan

План миграции к безопасной Ansible-first модели без преждевременного перехода к `src/` и `dist/`.

## Current State Analysis (2026-03-01)

### Inventory Sources

| Source | Path | Hosts | Status |
|--------|------|-------|--------|
| Manual | `ansible/inventory/production/` | 11 hosts | Operational |
| Generated | `generated/ansible/inventory/production/` | 2 hosts | Partial |
| Runtime (target) | `generated/ansible/runtime/production/` | TBD | Not exists |

### Data Classification (Manual Inventory)

**tracked-public** (→ inventory-overrides):
- Hardware specs: `hardware.*`
- Service lists: `services: []`
- Network configs: `network.*`, `vpn_servers.*`
- SSH settings: `ssh_*`, `ansible_*`
- Admin users (без ключей)
- Package lists, monitoring, backup config

**local-secret** (→ .gitignore или vault):
- SSH key lookups: `{{ lookup('file', '~/.ssh/...') }}`

### Key Finding

Topology содержит только 2 LXC хоста (postgresql, redis). Остальные 9 хостов в manual inventory не имеют topology representation. Это означает что manual inventory временно является authoritative для hosts structure, пока topology не будет дополнена.

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
4. Определяем hosts, которые еще существуют только в legacy manual inventory
5. Добавляем missing durable hosts в topology как prerequisite до cutover

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
2. Инвентаризируем generated `group_vars` и `host_vars`
3. Делим их на три класса:
   - topology-derived
   - manual non-secret override
   - secret-local / vault-managed
4. Фиксируем список tracked secret violations
5. Для каждого значения определяем owner и целевой путь после миграции
6. Отдельно помечаем legacy inventory values, которые:
   - уже противоречат topology
   - должны генерироваться
   - описывают hosts, отсутствующие в topology

### Concrete File Analysis

**ansible/inventory/production/hosts.yml** (309 lines):
```yaml
# tracked-public (keep in overrides):
all.vars.ansible_python_interpreter     # operator preference
all.vars.ansible_ssh_common_args        # operator preference
all.vars.environment_name               # operator config
all.vars.datacenter                     # operator config
all.vars.dns_servers                    # operator config
all.vars.ntp_servers                    # operator config
proxmox.hosts.pve-xps.*                 # full host (not in topology)
vms.children.firewalls.hosts.*          # full host (not in topology)
routers.children.openwrt.hosts.*        # full host (not in topology)
lxc.vars.*                              # operator defaults
lxc.children.*.hosts.*                  # full hosts (partial in topology)
```

**ansible/inventory/production/group_vars/all.yml** (214 lines):
```yaml
# tracked-public (keep in overrides):
environment, datacenter, timezone       # operator config
dns_nameservers, ntp_servers            # operator config
domain_name, search_domains             # operator config
ssh_port, ssh_permit_root_login         # operator security policy
firewall_*, fail2ban_*                  # operator security policy
node_exporter_*, log_level              # operator monitoring
backup_storage, backup_path             # operator backup
backup_retention, backup_schedule       # operator backup
common_packages                         # operator packages
swap_*, file_descriptor_limit           # operator tuning
services                                # service registry
default_tags, features                  # operator config

# local-secret (remove or vault):
admin_users[*].ssh_keys with lookup()   # secret reference
```

### Secret Violations Found

1. **Line 46**: `ssh_keys: - "{{ lookup('file', '~/.ssh/id_rsa.pub') }}"`
   - Action: Replace with vault-managed or `.example` placeholder

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

## Phase 2: Минимизировать `inventory-overrides/` и вынести секреты

### Что делаем

1. Создаем `ansible/inventory-overrides/production/`
2. Переносим туда только tracked manual non-secret vars, которые действительно являются operator preferences или временными исключениями
3. Переносим secret-bearing values в vault-managed local files или `.example` шаблоны
4. Оставляем legacy inventory переходным источником только до cutover

### Concrete Operations

```bash
# Create directory structure
mkdir -p ansible/inventory-overrides/production/group_vars
mkdir -p ansible/inventory-overrides/production/host_vars

# Move hosts.yml (contains full host definitions not in topology)
git mv ansible/inventory/production/hosts.yml \
       ansible/inventory-overrides/production/hosts.yml

# Split group_vars/all.yml
# 1. Create all.yml without secret lookups
# 2. Create all.yml.example with placeholder for secrets
```

**New file: ansible/inventory-overrides/production/group_vars/all.yml**
```yaml
# Operator overrides for all hosts
# These values extend/override generated inventory

# Environment
environment: production
datacenter: home-lab
timezone: UTC

# DNS (overrides generated dns_servers)
dns_nameservers:
  - 192.168.20.1    # AdGuard Home
  - 1.1.1.1         # Cloudflare

# ... (rest of non-secret config)
```

**New file: ansible/inventory-overrides/production/group_vars/all.yml.example**
```yaml
# Local secrets - copy to all-secrets.yml and fill in values
# all-secrets.yml is gitignored

admin_users:
  - name: admin
    ssh_keys:
      - "ssh-rsa AAAA... your-key-here"
```

**Add to .gitignore:**
```
ansible/inventory-overrides/production/group_vars/all-secrets.yml
```

### Правила

1. topology-derived host structure не копируется вручную в overrides
2. tracked overrides не содержат raw secrets
3. секреты допускаются только в local-only или vault-managed путях
4. generated `host_vars` не переопределяются молча через manual override с тем же именем
5. если intentional override нужен, это должно быть явно зафиксировано в assembler policy
6. стабильные service facts вроде `ansible_user`, `service_port`, `cores` и `ram` не должны жить в overrides для topology-owned hosts

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
ansible-inventory -i generated/ansible/inventory/production --list > /dev/null
git grep -n "password\\|token\\|private_key\\|root_password_hash\\|lookup.*file" ansible/inventory-overrides
# Must return 0 results
```

### Коммит

```text
refactor(adr-0051): separate ansible overrides from tracked secret values
```

---

## Phase 3: Расширить generator для topology-owned service runtime

### Что делаем

1. Выбираем canonical inventory hostname scheme на основе topology IDs
2. Дорабатываем generator так, чтобы topology-owned hosts получали runtime facts из topology
3. Для first-party LXC сервисов выводим как минимум:
   - `ansible_user`
   - `service_port`
   - resource profile values, например `cores` и `ram`
   - service group membership
   - playbook binding metadata
4. Убираем зависимость нормального runtime от legacy handwritten service facts

### Минимальный ожидаемый результат

1. `lxc-postgresql` и `lxc-redis` больше не зависят от tracked manual inventory для нормальной работы
2. generated inventory уже несет нужные service facts для playbook routing
3. `inventory-overrides` не используется как постоянный источник model data

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
ansible-inventory -i generated/ansible/inventory/production --list > /dev/null
```

### Коммит

```text
feat(adr-0051): generate topology-owned ansible runtime facts
```

---

## Phase 4: Реализовать assembled runtime inventory

### Что делаем

1. Создаем `topology-tools/assemble-ansible-runtime.py`
2. Собираем effective runtime inventory в `generated/ansible/runtime/production/`
3. Используем layered files:
   - `10-generated.yml`
   - `90-manual.yml`
4. Копируем generated `host_vars/*.yml`
5. Копируем manual `host_vars/*.yml` как overlays по явному правилу конфликтов

### Assembler Implementation

**File: topology-tools/assemble-ansible-runtime.py**

```python
#!/usr/bin/env python3
"""Assemble Ansible runtime inventory from generated and manual sources."""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
GENERATED_INV = REPO_ROOT / "generated/ansible/inventory/production"
MANUAL_INV = REPO_ROOT / "ansible/inventory-overrides/production"
RUNTIME_INV = REPO_ROOT / "generated/ansible/runtime/production"

# Secrets that must NOT appear in tracked source
SECRET_PATTERNS = [
    "password:", "token:", "private_key:", "root_password_hash:",
    "lookup('file'", 'lookup("file'
]

def validate_no_secrets(path: Path) -> list[str]:
    """Check file for secret patterns."""
    violations = []
    for pattern in SECRET_PATTERNS:
        if pattern in path.read_text():
            violations.append(f"{path}: contains '{pattern}'")
    return violations

def assemble():
    # Clean and create output
    if RUNTIME_INV.exists():
        shutil.rmtree(RUNTIME_INV)
    RUNTIME_INV.mkdir(parents=True)

    # 1. Copy generated hosts.yml
    shutil.copy(GENERATED_INV / "hosts.yml", RUNTIME_INV / "hosts.yml")

    # 2. Merge hosts from manual overrides (hosts not in topology)
    # TODO: implement YAML merge for hosts

    # 3. Create layered group_vars
    group_vars = RUNTIME_INV / "group_vars/all"
    group_vars.mkdir(parents=True)

    # Generated becomes 10-generated.yml
    shutil.copy(
        GENERATED_INV / "group_vars/all.yml",
        group_vars / "10-generated.yml"
    )

    # Manual becomes 90-manual.yml
    if (MANUAL_INV / "group_vars/all.yml").exists():
        shutil.copy(
            MANUAL_INV / "group_vars/all.yml",
            group_vars / "90-manual.yml"
        )

    # 4. Copy host_vars (generated first, then manual overlays)
    # ...

    print(f"Assembled runtime inventory: {RUNTIME_INV}")

if __name__ == "__main__":
    assemble()
```

### Assembler обязан падать, если

- нет generated inventory input
- нет обязательного override input, объявленного как required
- runtime inventory содержит raw secret values из tracked source
- manual `host_vars` конфликтуют с generated `host_vars` без explicit allowlist

## Phase 4.5: Dry-Run Comparison

До cutover нужно параллельно сравнить old и new runtime inventory.

Сравниваем:
1. список хостов
2. список групп
3. selected vars для 2-3 эталонных хостов
4. topology-owned service facts для `lxc-postgresql` и `lxc-redis`

Если differences intentional, они должны быть явно задокументированы в коммите cutover.

### Validation gate

```bash
python3 topology-tools/regenerate-all.py
python3 topology-tools/assemble-ansible-runtime.py
ansible-inventory -i generated/ansible/runtime/production --list > /dev/null
ansible-inventory -i generated/ansible/inventory/production --list > old-inventory.json
ansible-inventory -i generated/ansible/runtime/production --list > new-inventory.json
```

### Коммит

```text
feat(adr-0051): add ansible runtime inventory assembler
```

---

## Phase 5: Переключить runtime на assembled inventory

### Что делаем

1. Обновляем `ansible/ansible.cfg`
2. Обновляем `deploy/phases/03-services.sh`
3. Обновляем runbook'и, которые ссылаются на raw inventory path
4. Делаем assembled runtime inventory каноническим для операторов
5. По возможности выносим inventory path в одно общее место конфигурации вместо дублирования

### Concrete Changes

**ansible/ansible.cfg** (line 9):
```diff
-inventory = ../generated/ansible/inventory/production/hosts.yml
+inventory = ../generated/ansible/runtime/production
```

Note: Changed from file to directory. Ansible will auto-discover hosts.yml and group_vars/.

**deploy/phases/03-services.sh** (if hardcoded):
```diff
-INVENTORY="../generated/ansible/inventory/production/hosts.yml"
+INVENTORY="../generated/ansible/runtime/production"
```

**deploy/Makefile** (add assemble step):
```makefile
assemble-ansible:
	python3 ../topology-tools/assemble-ansible-runtime.py

generate: validate
	python3 ../topology-tools/regenerate-all.py
	$(MAKE) assemble-ansible
```

### Validation gate

```bash
python3 topology-tools/assemble-ansible-runtime.py
ansible-inventory -i generated/ansible/runtime/production --list > /dev/null
cd deploy && make validate
cd ansible && ansible-playbook playbooks/common.yml --syntax-check
cd ansible && ansible-playbook playbooks/postgresql.yml --syntax-check
cd ansible && ansible-playbook playbooks/redis.yml --syntax-check
```

### Коммит

```text
refactor(adr-0051): switch ansible runtime to assembled inventory
```

---

## Phase 6: Удалить legacy manual inventory coupling

### Условия входа

1. assembled runtime inventory работает
2. `ansible.cfg` и `deploy/` уже используют его
3. documentation уже обновлена
4. dry-run comparison завершен и differences понятны

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

## Phase 7: Принять ADR

ADR можно переводить в `Accepted` только после того, как:

1. assembled runtime inventory реально используется
2. tracked inventory больше не несет raw secrets
3. documentation соответствует реальному workflow
4. репозиторий готов к ADR 0052

## Rollback

Если после Phase 5 runtime inventory вызывает регрессии:
1. вернуть `ansible/ansible.cfg` на previous inventory target
2. вернуть `deploy/phases/03-services.sh` на previous inventory target
3. не удалять legacy manual inventory files до прохождения Phase 6
4. зафиксировать rollback отдельным revertable commit

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

---

## Implementation Checklist

### Phase 1 Commands
```bash
git checkout -b refactor/adr-0051-ansible-runtime
python3 topology-tools/regenerate-all.py
cd deploy && make validate
# Document findings in this file
git add adr/0051-migration-plan.md
git commit -m "docs(adr-0051): classify ansible inventory ownership and secret boundaries"
```

### Phase 2 Commands
```bash
# Create directories
mkdir -p ansible/inventory-overrides/production/group_vars
mkdir -p ansible/inventory-overrides/production/host_vars

# Move hosts.yml
git mv ansible/inventory/production/hosts.yml \
       ansible/inventory-overrides/production/hosts.yml

# Split group_vars (manual: extract secrets)
# Create all.yml without lookup() calls
# Create all.yml.example with placeholders

# Add to .gitignore
echo "ansible/inventory-overrides/production/group_vars/all-secrets.yml" >> .gitignore

# Validate no secrets in tracked files
git grep -n "lookup.*file" ansible/inventory-overrides
# Should return empty

git add -A
git commit -m "refactor(adr-0051): separate ansible overrides from tracked secret values"
```

### Phase 3 Commands
```bash
# Create assembler
cat > topology-tools/assemble-ansible-runtime.py << 'EOF'
#!/usr/bin/env python3
# ... implementation ...
EOF
chmod +x topology-tools/assemble-ansible-runtime.py

# Test assembly
python3 topology-tools/assemble-ansible-runtime.py
ansible-inventory -i generated/ansible/runtime/production --list > /dev/null

git add topology-tools/assemble-ansible-runtime.py
git commit -m "feat(adr-0051): add ansible runtime inventory assembler"
```

### Phase 4 Commands
```bash
# Update ansible.cfg
sed -i 's|inventory = ../generated/ansible/inventory/production/hosts.yml|inventory = ../generated/ansible/runtime/production|' ansible/ansible.cfg

# Update Makefile
# Add assemble-ansible target

# Test
python3 topology-tools/assemble-ansible-runtime.py
cd ansible && ansible-playbook playbooks/common.yml --syntax-check

git add -A
git commit -m "refactor(adr-0051): switch ansible runtime to assembled inventory"
```

### Phase 5 Commands
```bash
# Remove legacy (only after Phase 4 verified)
rm -rf ansible/inventory/production/
rmdir ansible/inventory/ 2>/dev/null || true

git add -A
git commit -m "refactor(adr-0051): remove legacy manual inventory coupling"
```

### Phase 6 Commands
```bash
# Update ADR status
sed -i 's/Status: Proposed/Status: Accepted/' adr/0051-ansible-runtime-and-secrets.md

git add adr/0051-ansible-runtime-and-secrets.md
git commit -m "docs(adr-0051): accept ADR after successful cutover"
```
