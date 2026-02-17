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
│   │   └── inventory/
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
python3 scripts/regenerate-all.py
```

Эта одна команда:
1. Очищает `generated/`
2. Валидирует `topology.yaml`
3. Генерирует Terraform → `generated/terraform/`
4. Генерирует Ansible → `generated/ansible/`
5. Генерирует документацию → `generated/docs/`

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
python3 scripts/regenerate-all.py
```

### 3. Просмотри изменения

```bash
cd generated/terraform
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
# Только Terraform
python3 scripts/generate-terraform.py

# Только Ansible
python3 scripts/generate-ansible-inventory.py

# Только документация
python3 scripts/generate-docs.py
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
python3 scripts/generate-terraform.py

# Вывод:
🧹 Cleaning output directory: generated/terraform
📁 Created output directory: generated/terraform
✓ Generated: generated/terraform/provider.tf
...
```

**Старые файлы удаляются автоматически!**

Никаких "мертвых" файлов, всегда свежая генерация.

---

## 📦 Что находится в `generated/`

### Terraform (6 файлов)

```
generated/terraform/
├── provider.tf                 # Proxmox provider
├── bridges.tf                  # Сетевые мосты (4)
├── vms.tf                      # Виртуальные машины (1)
├── lxc.tf                      # LXC контейнеры (3)
├── variables.tf                # Переменные
└── terraform.tfvars.example    # Пример переменных
```

### Ansible (1 + 4 + 3 файла)

```
generated/ansible/inventory/production/
├── hosts.yml                   # Инвентарь
├── group_vars/
│   └── all.yml                 # Общие переменные
└── host_vars/
    ├── postgresql-db.yml       # Переменные для PostgreSQL
    ├── redis-cache.yml         # Переменные для Redis
    └── nextcloud.yml           # Переменные для Nextcloud
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
python3 scripts/regenerate-all.py

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
python3 scripts/regenerate-all.py

# 3. Проверить изменения
cd generated/terraform
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
python3 scripts/regenerate-all.py

# Результат:
# ✓ Generated: generated/terraform/lxc.tf (4 containers)  ← было 3
# ✓ Generated: hosts.yml (4 LXC containers)               ← было 3

# 3. Terraform создаст новый контейнер
cd generated/terraform
terraform plan
# Plan: 1 to add (lxc-monitoring)

terraform apply
```

---

## 🔍 Troubleshooting

### "generated/ не создается"

```bash
# Проверь, что скрипт запускается
python3 scripts/regenerate-all.py

# Если ошибка валидации - исправь topology.yaml
python3 scripts/validate-topology.py
```

---

### "Файлы в неправильной структуре"

```bash
# Удали generated/ и регенерируй
rm -rf generated
python3 scripts/regenerate-all.py
```

---

### "Изменения в generated/ потерялись"

**Это ожидаемое поведение!**

- ❌ НЕ редактируй `generated/`
- ✅ Редактируй `topology.yaml`
- ✅ Запускай `regenerate-all.py`

---

## 📚 Дополнительная документация

- **Полная документация**: `scripts/GENERATORS-README.md`
- **Changelog**: `CHANGELOG-GENERATED-DIR.md`
- **Topology v2.0**: `topology.yaml`
- **Валидация**: `python3 scripts/validate-topology.py`

---

## ✅ Checklist для работы

- [ ] Отредактировал `topology.yaml`
- [ ] Запустил `python3 scripts/regenerate-all.py`
- [ ] Проверил `terraform plan` в `generated/terraform/`
- [ ] Применил изменения с `terraform apply`
- [ ] Запустил Ansible (если нужно)
- [ ] Закоммитил **только** `topology.yaml` (не `generated/`)

---

**Главное правило**: `topology.yaml` → `regenerate-all.py` → `generated/` → profit! 🚀

---

**Дата**: 2025-10-10
**Версия**: 1.0
