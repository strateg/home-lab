# Generated Directory - Quick Guide

## 🎯 Главный принцип

```
✏️  РЕДАКТИРУЙ:  topology.yaml
⚠️  НЕ ТРОГАЙ:   generated/*
```

---

## 📁 Структура

```
new_system/
├── topology.yaml           # ✏️  ИСТОЧНИК ИСТИНЫ - редактируй это
├── .gitignore              # Игнорирует generated/
├── generated/              # ⚠️  АВТО-ГЕНЕРАЦИЯ - НЕ РЕДАКТИРУЙ!
│   ├── terraform/
│   ├── ansible/
│   │   ├── inventory/
│   │   │   └── production/
│   │   └── runtime/
│   │       └── production/
│   └── docs/
├── ansible/
│   ├── playbooks/          # ✏️  Ручная логика playbooks
│   └── roles/              # ✏️  Ручные роли
└── scripts/
    └── regenerate-all.py   # ⭐ ГЛАВНАЯ КОМАНДА
```

---

## ⚡ Быстрый старт

### Регенерировать всё (рекомендуется)

```bash
python3 topology-tools/regenerate-all.py
```

Эта одна команда:
1. Очищает `generated/`
2. Валидирует `topology.yaml`
3. Генерирует Terraform baseline → `generated/terraform/`
4. Генерирует Ansible inventory input → `generated/ansible/inventory/<env>/`
5. Собирает runtime inventory → `generated/ansible/runtime/production/`
6. Генерирует документацию → `generated/docs/`

**Время**: ~1 секунда

---

## 🔄 Рабочий процесс

### 1. Редактируй topology.yaml

```bash
vim topology.yaml
# Добавил новый LXC контейнер, изменил IP, и т.д.
```

### 2. Регенерируй

```bash
python3 topology-tools/regenerate-all.py
```

### 3. Просмотри изменения

```bash
cd deploy && make assemble-native && cd ..
cd .work/native/terraform/proxmox
terraform plan
```

### 4. Примени

```bash
terraform apply
```

**Вот и всё!** 🎉

---

## 📝 Индивидуальные генераторы

Если нужно сгенерировать только одну часть:

```bash
# Только Terraform baseline
python3 topology-tools/generate-terraform-proxmox.py
python3 topology-tools/generate-terraform-mikrotik.py

# Только Ansible
python3 topology-tools/generate-ansible-inventory.py

# Только документация
python3 topology-tools/generate-docs.py
```

**Каждый генератор автоматически очищает свою директорию!**

---

## ⚠️ Важные правила

### ❌ НЕ ДЕЛАЙ

1. **НЕ редактируй файлы в `generated/`**
   - Они перезаписываются при каждой генерации
   - Все изменения будут потеряны

2. **НЕ коммить `generated/` в Git**
   - Уже в `.gitignore`
   - Эти файлы генерируются из `topology.yaml`

3. **НЕ удаляй `generated/` вручную**
   - Генераторы сами очищают директорию
   - Но можно удалить, если нужно (безопасно)

### ✅ ДЕЛАЙ

1. **Редактируй `topology.yaml`**
   - Единственный источник истины

2. **Запускай `regenerate-all.py`**
   - После каждого изменения topology.yaml

3. **Редактируй `ansible/playbooks/` и `ansible/roles/`**
   - Эти файлы ручные, не генерируются

4. **Коммить только исходники**
   - `topology.yaml` ✅
   - `scripts/` ✅
   - `ansible/playbooks/` ✅
   - `generated/` ❌

---

## 🧹 Автоматическая очистка

При запуске генератора:

```bash
python3 topology-tools/generate-terraform-proxmox.py

# Вывод:
🧹 Cleaning output directory: generated/terraform/proxmox
📁 Created output directory: generated/terraform/proxmox
✓ Generated: generated/terraform/proxmox/provider.tf
...
```

**Старые файлы удаляются автоматически!**

Никаких "мертвых" файлов, всегда свежая генерация.

---

## 📦 Что находится в `generated/`

### Terraform (6 файлов)

```
generated/terraform/
├── mikrotik/                   # Baseline RouterOS Terraform
└── proxmox/                    # Baseline Proxmox Terraform

.work/native/terraform/
├── mikrotik/                   # Native execution root after assemble-native
└── proxmox/                    # Native execution root after assemble-native
```

### Ansible (1 + 4 + 3 файла)

```
generated/ansible/
├── inventory/production/
│   ├── hosts.yml               # Topology-derived inventory input
│   └── group_vars/all.yml
└── runtime/production/
    ├── hosts.yml               # Operator-facing runtime inventory
    └── group_vars/all/
        ├── 10-generated.yml
        └── 90-manual.yml
```

### Документация (5 файлов)

```
generated/docs/
├── overview.md                 # Обзор инфраструктуры
├── network-diagram.md          # Диаграмма сети (Mermaid)
├── ip-allocation.md            # Таблица IP адресов
├── services.md                 # Инвентарь сервисов
└── devices.md                  # Устройства (физ, VM, LXC)
```

**Всего**: 15 файлов

---

## 🚀 Примеры использования

### После git clone

```bash
git clone <repo>
cd home-lab/new_system

# Директория generated/ НЕТ в репозитории
ls generated
# bash: ls: cannot access 'generated': No such file or directory

# Сгенерировать из topology.yaml
python3 topology-tools/regenerate-all.py

# Теперь есть!
ls generated
# ansible/  docs/  terraform/
```

---

### Изменить IP адрес

```bash
# 1. Редактировать topology.yaml
vim topology.yaml
# Изменил IP PostgreSQL: 10.0.30.10 → 10.0.30.15

# 2. Регенерировать
python3 topology-tools/regenerate-all.py

# 3. Проверить изменения
cd deploy && make assemble-native && cd ..
cd .work/native/terraform/proxmox
terraform plan
# Plan: 1 to change (IP address)

# 4. Применить
terraform apply
```

---

### Добавить новый LXC контейнер

```bash
# 1. Добавить в topology.yaml
vim topology.yaml
# Добавил:
# - id: lxc-monitoring
#   name: monitoring
#   ...

# 2. Регенерировать всё
python3 topology-tools/regenerate-all.py

# Результат:
# ✓ Generated: generated/terraform/lxc.tf (4 containers)  ← было 3
# ✓ Generated: hosts.yml (4 LXC containers)               ← было 3

# 3. Terraform создаст новый контейнер
cd deploy && make assemble-native && cd ..
cd .work/native/terraform/proxmox
terraform plan
# Plan: 1 to add (lxc-monitoring)

terraform apply
```

---

## 🔍 Troubleshooting

### "generated/ не создается"

```bash
# Проверь, что скрипт запускается
python3 topology-tools/regenerate-all.py

# Если ошибка валидации - исправь topology.yaml
python3 topology-tools/validate-topology.py
```

---

### "Файлы в неправильной структуре"

```bash
# Очисти только managed generated roots и регенерируй
python3 topology-tools/clean-generated.py
python3 topology-tools/regenerate-all.py
```

---

### "Изменения в generated/ потерялись"

**Это ожидаемое поведение!**

- ❌ НЕ редактируй `generated/`
- ✅ Редактируй `topology.yaml`
- ✅ Запускай `regenerate-all.py`

---

## 📚 Дополнительная документация

- **Полная документация**: `topology-tools/GENERATORS-README.md`
- **Changelog**: `CHANGELOG-GENERATED-DIR.md`
- **Topology v2.0**: `topology.yaml`
- **Валидация**: `python3 topology-tools/validate-topology.py`

---

## ✅ Checklist для работы

- [ ] Отредактировал `topology.yaml`
- [ ] Запустил `python3 topology-tools/regenerate-all.py`
- [ ] Проверил `terraform plan` в `.work/native/terraform/<target>/`
- [ ] Применил изменения с `terraform apply`
- [ ] Запустил Ansible (если нужно)
- [ ] Закоммитил **только** `topology.yaml` (не `generated/`)

---

**Главное правило**: `topology.yaml` → `regenerate-all.py` → `generated/` → profit! 🚀

---

**Дата**: 2025-10-10
**Версия**: 1.0
