# L0 Analysis: What Each Layer Actually Needs

**Дата:** 26 февраля 2026 г.
**Задача:** Определить правильную модульность L0 на основе потребностей L1-L7

---

## Анализ: Что Нужно Каждому Слою от L0

### L1 (Foundation)
- ✅ Security policy (какой уровень безопасности применить)
- ✅ Global identity (версия топологии, имя)
- ✅ SSH defaults (min key strength, timeouts)
- ✅ Firewall defaults (drop by default?)
- ✅ Encryption requirements (TLS 1.2+?)

### L2 (Network)
- ✅ Firewall policy (drop/accept by default)
- ✅ Network defaults (MTU, routing policy)
- ✅ Rate limiting policy
- ✅ Encryption requirements
- ✅ Logging requirements (log dropped packets?)

### L3 (Storage)
- ✅ Backup schedule policy (daily/weekly)
- ✅ Backup retention (30 days default?)
- ✅ Replication strategy (RPO, RTO)
- ✅ Encryption for backups (required?)

### L4 (Compute)
- ✅ VM resource defaults (CPU, memory)
- ✅ Resource limits per device
- ✅ High availability policy (HA required?)
- ✅ Performance targets (SLA)

### L5 (Application)
- ✅ SLA target (99.0%, 99.9%)
- ✅ Monitoring level (detailed/basic)
- ✅ Logging level (info/debug)
- ✅ Audit requirements
- ✅ Scaling policy (auto-scale enabled?)

### L6 (Observability)
- ✅ Alert severity defaults (critical/warning/info)
- ✅ Monitoring metrics interval (10s, 60s)
- ✅ Dashboard defaults
- ✅ Log retention days
- ✅ Metrics retention days

### L7 (Operations)
- ✅ Escalation policy template
- ✅ Incident response requirements
- ✅ Change approval requirements
- ✅ MTTR targets (5 min, 30 min)
- ✅ Runbook defaults

---

## Что L0 НЕ должна содержать

❌ Ссылки на L1: "primary_network_manager_device_ref"
❌ Конкретные IP адреса
❌ Конкретные device names
❌ Конкретные hostnames
❌ Конкретные port numbers

---

## Правильная Модульность L0

**Сгруппировать по ФУНКЦИОНАЛЬНЫМ ДОМЕНАМ, не по слоям:**

```
L0-meta/
├── _index.yaml                 # Version + metadata (abstract!)
├── security/                   # Security polícy module
│   ├── built-in/
│   │   ├── baseline.yaml
│   │   ├── strict.yaml
│   │   └── relaxed.yaml
│   └── custom/
├── defaults/                   # Global defaults (abstract!)
│   ├── network.yaml           # Network defaults (no IPs!)
│   ├── storage.yaml           # Backup/replication defaults
│   ├── compute.yaml           # VM/resource defaults
│   ├── application.yaml       # SLA/monitoring defaults
│   ├── observability.yaml     # Alert/log defaults
│   └── operations.yaml        # Escalation/incident defaults
```

---

## Содержимое Каждого Файла

### L0-meta/_index.yaml (Abstract Metadata)

```yaml
# VERSION & METADATA (no references to L1!)
version: 4.0.0
name: "Home Lab Infrastructure"
description: "Layered topology"

# WHICH SECURITY POLICY TO USE
active_security_policy: baseline

# INCLUDE OTHER MODULES
defaults: !include_dir_sorted defaults/
security_policies: !include_dir_sorted security/
```

### L0-meta/security/built-in/baseline.yaml

```yaml
id: baseline
description: "Standard production security"

password_policy:
  min_length: 16
  expire_days: 90
  history_count: 5

ssh_policy:
  permit_root_login: prohibit-password
  password_authentication: false
  pubkey_authentication: true
  port: null  # Don't specify port! (L2 decides)
  idle_timeout: 600

firewall_policy:
  default_action: drop
  log_blocked: true
  rate_limiting: true

audit_policy:
  log_authentication: false
  retention_days: 30

encryption_policy:
  tls_minimum_version: "1.2"
  certificate_validation: required
```

### L0-meta/defaults/network.yaml (Network Defaults - NO IPs!)

```yaml
# NETWORK DEFAULTS (abstract, not specific IPs)

network:
  # Network design defaults
  mtu_default: 1500
  routing_policy: static  # or dynamic
  dns_ttl_default: 300

  # No IP addresses here!
  # No device references here!

firewall:
  default_action: drop  # From security policy
  enable_logging: true
  enable_rate_limiting: true
  log_dropped_packets: true

encryption:
  tls_minimum_version: "1.2"  # From security policy
  require_encryption_in_transit: true
```

### L0-meta/defaults/storage.yaml (Backup Policies)

```yaml
storage:
  backup:
    enabled: true
    schedule: daily  # When to backup
    retention_days: 30  # How long to keep

  replication:
    enabled: false  # Is replication required?
    replication_factor: 2  # How many copies?

  encryption:
    encrypt_backups: true
    encrypt_in_transit: true

# No specific storage device!
# No mount points!
# No device names!
```

### L0-meta/defaults/compute.yaml (Resource Defaults)

```yaml
compute:
  # Default resource allocations (abstract!)
  vm_default_memory_mb: 2048
  vm_default_cpus: 2

  # Resource limits
  max_vms_per_node: 10
  max_memory_per_node_percent: 80

  # High availability
  high_availability_required: false
  redundancy_required: false

# No node names!
# No specific machine types!
```

### L0-meta/defaults/application.yaml (SLA & Monitoring)

```yaml
application:
  sla:
    target_uptime_percent: 99.0  # Default SLA

  monitoring:
    level: detailed  # detailed, basic, minimal
    metrics_interval_seconds: 60

  logging:
    level: info  # info, debug, warn
    retention_days: 30

  audit:
    enabled: false  # Audit changes?
    retention_days: 30

# No service names!
# No specific monitoring tools!
```

### L0-meta/defaults/observability.yaml (Alerts & Logs)

```yaml
observability:
  alerting:
    # Alert defaults (not specific alerts!)
    default_severity: warning
    default_escalation_delay: 5m
    critical_escalation_delay: 1m

  dashboards:
    # Dashboard defaults
    default_refresh_interval: 30s
    default_time_range: 1h

  logging:
    retention_days: 30
    compression: enabled

  metrics:
    retention_days: 90
    scrape_interval: 60s
    evaluation_interval: 15s

# No alert names!
# No dashboard titles!
```

### L0-meta/defaults/operations.yaml (Incident Response)

```yaml
operations:
  escalation:
    # Escalation policy (abstract!)
    first_response_sla_minutes: 15
    escalation_levels: 3
    escalation_delay_minutes: 10

  incident_response:
    auto_restart_enabled: false
    auto_failover_enabled: false
    manual_approval_required: true

  change_management:
    change_approval_required: true
    change_validation_required: true
    rollback_enabled: true

  mttr_targets:
    critical: 5  # 5 minutes
    major: 30    # 30 minutes
    minor: 120   # 2 hours

# No runbook names!
# No escalation contact names!
```

---

## Принцип: Что Может Быть в L0

### ✅ АБСТРАКТНОЕ (в L0)
- Версия, метаинформация
- Polícy (security, backup, replication)
- Defaults (VM size, monitoring level, SLA)
- Requirements (encryption required, HA required)
- Strategies (backup schedule, alert severity)

### ❌ КОНКРЕТНОЕ (НЕ в L0)
- IP адреса
- Device names
- Hostnames
- Port numbers
- Specific resource amounts (CPU cores, memory)
- Alert/runbook/dashboard names

---

## Как L1-L7 Используют L0

```yaml
# L1 использует:
security:
  policy: ${L0.active_security_policy}  # базовый level
  ssh_timeout: ${L0.security[baseline].ssh_policy.idle_timeout}

# L3 использует:
storage:
  backup_schedule: ${L0.defaults.storage.backup.schedule}
  retention_days: ${L0.defaults.storage.backup.retention_days}

# L5 использует:
application:
  sla_target: ${L0.defaults.application.sla.target_uptime_percent}
  monitoring_level: ${L0.defaults.application.monitoring.level}

# L7 использует:
operations:
  mttr_target: ${L0.defaults.operations.mttr_targets.critical}
  escalation_policy: ${L0.defaults.operations.escalation}
```

**Все значения АБСТРАКТНЫЕ, никак не привязаны к L1!**

---

## Сравнение: Неправильная vs Правильная L0

### ❌ НЕПРАВИЛЬНАЯ (что я делал)

```yaml
# L0-meta/_index.yaml
defaults:
  primary_network_manager_device_ref: network-gateway  # Ссылка на L1!!! 🚫
  primary_router_ip: 192.168.88.1                      # IP адрес!!! 🚫
```

### ✅ ПРАВИЛЬНАЯ (этот подход)

```yaml
# L0-meta/_index.yaml
version: 4.0.0
active_security_policy: baseline

# ONLY abstract policies and defaults
defaults: !include_dir_sorted defaults/

# That's it! No references to L1, L2, etc.
```

---

## Summary

**L0 должна быть абсолютно независимой:**
- ✅ Знает версию, policy, defaults
- ❌ Не знает ничего о L1-L7
- ❌ Не содержит references на верхние слои
- ❌ Не содержит concrete values (IPs, names)

**L1-L7 используют L0:**
- Каждый слой берёт нужные polícy/defaults из L0
- Каждый слой РЕАЛИЗУЕТ эти polícy с concrete values
- Однонаправленная зависимость: L1-L7 → L0

**Результат:** Чистая архитектура без циклических зависимостей!
