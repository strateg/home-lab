# ADR 0051: Migration Plan

План миграции к новой структуре с сохранением git history.

## Принципы миграции

1. Использовать `git mv` для сохранения истории
2. Выполнять атомарные коммиты по фазам
3. Обновлять ссылки в коде после каждой фазы
4. Не ломать существующий workflow до завершения

---

## Phase 0: Подготовка

```bash
# Убедиться что working tree чистый
git status

# Создать ветку миграции
git checkout -b refactor/adr-0051-build-pipeline

# Обновить .gitignore
cat >> .gitignore << 'EOF'

# ADR 0051: Build pipeline
dist/
EOF

git add .gitignore
git commit -m "chore: prepare for ADR 0051 migration

Add dist/ to .gitignore"
```

---

## Phase 1: Создание структуры `src/`

```bash
# Создать директории
mkdir -p src/ansible
mkdir -p src/bootstrap
mkdir -p src/configs
mkdir -p src/scripts

git add src/
git commit -m "chore(adr-0051): create src/ directory structure"
```

---

## Phase 2: Миграция Ansible

### 2.1 Playbooks и Roles (просто перемещаем)

```bash
# Переместить playbooks
git mv ansible/playbooks src/ansible/playbooks

# Переместить roles
git mv ansible/roles src/ansible/roles

# Переместить вспомогательные файлы
git mv ansible/requirements.yml src/ansible/requirements.yml
git mv ansible/vault-helper.sh src/ansible/vault-helper.sh

# Переместить group_vars (общие, не inventory-specific)
git mv ansible/group_vars src/ansible/group_vars

git commit -m "refactor(adr-0051): move ansible playbooks, roles to src/

- src/ansible/playbooks/ - all playbooks
- src/ansible/roles/ - all roles
- src/ansible/group_vars/ - vault and common vars
- src/ansible/requirements.yml - galaxy requirements"
```

### 2.2 Manual Inventory Config

```bash
# Создать директорию для manual inventory config
mkdir -p src/ansible/inventory-config/group_vars
mkdir -p src/ansible/inventory-config/host_vars

# Переместить manual group_vars (богатая конфигурация)
git mv ansible/inventory/production/group_vars/all.yml \
       src/ansible/inventory-config/group_vars/all.yml

# Удалить остатки manual inventory (hosts.yml будет generated)
# ВАЖНО: hosts.yml дублирует generated, удаляем
git rm ansible/inventory/production/hosts.yml

# Удалить пустые директории
rmdir ansible/inventory/production/group_vars 2>/dev/null || true
rmdir ansible/inventory/production 2>/dev/null || true
rmdir ansible/inventory/host_vars 2>/dev/null || true
rmdir ansible/inventory/group_vars 2>/dev/null || true
rmdir ansible/inventory 2>/dev/null || true

git commit -m "refactor(adr-0051): consolidate ansible inventory config

- src/ansible/inventory-config/group_vars/all.yml - manual rich config
- Remove duplicate hosts.yml (use generated version)
- Generated inventory remains in generated/ansible/inventory/"
```

### 2.3 Удалить пустую ansible/

```bash
# Проверить что ansible/ пуста
ls -la ansible/

# Если пуста - удалить
rmdir ansible 2>/dev/null || echo "ansible/ not empty, check contents"

git commit -m "refactor(adr-0051): remove empty ansible/ directory" --allow-empty
```

---

## Phase 3: Миграция Bootstrap Scripts

### 3.1 MikroTik Bootstrap

```bash
# Переместить manual MikroTik scripts
git mv bootstrap/mikrotik src/bootstrap/mikrotik

git commit -m "refactor(adr-0051): move mikrotik bootstrap to src/

Manual scripts:
- src/bootstrap/mikrotik/bootstrap.rsc
- src/bootstrap/mikrotik/exported_config.rsc
- src/bootstrap/mikrotik/exported_config_safe.rsc

Note: init-terraform.rsc duplicates generated version, will be removed"
```

### 3.2 Удалить дубликат init-terraform.rsc

```bash
# init-terraform.rsc генерируется в generated/bootstrap/rtr-mikrotik-chateau/
# Удалить manual версию
git rm src/bootstrap/mikrotik/init-terraform.rsc

git commit -m "refactor(adr-0051): remove duplicate init-terraform.rsc

Use generated version: generated/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc"
```

### 3.3 Proxmox Bare-Metal

```bash
# Переместить bare-metal scripts
git mv manual-scripts/bare-metal src/bootstrap/proxmox

git commit -m "refactor(adr-0051): move proxmox bare-metal to src/bootstrap/

- src/bootstrap/proxmox/create-uefi-autoinstall-proxmox-usb.sh
- src/bootstrap/proxmox/answer.toml
- src/bootstrap/proxmox/post-install/
- src/bootstrap/proxmox/docs/"
```

### 3.4 Orange Pi 5

```bash
# Переместить OPi5 scripts
git mv manual-scripts/opi5 src/bootstrap/opi5

git commit -m "refactor(adr-0051): move opi5 scripts to src/bootstrap/"
```

### 3.5 OpenWRT Scripts

```bash
# Переместить OpenWRT scripts
git mv manual-scripts/openwrt src/bootstrap/openwrt

git commit -m "refactor(adr-0051): move openwrt scripts to src/bootstrap/"
```

### 3.6 Очистить manual-scripts/

```bash
# Проверить что осталось
ls -la manual-scripts/

# Удалить архив если не нужен
git rm -r manual-scripts/archive 2>/dev/null || true

# Logger - утилита, переместить в scripts
git mv manual-scripts/claude-logger.py src/scripts/claude-logger.py
git mv manual-scripts/requirements-logger.txt src/scripts/requirements-logger.txt
git mv manual-scripts/LOGGER-README.md src/scripts/LOGGER-README.md

# Удалить пустую директорию
rmdir manual-scripts 2>/dev/null || true

git commit -m "refactor(adr-0051): consolidate manual-scripts/

- Logger utility moved to src/scripts/
- Archive removed
- manual-scripts/ directory removed"
```

---

## Phase 4: Миграция Configs

```bash
# Переместить configs
git mv configs src/configs

git commit -m "refactor(adr-0051): move configs to src/

- src/configs/glinet/ - GL.iNet router configs
- src/configs/vpn/ - VPN configurations
- src/configs/services/ - service configs"
```

---

## Phase 5: Миграция Scripts

```bash
# Переместить utility scripts
git mv scripts/fix_whitespace.py src/scripts/fix_whitespace.py
git mv scripts/*.cmd src/scripts/ 2>/dev/null || true

# Удалить пустую директорию
rmdir scripts 2>/dev/null || true

git commit -m "refactor(adr-0051): move utility scripts to src/scripts/"
```

---

## Phase 6: Удалить пустую bootstrap/

```bash
# Проверить
ls -la bootstrap/

# Удалить README если есть
git rm bootstrap/mikrotik/README.md 2>/dev/null || true

# Удалить пустые директории
rmdir bootstrap/mikrotik 2>/dev/null || true
rmdir bootstrap 2>/dev/null || true

git commit -m "refactor(adr-0051): remove empty bootstrap/ directory"
```

---

## Phase 7: Удалить дубликат MikroTik device

```bash
# Удалить дубликат (оставить rtr-mikrotik-chateau.yaml)
git rm topology/L1-foundation/devices/owned/network/mikrotik-chateau.yaml

git commit -m "fix(topology): remove duplicate mikrotik-chateau.yaml

Keep rtr-mikrotik-chateau.yaml as canonical (follows naming convention)"
```

---

## Phase 8: Обновить ссылки в коде

### 8.1 Обновить deploy/Makefile

```bash
# Обновить пути в Makefile
# (потребуется редактирование)
```

### 8.2 Обновить CLAUDE.md

```bash
# Обновить документацию структуры
# (потребуется редактирование)
```

### 8.3 Обновить .github/workflows (если есть)

```bash
# Обновить CI пути
```

```bash
git add -A
git commit -m "docs(adr-0051): update references to new src/ structure"
```

---

## Phase 9: Создать Assembler

```bash
# Создать assembler script
cat > topology-tools/assemble-deploy.py << 'EOF'
#!/usr/bin/env python3
"""Assemble deploy packages from generated + src."""
# TODO: Implement based on ADR 0051
pass
EOF

chmod +x topology-tools/assemble-deploy.py

git add topology-tools/assemble-deploy.py
git commit -m "feat(adr-0051): add deploy package assembler skeleton"
```

---

## Phase 10: Финализация

```bash
# Обновить ADR статус
sed -i 's/Status: Proposed/Status: Accepted/' adr/0051-build-pipeline-and-deploy-packages.md

# Обновить дату
sed -i 's/Date: 2026-03-01/Date: 2026-03-01 (Accepted)/' adr/0051-build-pipeline-and-deploy-packages.md

git add adr/
git commit -m "docs(adr-0051): accept ADR after migration complete"

# Merge в main
git checkout main
git merge refactor/adr-0051-build-pipeline
```

---

## Итоговая структура после миграции

```
home-lab/
├── topology/                      # L0-L7 (без изменений)
├── topology-tools/                # Generators (без изменений)
│   └── assemble-deploy.py         # NEW
│
├── src/                           # NEW: All manual sources
│   ├── ansible/
│   │   ├── playbooks/             # ← ansible/playbooks/
│   │   ├── roles/                 # ← ansible/roles/
│   │   ├── group_vars/            # ← ansible/group_vars/
│   │   ├── inventory-config/      # ← ansible/inventory/production/group_vars/
│   │   │   └── group_vars/
│   │   │       └── all.yml
│   │   ├── requirements.yml       # ← ansible/requirements.yml
│   │   └── vault-helper.sh        # ← ansible/vault-helper.sh
│   │
│   ├── bootstrap/
│   │   ├── mikrotik/              # ← bootstrap/mikrotik/
│   │   │   ├── bootstrap.rsc
│   │   │   ├── exported_config.rsc
│   │   │   └── exported_config_safe.rsc
│   │   ├── proxmox/               # ← manual-scripts/bare-metal/
│   │   │   ├── create-uefi-autoinstall-proxmox-usb.sh
│   │   │   ├── answer.toml
│   │   │   ├── post-install/
│   │   │   └── docs/
│   │   ├── opi5/                  # ← manual-scripts/opi5/
│   │   │   └── install.sh
│   │   └── openwrt/               # ← manual-scripts/openwrt/
│   │
│   ├── configs/                   # ← configs/
│   │   ├── glinet/
│   │   ├── vpn/
│   │   └── services/
│   │
│   └── scripts/                   # ← scripts/ + manual-scripts/*.py
│       ├── claude-logger.py
│       ├── fix_whitespace.py
│       └── *.cmd
│
├── generated/                     # (без изменений)
│   ├── terraform/
│   ├── ansible/inventory/
│   ├── bootstrap/
│   └── docs/
│
├── dist/                          # NEW: Deploy packages (gitignored)
│
├── deploy/                        # (без изменений)
├── tests/                         # (без изменений)
├── docs/                          # (без изменений)
└── adr/                           # (без изменений)
```

---

## Удалённые директории

| Старый путь | Причина |
|-------------|---------|
| `ansible/` | Перемещено в `src/ansible/` |
| `bootstrap/` | Перемещено в `src/bootstrap/` |
| `manual-scripts/` | Перемещено в `src/bootstrap/` и `src/scripts/` |
| `configs/` | Перемещено в `src/configs/` |
| `scripts/` | Перемещено в `src/scripts/` |

## Удалённые файлы (дубликаты)

| Файл | Причина |
|------|---------|
| `ansible/inventory/production/hosts.yml` | Дубликат generated версии |
| `bootstrap/mikrotik/init-terraform.rsc` | Дубликат generated версии |
| `topology/L1-foundation/devices/owned/network/mikrotik-chateau.yaml` | Дубликат rtr-mikrotik-chateau.yaml |

---

## Команды для выполнения (копипаст)

```bash
#!/bin/bash
# Full migration script
set -e

echo "=== Phase 0: Preparation ==="
git checkout -b refactor/adr-0051-build-pipeline
echo "dist/" >> .gitignore
git add .gitignore
git commit -m "chore: prepare for ADR 0051 migration"

echo "=== Phase 1: Create src/ structure ==="
mkdir -p src/ansible src/bootstrap src/configs src/scripts
git add src/
git commit -m "chore(adr-0051): create src/ directory structure" --allow-empty

echo "=== Phase 2: Migrate Ansible ==="
git mv ansible/playbooks src/ansible/playbooks
git mv ansible/roles src/ansible/roles
git mv ansible/requirements.yml src/ansible/requirements.yml
git mv ansible/vault-helper.sh src/ansible/vault-helper.sh
git mv ansible/group_vars src/ansible/group_vars
git commit -m "refactor(adr-0051): move ansible playbooks, roles to src/"

mkdir -p src/ansible/inventory-config/group_vars
mkdir -p src/ansible/inventory-config/host_vars
git mv ansible/inventory/production/group_vars/all.yml src/ansible/inventory-config/group_vars/all.yml
git rm ansible/inventory/production/hosts.yml
git commit -m "refactor(adr-0051): consolidate ansible inventory config"

echo "=== Phase 3: Migrate Bootstrap ==="
git mv bootstrap/mikrotik src/bootstrap/mikrotik
git commit -m "refactor(adr-0051): move mikrotik bootstrap to src/"

git rm src/bootstrap/mikrotik/init-terraform.rsc
git commit -m "refactor(adr-0051): remove duplicate init-terraform.rsc"

git mv manual-scripts/bare-metal src/bootstrap/proxmox
git commit -m "refactor(adr-0051): move proxmox bare-metal to src/bootstrap/"

git mv manual-scripts/opi5 src/bootstrap/opi5
git commit -m "refactor(adr-0051): move opi5 scripts to src/bootstrap/"

git mv manual-scripts/openwrt src/bootstrap/openwrt
git commit -m "refactor(adr-0051): move openwrt scripts to src/bootstrap/"

git mv manual-scripts/claude-logger.py src/scripts/
git mv manual-scripts/requirements-logger.txt src/scripts/
git mv manual-scripts/LOGGER-README.md src/scripts/
git rm -r manual-scripts/archive 2>/dev/null || true
git commit -m "refactor(adr-0051): consolidate manual-scripts/"

echo "=== Phase 4: Migrate Configs ==="
git mv configs src/configs
git commit -m "refactor(adr-0051): move configs to src/"

echo "=== Phase 5: Migrate Scripts ==="
git mv scripts/fix_whitespace.py src/scripts/
git mv scripts/*.cmd src/scripts/ 2>/dev/null || true
git commit -m "refactor(adr-0051): move utility scripts to src/scripts/"

echo "=== Phase 6: Cleanup ==="
# Remove empty directories (git doesn't track them)

echo "=== Phase 7: Remove MikroTik duplicate ==="
git rm topology/L1-foundation/devices/owned/network/mikrotik-chateau.yaml
git commit -m "fix(topology): remove duplicate mikrotik-chateau.yaml"

echo "=== Migration complete ==="
echo "Next steps:"
echo "1. Update deploy/Makefile paths"
echo "2. Update CLAUDE.md documentation"
echo "3. Create assembler script"
echo "4. Test regeneration"
```
