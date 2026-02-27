# L0 Analysis: Global vs Layer-Specific Settings

**Дата:** 26 февраля 2026 г.
**Задача:** Определить что ДЕЙСТВИТЕЛЬНО глобально, что специфично слою

---

## Анализ: Что Влияет на ВСЕ Слои

### ✅ ГЛОБАЛЬНОЕ (в L0) - Влияет на ВСЕ

| Параметр | Почему глобальный | Влияет на | Пример |
|----------|------------------|-----------|--------|
| **Версия топологии** | Все слои обновляются вместе | L1-L7 | v4.0.0 |
| **Compliance requirements** | Регуляторные требования для ВСЕГО | L1-L7 | GDPR required, PCI-DSS |
| **Global security requirements** | Encryption/auth для ВСЕХ устройств | L1-L7 | "Encryption required everywhere" |
| **Global naming scheme** | Все используют одну схему | L1-L7 | svc-{domain}.{name} |
| **Min/max constraints** | Для всей инфры | L1-L7 | Min TLS 1.2, Min Python 3.9 |

---

## Анализ: Что СПЕЦИФИЧНО Слою

### ❌ НЕПРАВИЛЬНО (в L0)
```yaml
# L0-meta/defaults/application.yaml
sla:
  target_uptime_percent: 99.0  # ← Это ОШИБКА!

monitoring:
  level: detailed  # ← Это ОШИБКА!
```

**Почему неправильно:**
- Nextcloud может иметь 99.9% SLA
- Redis может быть best-effort (99%)
- Какой Nextcloud? Какой Redis? L0 не знает!
- Каждый сервис имеет СВОЮ SLA

### ✅ ПРАВИЛЬНО (в L5)

```yaml
# L5-application/services/nextcloud.yaml
service:
  id: nextcloud
  sla:
    target_uptime_percent: 99.9  # Specific to THIS service

  monitoring:
    level: detailed  # Specific to THIS service
```

---

## Дефект Моего Подхода

### Что Я Делал (WRONG)

```
L0-meta/defaults/
├── application.yaml       # SLA 99.0% для ВСЕХ сервисов
├── observability.yaml     # Alert severity для ВСЕХ алертов
├── operations.yaml        # MTTR 5min для ВСЕХ инцидентов
├── storage.yaml           # Backup daily для ВСЕГО хранилища
└── compute.yaml           # VM memory 2GB для ВСЕХ VM
```

**Проблема:** Все сервисы получают одни и те же параметры!

### Что Должно Быть (RIGHT)

```
L0-meta/
└── _index.yaml            # Только VERSION и COMPLIANCE

L1-meta/
├── security-defaults.yaml # SSH baseline для устройств
├── firewall-defaults.yaml # Firewall baseline
└── device-defaults.yaml   # Device lifecycle

L2-meta/
├── network-strategy.yaml  # Сетевой design
└── segment-defaults.yaml  # Per-segment firewall

L3-meta/
├── backup-strategy.yaml   # Backup policies per DATA TYPE
└── replication-strategy.yaml # RPO/RTO per SERVICE

L5-meta/
├── sla-templates.yaml     # SLA options (99%, 99.9%, etc)
├── monitoring-profiles.yaml  # Monitoring options
└── audit-policies.yaml    # Audit requirements per type

L6-meta/
├── alert-severity.yaml    # Alert default severity
└── dashboard-templates.yaml # Template styles

L7-meta/
├── escalation-templates.yaml # Escalation policy templates
└── runbook-templates.yaml # Runbook patterns
```

---

## Правильное Разделение

### L0: ТОЛЬКО Глобальное (что влияет на ВСЕ)

```yaml
# L0-meta/_index.yaml

version: 4.0.0

compliance:
  requirements:
    - gdpr_compliant: true      # Влияет на L1 (encryption), L5 (logging), L6 (retention)
    - pci_dss: false
    - hipaa: false

security_constraints:
  # Глобальные требования (влияет на ВСЕ)
  encryption_required: true     # L1, L2, L5, L6 все используют
  min_tls_version: "1.2"       # Все используют
  authentication_required: true # Все используют

naming_scheme:
  # Как именовать везде (влияет на ВСЕ)
  device_pattern: "{type}-{name}"
  service_pattern: "svc-{domain}.{name}"
  metric_pattern: "{domain}_{metric_type}"

version_requirements:
  # Минимальные версии для инструментов (влияет на ВСЕ)
  min_terraform: "1.0.0"
  min_python: "3.9"
  min_ansible: "2.10"

# ВСЁ! Больше ничего в L0!
```

### L1: Device Defaults (для устройств)

```yaml
# L1-foundation/meta/defaults.yaml
# Применяется ко ВСЕМ устройствам в L1

device_defaults:
  # Базовые требования для устройств
  security_policy: baseline  # SSH key-based, etc

  ssh:
    # Baseline для SSH (может быть overridden в каждом device)
    permit_root_login: prohibit-password
    password_authentication: false
    idle_timeout: 600

  firewall:
    # Baseline для firewall (может быть overridden per device)
    default_action: drop
    enable_logging: true
```

### L2: Network Strategy (для сети)

```yaml
# L2-network/meta/defaults.yaml

network_strategy:
  # Глобальная сетевая архитектура
  mtu_default: 1500
  routing_type: static  # or dynamic

  # Per-segment defaults (but NOT in L0!)
  segments:
    production:
      firewall_action: drop
      rate_limiting: true
    management:
      firewall_action: drop
      rate_limiting: false
```

### L3: Storage Strategy (для хранилища)

```yaml
# L3-storage/meta/defaults.yaml

backup_strategy:
  # Разные стратегии для РАЗНЫХ типов данных!
  critical_data:
    schedule: daily
    retention_days: 365
    replication_factor: 3

  temporary_data:
    schedule: weekly
    retention_days: 30
    replication_factor: 1

  # NOT in L0!
```

### L5: Application Defaults (для сервисов)

```yaml
# L5-application/meta/defaults.yaml

sla_templates:
  # Options, not hardcoded!
  critical:
    uptime_percent: 99.9
    mttr_minutes: 5

  standard:
    uptime_percent: 99.0
    mttr_minutes: 30

  besteffort:
    uptime_percent: 95.0
    mttr_minutes: null

monitoring_profiles:
  # Options, not hardcoded!
  detailed:
    metrics_interval_seconds: 10
    retention_days: 90

  basic:
    metrics_interval_seconds: 60
    retention_days: 30
```

### L6: Observability Strategy (для мониторинга)

```yaml
# L6-observability/meta/defaults.yaml

alert_severity_templates:
  # Default severity per type (but each alert chooses its own!)
  performance:
    default_severity: warning
    escalation_delay_minutes: 15

  availability:
    default_severity: critical
    escalation_delay_minutes: 1

# NOT in L0!
```

### L7: Operations Templates (для операций)

```yaml
# L7-operations/meta/defaults.yaml

incident_response_templates:
  # Templates per incident type (but each chooses!)
  database_down:
    first_response_sla_minutes: 5
    escalation_levels: 2

  network_down:
    first_response_sla_minutes: 1
    escalation_levels: 3

# NOT in L0!
```

---

## Принцип: Вертикальная Зависимость

```
L0: GLOBAL (Compliance, Version, Naming, Security Constraints)
│
├─→ L1: Device Defaults (SSH baseline, Device lifecycle)
│
├─→ L2: Network Strategy (MTU, Segment firewall)
│
├─→ L3: Storage Strategy (Backup per data type)
│
├─→ L4: Compute (Resource allocation)
│
├─→ L5: Application Defaults (SLA options, Monitoring profiles)
│
├─→ L6: Observability (Alert templates, Dashboard styles)
│
└─→ L7: Operations (Incident templates, Runbooks)

KEY: L0 ← L1-L7 (one-way!)
Each layer has its own META for layer-specific defaults!
```

---

## Ошибка: Центральный Хаб

### ❌ What I Did (WRONG)

```
L0-meta/defaults/
├── application.yaml    ← SLA, Monitoring here!
├── observability.yaml  ← Alerts, Logs here!
├── operations.yaml     ← MTTR, Escalation here!
└── storage.yaml        ← Backup schedule here!

Result: L0 is a central hub for everything!
L1-L7 can't be independent!
```

### ✅ What Should Be (RIGHT)

```
L0-meta/
└── _index.yaml         ← ONLY: Version, Compliance, Constraints

L1-meta/, L2-meta/, ... L7-meta/
└── defaults.yaml       ← Each layer owns its defaults!

Result: Each layer is independent!
L0 is minimal and pure!
```

---

## Анализ: Что РЕАЛЬНО в L0

### Да (Глобальное)
✅ Version
✅ Compliance requirements (GDPR, PCI-DSS, HIPAA)
✅ Global security constraints (encryption required, min TLS)
✅ Global naming scheme
✅ Min/max version requirements (Terraform, Python, etc)

### Нет (Специфично слою)
❌ SLA targets (per service in L5)
❌ Monitoring level (per service in L5)
❌ Alert severity (per alert in L6)
❌ Backup schedule (per data type in L3)
❌ VM memory default (per compute environment in L4)
❌ Incident MTTR (per incident type in L7)
❌ Escalation policy (per service in L7)

---

## Summary

**Главная Ошибка:** Я вынес СПЕЦИФИЧНЫЕ для слоя параметры в L0

**Правильный Подход:**
1. L0 содержит ТОЛЬКО: версия, compliance, global constraints, naming scheme
2. Каждый слой (L1-L7) имеет свой META с defaults для ЭТОГО слоя
3. L1-L7 могут быть независимыми
4. L0 минимальна и чистая

**Результат:**
- ✅ L0 не становится хабом конфигураций
- ✅ Каждый слой контролирует свои defaults
- ✅ Лучше scalable (добавь новый сервис в L5 = добавь параметры в L5-meta, не в L0)
- ✅ Правильная архитектура
