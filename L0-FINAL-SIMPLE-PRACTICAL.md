# L0 FINAL: Максимально Простой и Практичный Design

**Дата:** 26 февраля 2026 г.
**Принцип:** KISS (Keep It Simple, Stupid)

---

## Структура: Простая с Модульными Security Политиками

```
L0-meta/
├── _index.yaml                   # Главный конфиг (редактируешь ЭТО!)
└── security/                     # Опциональные security политики
    ├── built-in/                 # Pre-built policies
    │   ├── baseline.yaml         # Standard (default)
    │   ├── strict.yaml           # High-security
    │   └── relaxed.yaml          # Development
    └── custom/                   # Твои custom policies (если нужны)
        └── .gitkeep
```

**Главное:** Редактируешь только `_index.yaml`!
**Security:** Выбираешь из baseline/strict/relaxed в `_index.yaml`

---

## Содержимое: L0-meta/_index.yaml

```yaml
# ============================================================================
# L0 META - Home Lab Infrastructure Configuration
# Edit this file and regenerate: python3 topology-tools/regenerate-all.py
# ============================================================================

# === VERSION & IDENTIFICATION ===
version: 4.0.0
name: "Home Lab Infrastructure"
description: "MikroTik Chateau + Orange Pi 5 + Proxmox"
created: 2025-10-06
author: dprohhorov
last_updated: 2026-02-26

# === PRIMARY SETTINGS (Основные настройки) ===
# Редактируй эти значения если нужно что-то изменить

network:
  # IMPORTANT: Concrete IP addresses belong in L1-Foundation!
  # Use logical references here, not specific IPs
  primary_network_manager_device_ref: network-gateway  # L1 implements with IP
  primary_dns_resolver_ref: default-dns               # L1 implements with IP
  ntp_source_ref: pool-ntp                            # L1 implements with IP
  # See L1-foundation/devices/ for actual IP addresses!

security:
  security_level: baseline  # Options: baseline, strict, relaxed
  ssh_key_required: true
  password_min_length: 16
  password_expire_days: 90
  firewall_default_action: drop

operations:
  backup_enabled: true
  backup_schedule: daily
  backup_retention_days: 30
  monitoring_enabled: true
  monitoring_level: detailed  # Options: detailed, basic, minimal
  audit_logging: false  # Set to true if you want full audit trail

features:
  high_availability: false  # Not applicable for single-point hardware
  encryption_tls_minimum: "1.2"
  rate_limiting: true

# === CHANGE LOG ===
changelog:
  - version: 4.0.0
    date: 2026-02-17
    changes:
      - Simplified to single L0 file
      - Git-based testing approach
      - Removed multiple environments (testing/staging/dev)
    rationale: "Production infrastructure with single config, test via git branches and terraform plan"

  - version: 3.0.0
    date: 2026-02-16
    changes:
      - MikroTik Chateau as central router
      - Orange Pi 5 as dedicated app server
      - Proxmox for storage and additional services

  - version: 2.1.0
    date: 2025-10-10
    changes: Phase 2 improvements

  - version: 2.0.0
    date: 2025-10-09
    changes: Physical/logical/compute separation

  - version: 1.1.0
    date: 2025-10-09
    changes: Trust zones, metadata enhancements

  - version: 1.0.0
    date: 2025-10-06
    changes: Initial Infrastructure-as-Data

# === TESTING APPROACH ===
# DO NOT CREATE "STAGING" OR "TESTING" ENVIRONMENTS
# Instead, use this workflow:
#
# 1. git checkout -b feature/your-change
# 2. Edit topology files
# 3. terraform plan (see what will change)
# 4. terraform apply (if plan looks good)
# 5. If anything goes wrong: git revert or git reset
#
# This is safer, simpler, and requires NO extra VMs

testing_notes: |
  TESTING WORKFLOW (No Extra VMs Needed):

  Want to test a change?

  Step 1: Create git branch
    git checkout -b feature/nextcloud-upgrade

  Step 2: Edit topology
    vim topology/L5-application/services/web-services.yaml

  Step 3: Validate changes
    python3 topology-tools/validate-topology.py
    terraform plan

  Step 4: If plan looks good
    git commit
    git merge feature/nextcloud-upgrade
    terraform apply

  Step 5: If something breaks
    git revert <commit-hash>
    terraform apply

  NO TEST-VMs NEEDED! Git branches + terraform plan = safe testing!

# === SECURITY POLICIES ===
# Three built-in policies available:
# - baseline: Standard production security (default)
# - strict: High-security (key-only SSH, 20+ char passwords, audit logging)
# - relaxed: Development-friendly (password auth allowed, 8+ char passwords)
#
# Select policy in this section:

security_policy: baseline  # Options: baseline, strict, relaxed

# === OPTIONAL: CREATE CUSTOM POLICY ===
# If built-in policies don't fit, create custom:
# File: L0-meta/security/custom/my-policy.yaml
# Then reference: security_policy: my-policy
#
# Most home labs use baseline or strict. Custom policies are rare.

# === DEFAULTS FOR L1-L7 ===
# These are used if specific layers don't override them

defaults:
  security_policy: baseline
  network_manager: mikrotik-chateau
  dns_primary: 192.168.88.1
  dns_secondary: 1.1.1.1
  backup_enabled: true
  monitoring_enabled: true
  sla_target: 99.0  # 99% uptime target
  alert_severity_default: warning

# === NOTES ===
notes: |
  IMPORTANT:

  1. This is a SINGLE CONFIGURATION for PRODUCTION
     - No "staging" environment
     - No "development" environment
     - No test-VMs on Proxmox
     - One infrastructure, one config, maximum simplicity

  2. For TESTING changes safely:
     - Use git branches (feature/your-change)
     - Use terraform plan (see what changes)
     - Use git revert if something breaks
     - NO extra resources needed!

  3. Update this file only when you need to change:
     - Router IP
     - DNS server
     - Security level
     - Backup schedule
     - Other global settings

  4. For service-specific changes:
     - Edit L5 application files directly
     - Edit L2 network files directly
     - Use terraform plan to validate
     - Merge to main only when confident

# ============================================================================
# END OF L0 CONFIGURATION
# ============================================================================
```

---

## Использование

### Когда Нужно Что-то Изменить

**Сценарий: Хочешь Включить Audit Logging**

```bash
# Шаг 1: Создай git branch
git checkout -b feature/enable-audit

# Шаг 2: Отредактируй L0-meta/_index.yaml
vim topology/L0-meta/_index.yaml
# Измени: audit_logging: false → audit_logging: true

# Шаг 3: Валидируй
python3 topology-tools/validate-topology.py
# Если ошибок → отмени (git checkout -- topology/)
# Если OK → продолжай

# Шаг 4: Посмотри что изменится
terraform plan
# Выведет какие конфиги изменятся

# Шаг 5: Если нравится → apply
git commit topology/L0-meta/_index.yaml -m "feat: enable audit logging"
git merge feature/enable-audit
terraform apply

# Шаг 6: Если что-то сломалось → откати
git revert <commit-hash>
terraform apply
```

---

### Когда Хочешь Изменить Сервис

**Сценарий: Обновить Версию Nextcloud**

```bash
# ВАРИАНТ A: Простое изменение (в git branch)
git checkout -b feature/nextcloud-v28
vim topology/L5-application/services/web-services.yaml
# Измени версию

terraform plan
# Проверь что изменится

git commit
git merge feature/nextcloud-v28
terraform apply

# ВАРИАНТ B: Если надо откатить
git log --oneline
git revert <commit-hash>
terraform apply
```

---

## Что ИСКЛЮЧИТЬ Из Этого Design

❌ **НЕ ДОБАВЛЯТЬ:**
- environment: production/staging/development
- multiple config files per layer
- test-vm-01..05 на Proxmox
- environments.yaml с разными стратегиями
- policies/security.yaml custom policies
- regional-policies/ для разных регионов

✅ **ДОБАВИТЬ ВМЕСТО:**
- Git branches для экспериментов
- Terraform plan для валидации
- Git history для отката
- Простые комментарии в _index.yaml

---

## Преимущества Этого Подхода

| Аспект | Этот Подход | Сложный Подход |
|--------|-------------|----------------|
| **Файлы в L0** | 1 | 9 |
| **Конфигурации** | 1 (production) | 3 (prod/staging/dev) |
| **Доп VM для тестирования** | 0 | 5 (test-vm-01..05) |
| **Дублирование конфигов** | 0 | ~50% дублирования |
| **Сложность** | Минимальная | Высокая |
| **Время обучения** | 5 минут | 30 минут |
| **Требуемые ресурсы на Proxmox** | Минимальные | Много |
| **Способ тестирования** | git + terraform plan | Отдельные test-VMs |
| **Откат при ошибке** | git revert | Удалить test-VMs |

**Победитель: Этот подход!** Во всём простой and практичнее.

---

## Откат При Проблемах

### Если Что-то Сломалось

```bash
# Посмотри что ты менял
git log --oneline
# Выведет последние commits

# Откати последний commit
git revert <commit-hash>
terraform apply
# Прошлое состояние восстановлено!

# Или полностью откати в прошлое
git reset --hard HEAD~3  # Откати на 3 commits назад
terraform apply
```

**Никаких ручных откатов, всё через git!**

---

## Итоговая Структура L0

```
topology/
└── L0-meta/
    └── _index.yaml          ← ВСЕ НАСТРОЙКИ ЗДЕСЬ
                                (больше ничего не нужно!)
```

**Простота = надёжность**

---

## Когда Полезен Этот Подход

✅ Когда железо слабое (как твой Proxmox)
✅ Когда не хочешь дублировать конфиги
✅ Когда хочешь максимальную простоту
✅ Когда нужен быстрый откат
✅ Когда один человек управляет инфрой
✅ Когда инфра production-ready

**Твой случай:** Идеально подходит!

---

## Status

✅ Простой design
✅ Ноль extra resources
✅ Ноль дублирования
✅ Максимальная простота
✅ Git-based testing
✅ Быстрый откат

**Ready to use!**
