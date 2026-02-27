# L0 FINAL: Only Global Settings That Affect ALL Layers

**Дата:** 26 февраля 2026 г.
**Версия:** ПРАВИЛЬНАЯ (без центрального хаба)

---

## L0 Meta Structure (Минимальная!)

```
L0-meta/
└── _index.yaml              # Это ВСЁ что нужно в L0!
```

**Одного файла достаточно!**

---

## L0-meta/_index.yaml (ТОЛЬКО Глобальное)

```yaml
# =============================================================================
# L0 META LAYER - ONLY Global Settings That Affect ALL Layers
# =============================================================================

# === VERSION (affects everything) ===
version: 4.0.0
name: "Home Lab Infrastructure"
created: 2025-10-06

# === GLOBAL COMPLIANCE (affects everything) ===
compliance:
  # These affect ALL layers (L1-L7)
  gdpr_compliant: true        # L1 (encryption), L5 (logging), L6 (retention)
  pci_dss_compliant: false
  hipaa_compliant: false

# === GLOBAL SECURITY CONSTRAINTS (affects everything) ===
security_constraints:
  # These apply to ALL layers
  encryption_required: true    # L1 (SSH), L2 (network), L5 (comms), L6 (logs)
  min_tls_version: "1.2"       # L1, L2, L5 all enforce this
  authentication_required: true # Every connection needs auth

# === GLOBAL NAMING SCHEME (affects everything) ===
naming:
  # How to name things across ALL layers
  device_pattern: "{type}-{location}-{number}"
  service_pattern: "svc-{domain}.{name}"
  metric_pattern: "{layer}_{domain}_{metric}"

  examples:
    device: "router-main-01"
    service: "svc-web.nextcloud"
    metric: "L5_app_response_time_ms"

# === VERSION CONSTRAINTS (affects everything) ===
version_requirements:
  # Tools that ALL layers depend on
  min_terraform: "1.0.0"
  min_ansible: "2.10.0"
  min_python: "3.9"

  # Optional: pin specific versions
  # terraform: "~> 1.5.0"
  # python: "~> 3.11.0"

# === NOTES ===
notes: |
  L0 CONTAINS ONLY:
  ✅ Version and metadata
  ✅ Global compliance requirements
  ✅ Global security constraints
  ✅ Global naming schemes
  ✅ Version requirements

  L0 DOES NOT contain:
  ❌ SLA targets (per service in L5)
  ❌ Monitoring levels (per service in L5)
  ❌ Alert severity (per alert in L6)
  ❌ Backup schedules (per data type in L3)
  ❌ VM defaults (per environment in L4)
  ❌ Incident MTTR (per service in L7)

  EACH LAYER HAS ITS OWN META:
  - L1-meta/defaults.yaml (device defaults)
  - L2-meta/defaults.yaml (network defaults)
  - L3-meta/defaults.yaml (storage defaults)
  - L4-meta/defaults.yaml (compute defaults)
  - L5-meta/defaults.yaml (application defaults)
  - L6-meta/defaults.yaml (observability defaults)
  - L7-meta/defaults.yaml (operations defaults)
```

---

## Как Каждый Слой Использует L0

### L1 (Foundation)

```yaml
# L1-foundation/meta/defaults.yaml
# Использует только из L0:
version: ${L0.version}  # Must be consistent
naming_device_pattern: ${L0.naming.device_pattern}
encryption_required: ${L0.security_constraints.encryption_required}

# Собственные L1 defaults:
device_defaults:
  ssh:
    permit_root_login: prohibit-password
    min_key_strength: 2048
  firewall:
    default_action: drop
```

### L2 (Network)

```yaml
# L2-network/meta/defaults.yaml
# Использует только из L0:
version: ${L0.version}
naming_metric_pattern: ${L0.naming.metric_pattern}
min_tls_version: ${L0.security_constraints.min_tls_version}

# Собственные L2 defaults:
network_strategy:
  mtu: 1500
  segments:
    production:
      firewall_action: drop
    management:
      firewall_action: drop
```

### L3 (Storage)

```yaml
# L3-storage/meta/defaults.yaml
# Использует только из L0:
version: ${L0.version}
gdpr_compliant: ${L0.compliance.gdpr_compliant}  # Affects retention!

# Собственные L3 defaults:
backup_templates:
  critical_data:
    schedule: daily
    retention_days: 365  # GDPR: 1 year for critical
  temporary_data:
    schedule: weekly
    retention_days: 30
```

### L5 (Application)

```yaml
# L5-application/meta/defaults.yaml
# Использует только из L0:
version: ${L0.version}
encryption_required: ${L0.security_constraints.encryption_required}
naming_service_pattern: ${L0.naming.service_pattern}

# Собственные L5 defaults:
sla_templates:
  critical:
    uptime_percent: 99.9
  standard:
    uptime_percent: 99.0

monitoring_profiles:
  detailed:
    metrics_interval: 10s
  basic:
    metrics_interval: 60s
```

### L6 (Observability)

```yaml
# L6-observability/meta/defaults.yaml
# Использует только из L0:
version: ${L0.version}
gdpr_compliant: ${L0.compliance.gdpr_compliant}  # Affects log retention!

# Собственные L6 defaults:
alert_templates:
  performance:
    default_severity: warning
  availability:
    default_severity: critical

log_defaults:
  retention_days: 30  # or more if GDPR requires
```

### L7 (Operations)

```yaml
# L7-operations/meta/defaults.yaml
# Использует только из L0:
version: ${L0.version}
compliance: ${L0.compliance}  # Affects incident reporting!

# Собственные L7 defaults:
incident_response:
  critical:
    first_response_sla_minutes: 5
    escalation_delay: 1 minute
  normal:
    first_response_sla_minutes: 15
    escalation_delay: 5 minutes
```

---

## Правильная Зависимость

```
┌─────────────────────────────────────┐
│ L0: GLOBAL ONLY                     │
├─────────────────────────────────────┤
│ ✅ version: 4.0.0                   │
│ ✅ compliance: gdpr_compliant: true │
│ ✅ security_constraints: ...        │
│ ✅ naming_scheme: ...               │
│ ✅ version_requirements: ...        │
│                                     │
│ ❌ NO SLA targets                   │
│ ❌ NO Monitoring levels             │
│ ❌ NO Alert severity                │
│ ❌ NO Backup schedules              │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴────────────┐
    │ ALL layers read L0    │
    │ Each layer adds OWN   │
    │ META defaults!        │
    │                       │
    └──────────┬────────────┘
               │
    ┌──────────┴──────────────────────────────────┐
    │                                              │
    ▼                                              ▼
L1-meta/defaults.yaml              L2-meta/defaults.yaml
(SSH, Device lifecycle)            (Network design)
    │                                  │
    ▼                                  ▼
L3-meta/, L4-meta/, ...
(Storage, Compute, etc)
    │
    ▼
L5-meta/ (SLA options, Monitoring profiles)
    │
    ▼
L6-meta/ (Alert templates, Log policies)
    │
    ▼
L7-meta/ (Incident templates, Runbooks)

EACH LAYER HAS OWN META!
```

---

## Summary: Правильное L0

| What | L0 | L1-L7 |
|-----|----|----|
| **Version** | ✅ | ✅ Use L0 |
| **Compliance** | ✅ | ✅ Use L0 |
| **Security constraints** | ✅ | ✅ Use L0 |
| **Naming scheme** | ✅ | ✅ Use L0 |
| **SLA targets** | ❌ | ✅ Own defaults |
| **Monitoring level** | ❌ | ✅ Own defaults |
| **Backup schedule** | ❌ | ✅ Own defaults |
| **Alert severity** | ❌ | ✅ Own defaults |
| **VM memory** | ❌ | ✅ Own defaults |

---

## Преимущества Этого Подхода

✅ **L0 минимальна** (один файл!)
✅ **L0 не становится хабом** (нет центрального управления)
✅ **Каждый слой независим** (может иметь свои defaults)
✅ **Scalable** (добавь новый сервис = добавь в L5-meta, не в L0)
✅ **Чистая архитектура** (no circular dependencies)
✅ **Понятно** (что в L0, что в каждом слое ясно)
