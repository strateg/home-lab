# ✅ L0 CORRECT: Global Only - No Central Hub

**Дата:** 26 февраля 2026 г.
**Статус:** ✅ ПРАВИЛЬНАЯ архитектура

---

## Главное Понимание

### ❌ Ошибка (Центральный Хаб)
```
L0-meta/defaults/
├── application.yaml       # SLA 99.0% для ВСЕХ
├── storage.yaml           # Backup daily для ВСЕГО
├── observability.yaml     # Alert severity для ВСЕХ
└── operations.yaml        # MTTR для ВСЕХ
```

**Проблема:** L0 становится хабом, все слои зависят от L0

### ✅ Правильно (Распределённое)
```
L0-meta/
└── _index.yaml            # ТОЛЬКО глобальное

L1-meta/, L2-meta/, ... L7-meta/
└── defaults.yaml          # Каждый слой свои defaults
```

**Преимущество:** Каждый слой независим!

---

## Что В L0 (ТОЛЬКО Глобальное)

| Параметр | Почему в L0 | Влияет На |
|----------|----------|----------|
| **Version** | Все обновляются вместе | L1-L7 |
| **GDPR compliant: true** | Regulatory для ВСЕГО | L1 (encryption), L5 (logging), L6 (retention) |
| **encryption_required: true** | Security constraint для ВСЕХ | L1, L2, L5, L6 |
| **min_tls_version: 1.2** | For everything | L1, L2, L5, L6 |
| **Naming scheme** | Consistency везде | L1-L7 |

---

## Что В Каждом Слое (Не в L0!)

### L1-meta/defaults.yaml
- SSH policy baseline
- Device lifecycle
- Firewall baseline

### L2-meta/defaults.yaml
- Network strategy
- MTU defaults
- Segment firewall policy

### L3-meta/defaults.yaml
- Backup schedule **PER DATA TYPE** (критичные vs временные)
- Replication strategy

### L5-meta/defaults.yaml
- SLA **OPTIONS** (99%, 99.9%, etc) не hardcoded!
- Monitoring **PROFILES** (detailed, basic, etc)
- Service-specific defaults

### L6-meta/defaults.yaml
- Alert severity **templates**
- Log retention **per type**
- Dashboard **styles**

### L7-meta/defaults.yaml
- Incident response **templates**
- Escalation **policies per severity**
- Runbook **patterns**

---

## Правильная Зависимость

```
L0: GLOBAL
├─ version
├─ compliance (GDPR, PCI, HIPAA)
├─ security_constraints (encryption, TLS)
├─ naming (device, service, metric)
└─ version_requirements (Terraform, Python)

    ↑↑↑ USED BY ALL LAYERS ↑↑↑

L1-L7: INDEPENDENT
├─ L1-meta (device defaults)
├─ L2-meta (network defaults)
├─ L3-meta (storage defaults)
├─ L4-meta (compute defaults)
├─ L5-meta (sla options, monitoring profiles)
├─ L6-meta (alert templates, log policies)
└─ L7-meta (incident templates, escalation)

    ↑↑↑ EACH USES OWN DEFAULTS ↑↑↑

L1-L7: INSTANCES
├─ L1 devices (override L1-meta if needed)
├─ L2 networks (override L2-meta if needed)
├─ L5 services (override L5-meta if needed)
└─ etc (each can override layer-meta)

ONE-WAY DEPENDENCY: Instances → Layer-meta → L0
NO CIRCULAR DEPENDENCIES! ✅
```

---

## Пример: Как Это Работает

### L0
```yaml
version: 4.0.0
compliance:
  gdpr_compliant: true
security_constraints:
  encryption_required: true
```

### L3-meta/defaults.yaml
```yaml
backup_templates:
  critical:
    retention_days: 365  # GDPR compliant (from L0)
  temporary:
    retention_days: 30
```

### L3 Service (Nextcloud Database)
```yaml
backup:
  template: critical      # Uses L3-meta
  # Gets retention_days: 365 from L3-meta
  # Which respects L0 GDPR requirement
```

**Результат:** L3 независим, но соблюдает L0 требования!

---

## Созданные Файлы

1. **`L0-ANALYSIS-GLOBAL-VS-LAYER-SPECIFIC.md`**
   - Анализ что глобально, что специфично слою

2. **`L0-FINAL-CORRECT-MINIMAL.md`**
   - Правильный L0 (один файл!)
   - L1-L7 meta структура
   - Примеры использования

3. **`adr/0049-L0-final.md`**
   - Финальный ADR

---

## Summary

**L0 = ГЛОБАЛЬНО ТОЛЬКО**
- Version
- Compliance requirements
- Security constraints
- Naming scheme
- Tool requirements

**L1-L7 = НЕЗАВИСИМЫЕ с OWN META**
- Каждый слой имеет defaults для этого слоя
- Каждый слой может быть independent
- Добавление нового сервиса = добавление в L5-meta

**Результат:** Чистая, scalable архитектура! ✅
