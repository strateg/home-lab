# ✅ FINAL L0 DESIGN: Simplified + Modular Security Policies

**Дата:** 26 февраля 2026 г.
**Статус:** ✅ ГОТОВО К РЕАЛИЗАЦИИ

---

## 📋 New ADR 0049 (Updated)

Создал новый ADR 0049 который заменяет все предыдущие версии:

**`adr/0049-l0-simplified-with-security-policies.md`**

Содержит:
- ✅ Упрощённый L0 design
- ✅ Модульные security polícy
- ✅ Git-based тестирование (без extra VMs)
- ✅ Ясная стратегия security
- ✅ Practical workflow

---

## 🏗️ L0 Structure (FINAL)

```
L0-meta/
├── _index.yaml                   # Главный конфиг (редактируешь ЭТО!)
└── security/                     # Security polícy (опциональные)
    ├── built-in/                 # Pre-built polícy
    │   ├── baseline.yaml         # Standard production
    │   ├── strict.yaml           # High-security
    │   └── relaxed.yaml          # Development
    └── custom/                   # Твои polícy (если нужны)
```

---

## 📝 L0-meta/_index.yaml (Main File)

```yaml
# === VERSION ===
version: 4.0.0
name: "Home Lab Infrastructure"

# === NETWORK ===
network:
  primary_router: mikrotik-chateau
  primary_dns: 192.168.88.1
  backup_dns: 1.1.1.1
  ntp_server: pool.ntp.org

# === SECURITY POLICY ===
security_policy: baseline  # Choose: baseline, strict, relaxed, or custom

# === OPERATIONS ===
operations:
  backup_enabled: true
  backup_schedule: daily
  monitoring_enabled: true
  audit_logging: false

# === DEFAULTS ===
defaults:
  sla_target: 99.0
  firewall_default_action: drop
  encryption_tls_minimum: "1.2"

# === TESTING ===
testing_notes: |
  Use git for safe testing:
  1. git checkout -b feature/your-change
  2. Edit topology files
  3. terraform plan (see what changes)
  4. terraform apply (if plan OK)
  5. git revert if something breaks
```

**Итого:** ~50 строк. Всё что нужно!

---

## 🔐 Three Security Policies (Built-in)

### Baseline (Default)

```yaml
# L0-meta/security/built-in/baseline.yaml

Min password: 16 characters
Password rotation: 90 days
SSH: Key-only (no password)
SSH root: Prohibited-password
Firewall: Drop by default
Audit logging: No (optional)

Use for: Standard production
```

### Strict

```yaml
# L0-meta/security/built-in/strict.yaml

Min password: 20 characters
Password rotation: 60 days
SSH: Key-only (no password)
SSH root: No (not allowed)
SSH port: 2222 (non-standard)
Firewall: Drop by default
Geo-blocking: Yes
Audit logging: Yes

Use for: Sensitive data, compliance
```

### Relaxed

```yaml
# L0-meta/security/built-in/relaxed.yaml

Min password: 8 characters
Password rotation: Never
SSH: Password auth allowed
SSH root: Yes (allowed)
Firewall: Accept by default
Audit logging: No

Use for: Development/testing only
```

---

## 🎯 How to Use

### Step 1: Choose Policy in _index.yaml

```yaml
security_policy: baseline  # or strict, or relaxed
```

### Step 2: Regenerate

```bash
python3 topology-tools/regenerate-all.py
```

### Step 3: Apply

```bash
terraform apply
```

**Done!** All L1-L7 layers have that security level.

---

## 🧪 Testing (No Extra VMs!)

```bash
# Want to test stricter security?

git checkout -b feature/stricter-security
vim topology/L0-meta/_index.yaml
# Change: security_policy: baseline → strict

terraform plan
# See what changes (stricter passwords, no root SSH, etc.)

# If looks good:
terraform apply

# If something breaks:
git revert <commit-hash>
terraform apply
# Instant rollback!
```

---

## 📊 Comparison Table

| Aspect | Built-in | Custom |
|--------|----------|--------|
| **Use case** | 90-95% of cases | Rare (HIPAA/PCI-DSS) |
| **Effort** | Zero (already created) | Create one file |
| **Complexity** | Simple | Simple |
| **Customization** | Three choices | Unlimited |
| **Example** | baseline, strict, relaxed | hipaa-compliant |

---

## 🚀 Implementation Plan

### Week 1: Create L0 Structure
- Create _index.yaml with all settings
- Create security/built-in/ with 3 polícy
- Update topology-tools to load polícy

### Week 2: Migration
- Convert old L0-meta.yaml to new structure
- Test with all generators
- Verify everything works

### Week 3: Documentation
- Document how to use _index.yaml
- Document security polícy selection
- Document git-based testing

---

## ✨ Benefits of This Design

| Аспект | До | После |
|--------|-----|-------|
| **L0 файлы** | 9 (сложно) | 1 main + opt security/ (просто) |
| **Доп VM** | 5 test-VMs (требует ресурсы) | 0 (git вместо этого) |
| **Дублирование** | ~30% | 0% |
| **Когнитивная нагрузка** | Высокая | Низкая |
| **Security polícy** | Не раскрыто | Полностью раскрыто |
| **Практичность** | Сложная | Очень простая |

---

## 📁 Созданные Документы

1. **adr/0049-l0-simplified-with-security-policies.md** ← ГЛАВНЫЙ ADR
   - Архитектурное решение
   - Структура L0
   - Security polícy
   - Implementation plan

2. **L0-FINAL-SIMPLE-PRACTICAL.md**
   - Готовый _index.yaml
   - Примеры использования
   - Быстрый старт

3. **L0-SECURITY-POLICIES-GUIDE.md** (НОВЫЙ)
   - Как работают security polícy
   - Когда использовать какую
   - Как создать custom (если нужно)
   - Troubleshooting

4. **L0-PRACTICAL-SIMPLE-APPROACH.md**
   - Философия подхода
   - Почему без extra VMs лучше

---

## 🎓 Quick Start

**Для новичка (5 минут):**
1. Прочитать L0-FINAL-SIMPLE-PRACTICAL.md
2. Скопировать _index.yaml content
3. Выбрать security_policy: baseline
4. Готово!

**Для DevOps (10 минут):**
1. Прочитать ADR 0049
2. Прочитать L0-SECURITY-POLICIES-GUIDE.md
3. Выбрать правильную polícy для твоего случая
4. Создать custom если нужна (редко)

---

## 💡 Key Points

✅ **Простота:** _index.yaml - это всё что нужно
✅ **Security:** Три встроенные polícy + возможность custom
✅ **Тестирование:** Git branches + terraform plan = безопасно
✅ **Модульность:** Security polícy отделены от main config
✅ **No duplication:** Одна production config
✅ **No extra VMs:** Слабый Proxmox не страдает

---

## 🎉 Status: READY TO IMPLEMENT

✅ ADR 0049 updated
✅ L0 structure defined
✅ Security polícy раскрыта
✅ Git-based testing объяснён
✅ Все документы готовы

**Готово к реализации!** 🚀
