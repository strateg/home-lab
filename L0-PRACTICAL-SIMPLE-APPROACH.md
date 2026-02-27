# Тестирование Без Дополнительных VM: Простой и Практичный Подход

**Дата:** 26 февраля 2026 г.
**Подход:** No extra VMs, no config duplication, just safe testing

---

## Проблема с Моим Предложением

❌ Я предложил создавать test-vm-01..05 на Proxmox
❌ Это требует дополнительные ресурсы
❌ Это требует дублировать конфигурации
❌ Это усложняет топологию

**Ты прав! Это плохой подход для слабого железа.**

---

## Простое Решение: Validate Before Apply

### Принцип

**У тебя уже есть все инструменты для безопасного тестирования:**

1. **Terraform plan** — посмотреть что изменится БЕЗ применения
2. **Dry-run генераторов** — проверить конфиги перед генерацией
3. **Git branches** — экспериментировать без риска
4. **Git rollback** — откатить если что-то сломалось

**Ноль дополнительных VM. Ноль дублирования конфигов.**

---

## Workflow: Тестирование Безопасно

### Сценарий: Хочешь Обновить Nextcloud

#### Шаг 1: Создай Git Branch для Эксперимента

```bash
# Вместо создания test-VMs, создай git branch!
git checkout -b feature/nextcloud-upgrade

# Вся топология скопирована в branch
# Можешь экспериментировать без риска
```

#### Шаг 2: Внеси Изменения в Topology

```bash
# Отредактируй L5 сервис (версия Nextcloud)
# или L6 алерты для новой версии
# или что угодно

vim topology/L5-application/services/web-services.yaml
# Change: nextcloud_version: 27 → 28
```

#### Шаг 3: Валидируй ДО Применения

```bash
# ВАРИАНТ A: Используй terraform plan (сухой прогон)
cd terraform
terraform plan -out=tfplan
# Прочитай что именно изменится
# Если всё OK → можно apply
# Если что-то странное → отмени (ctrl+c)

# ВАРИАНТ B: Используй dry-run генератора
python3 topology-tools/generate-docs.py --dry-run
python3 topology-tools/validate-topology.py --strict
# Провери валидацию ДО любых изменений
```

#### Шаг 4: Если Всё OK — Apply к Реальной Инфре

```bash
# После валидации ты уверен что изменения безопасны
git checkout main
git merge feature/nextcloud-upgrade
# Теперь apply to production
terraform apply tfplan
```

#### Шаг 5: Если Что-то Пошло Не Так — Откати

```bash
# Благодаря git history, откатиться просто:
git log --oneline
git revert <commit-hash>
# Или просто checkout старую версию:
git checkout main~1 -- topology/
```

---

## Инструменты Тестирования (Которые у Тебя Уже ЕСТЬ)

### 1. Terraform Plan (Безопасный Сухой Прогон)

```bash
# Посмотри что Terraform хочет изменить БЕЗ применения
terraform plan
# Выведет все изменения в красивом формате
# Если выглядит хорошо → terraform apply
# Если странное → abort
```

**Что проверяет:**
- Какие VM будут созданы/удалены
- Какие конфиги изменятся
- Есть ли синтаксические ошибки

**Преимущество:** Нет риска, можно смотреть сколько угодно раз

### 2. Topology Validator (Проверка Корректности)

```bash
# Валидируй топологию перед применением
python3 topology-tools/validate-topology.py

# Проверит:
# - Все refs существуют
# - Нет циклических зависимостей
# - Все требуемые поля заполнены
# - Нет конфликтов в naming
```

### 3. Generators с Dry-Run

```bash
# Запусти генератор в режиме "только показать, не писать"
python3 topology-tools/generate-terraform.py --dry-run
python3 topology-tools/generate-ansible.py --dry-run
python3 topology-tools/generate-docs.py --dry-run

# Выведет что сгенерируется БЕЗ написания на диск
# Можешь проверить результат
```

### 4. Git Branches (Экспериментирование Без Риска)

```bash
# Создай branch для экспериментов
git checkout -b experiment/new-feature

# Вноси изменения, тестируй, валидируй
# Если не нравится → просто delete branch
git checkout main
git branch -D experiment/new-feature

# Если нравится → merge в main
git merge experiment/new-feature
```

---

## Практический Workflow (День в День)

### Утро: Production Работает

```bash
# Всё работает как надо
environment: production  # (один environment, готов к use!)
# Real Orange Pi 5, Real MikroTik, Real Proxmox

# Ничего не меняешь, всё стабильно
```

### Днём: Хочешь Что-то Улучшить

```bash
# Шаг 1: Создай branch
git checkout -b feature/nextcloud-version-bump

# Шаг 2: Отредактируй что хочешь
vim topology/L5-application/services/web-services.yaml
# Изменилось: nextcloud_version

# Шаг 3: Валидируй
python3 topology-tools/validate-topology.py
# Выведет ошибки если что-то сломалось

# Шаг 4: Посмотри что изменится
terraform plan
# Выведет все изменения

# Если всё good:
git add topology/
git commit -m "feat: bump nextcloud to v28"

# Если что-то не ок:
git checkout -- topology/  # откати всё
```

### Вечером: Готов к Apply

```bash
# Когда уверен что всё правильно:
git merge feature/nextcloud-version-bump
# Merge в main

# Затем apply к реальной инфре:
terraform apply
ansible-playbook site.yml
```

### Если Сломалось

```bash
# Просто откати с помощью git:
git revert <commit-hash>
# или
git reset --hard <commit-hash>

# Terraform автоматически откатит изменения
terraform apply  # вернёт старое состояние
```

---

## Что НА САМОМ ДЕЛЕ Нужно в L0

Вместо `environment: production/testing/development` → просто:

```yaml
# L0-meta/_index.yaml (максимально простой!)
version: 4.0.0
name: "Home Lab Infrastructure"

quick_settings:
  primary_router: mikrotik-chateau
  primary_dns: 192.168.1.1
  security_level: baseline  # или strict если нужна
  backup_enabled: true
  monitoring_enabled: true
  audit_logging: false

# Всё! Больше ничего не нужно!
# Нет environment switching
# Нет дублирования конфигов
# Просто одна инфра, одна конфигурация
```

**Точка!** Никаких "production/staging/development" профилей.

---

## Процесс Тестирования (ОЧЕНЬ ПРОСТОЙ)

```
┌─────────────────────────────────────────────┐
│ Хочешь изменить что-то?                     │
└──────────────┬──────────────────────────────┘
               │
    ┌──────────▼──────────┐
    │ 1. git checkout -b  │
    │    feature/name     │ ← Создай branch
    │                     │
    │ 2. Отредактируй     │
    │    topology/*.yaml  │
    │                     │
    │ 3. terraform plan   │ ← Проверь что изменится
    │    (смотри output)  │
    │                     │
    │ 4. Если OK:         │
    │    git merge        │ ← Merge в main
    │    terraform apply  │ ← Apply to production
    │                     │
    │ 5. Если BROKEN:     │
    │    git revert       │ ← Откати всё
    │    terraform apply  │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  Done!             │
    │  Без доп VM        │
    │  Без дублирования  │
    │  Без усложнений    │
    └────────────────────┘
```

---

## Что Удалить Из Моего Предложения

❌ Удалить: Концепция environments (production/testing/development)
❌ Удалить: Дублирование конфигов
❌ Удалить: test-vm-01..05 на Proxmox
❌ Удалить: Многоуровневые конфигурационные файлы

✅ Оставить: Простой L0 с основными настройками
✅ Оставить: Git branches для экспериментов
✅ Оставить: terraform plan для безопасной валидации
✅ Оставить: Git history для возможности откката

---

## Правильная L0 Structure (ОЧЕНЬ ПРОСТАЯ)

```
L0-meta/
└── _index.yaml    ← ВСЕ НАСТРОЙКИ ЗДЕСЬ!
    (больше ничего не нужно)
```

Содержимое:

```yaml
version: 4.0.0
name: "Home Lab Infrastructure"

# Основные настройки
primary_router: mikrotik-chateau
primary_dns: 192.168.1.1
security_level: baseline
backup_enabled: true
monitoring_enabled: true
audit_logging: false

# Всё! Простота!
```

**Никаких environments, никаких profiles, никаких конфигов.**

---

## Инструменты Для Безопасного Тестирования

| Инструмент | Что Делает | Когда Использовать |
|------------|-----------|-------------------|
| **git branch** | Изолирует изменения | Когда хочешь экспериментировать |
| **terraform plan** | Показывает что изменится | ДО применения изменений |
| **validate-topology.py** | Проверяет корректность | После редактирования topology |
| **git revert/reset** | Откатывает изменения | Если что-то сломалось |
| **terraform state** | Хранит текущее состояние | Для отката на Proxmox/Orange Pi |

**Все уже установлены и работают!**

---

## Обыкновенный День

```bash
# Утро: всё работает
$ git status
On branch main
nothing to commit, working tree clean

# Хочешь улучшить Nextcloud
$ git checkout -b feature/nextcloud-v28
$ vim topology/L5-application/services/web-services.yaml
# Change version: 27 → 28

# Проверь что изменится
$ terraform plan
Plan: 1 to change (in Nextcloud service)
# Выглядит хорошо!

# Залей в main
$ git checkout main
$ git merge feature/nextcloud-v28
$ terraform apply
# Nextcloud обновлён на реальной инфре!

# Вечер: всё работает, новая версия
$ nextcloud-client access
# V28 running, users happy!
```

**Никаких test-VMs, никаких конфигов, никаких усложнений.**

---

## Итог

### Неправильно (мой первый подход):
```
- 9 файлов в L0
- environments: production/testing/development
- test-vm-01..05 на Proxmox
- дублирование конфигов
- усложнение топологии
```

### Правильно (этот подход):
```
- 1 файл в L0 (_index.yaml)
- одна конфигурация (production)
- ноль доп VM
- ноль дублирования
- максимальная простота
+ git branches для тестирования
+ terraform plan для безопасности
+ git history для отката
```

**Безопаснее, проще, практичнее.**

---

## Итоговые Документы для Обновления

Нужно создать:
1. `L0-SIMPLIFIED-FINAL-PRACTICAL.md` — Финальный простой L0
2. `TESTING-WITHOUT-EXTRA-VMS.md` — Как тестировать без лишних VM

Удалить/переделать:
- environments.yaml → НЕ НУЖЕН
- Всё про testing environment → Заменить на git workflow
