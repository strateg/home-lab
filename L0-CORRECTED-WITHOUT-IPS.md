# L0 Meta Layer: Correct Design (WITHOUT IP Addresses)

**Дата:** 26 февраля 2026 г.
**Исправление:** Убрал IP адреса - это нарушение архитектуры

---

## Правильная L0 Structure

```
L0-meta/
├── _index.yaml                    # Глобальные polícy и settings
└── security/                      # Модульные security polícy
    ├── built-in/
    │   ├── baseline.yaml
    │   ├── strict.yaml
    │   └── relaxed.yaml
    └── custom/
```

---

## Содержимое: L0-meta/_index.yaml (ИСПРАВЛЕННОЕ)

```yaml
# ============================================================================
# L0 META - Global Configuration Policies
# This layer defines ABSTRACT policies, not specific IP addresses or devices
# IP addresses and specific hardware references belong to L1-Foundation
# ============================================================================

# === VERSION ===
version: 4.0.0
name: "Home Lab Infrastructure"
description: "Layered topology architecture"

# === GLOBAL DEFAULTS (Abstract, not specific) ===
defaults:
  # Network: Reference logical entities, not IP addresses
  primary_network_manager_device_ref: mikrotik-chateau  # Logical reference!
  primary_dns_resolver_ref: default-dns                 # Logical reference!
  ntp_source_ref: pool-ntp                              # Logical reference!
  # (Actual IPs for these are defined in L1-Foundation)

  # SLA/Monitoring
  default_sla_target: 99.0  # Abstract: 99% uptime
  default_monitoring_level: detailed  # Abstract: what level
  default_backup_retention_days: 30   # Abstract: how long

  # Firewall
  firewall_default_action: drop  # Abstract: policy
  firewall_enable_logging: true  # Abstract: policy

  # Encryption
  tls_minimum_version: "1.2"  # Abstract: requirement
  certificate_validation: required  # Abstract: policy

# === SECURITY POLICY SELECTION ===
# Choose which security politique to apply globally
security_policy: baseline  # Options: baseline, strict, relaxed, or custom

# === OPERATIONS STRATEGY ===
operations:
  backup_enabled: true
  backup_schedule: daily                 # Abstract: when
  backup_retention_days: 30              # Abstract: how long

  monitoring_enabled: true
  monitoring_level: detailed             # Abstract: verbosity level

  audit_logging_enabled: false           # Abstract: policy
  audit_retention_days: 30               # Abstract: how long

# === FEATURE FLAGS ===
# What capabilities should be available across topology?
features:
  high_availability: false     # Not applicable for single-point infra
  encryption_required: true    # Policy: always use encryption
  rate_limiting: true          # Policy: enable rate limiting
  geo_blocking: false          # Policy: don't block by geography

# === NOTES ===
notes: |
  ARCHITECTURAL PRINCIPLES:

  1. L0 defines ABSTRACT POLICIES
     - Security level (baseline/strict/relaxed)
     - Operational strategies (backup schedule, monitoring level)
     - Global defaults (SLA, encryption requirements)
     - Feature availability (what's enabled)

  2. L0 DOES NOT define:
     ✗ IP addresses (→ L1-Foundation)
     ✗ Specific device names (→ L1-Foundation)
     ✗ Hardware details (→ L1-Foundation)
     ✗ Port numbers (→ L2-Network)
     ✗ Service-specific settings (→ L5-Application)

  3. L1-Foundation IMPLEMENTS L0 policies:
     - Chooses device "mikrotik-chateau" and assigns IP 192.168.88.1
     - Chooses DNS server and assigns IP 192.168.88.1
     - Ensures chosen devices meet L0 requirements

  4. Testing Strategy:
     - Use git branches for experiments
     - Use terraform plan to validate changes
     - Use git revert for instant rollback
     - NO extra VMs needed

# === CHANGELOG ===
changelog:
  - version: 4.0.0
    date: 2026-02-26
    changes:
      - Simplified L0 design (abstract polícy only)
      - Modular security polícy (baseline/strict/relaxed)
      - Git-based testing (no extra VMs)
      - Removed IP addresses (belong in L1)
      - Removed device-specific references (belong in L1)
    rationale: "L0 should contain abstract policies, not concrete IP/hardware details"

# ============================================================================
# END L0 META
# All concrete IP addresses and device details are in L1-Foundation
# ============================================================================
```

---

## Правильное Разделение Слоёв

### ❌ НЕПРАВИЛЬНО (что я делал)

```yaml
# L0-meta/_index.yaml (WRONG!)
network:
  primary_router: mikrotik-chateau
  primary_router_ip: 192.168.88.1  ← IP АДРЕС В L0!!! 🚫
  primary_dns: 192.168.88.1         ← IP АДРЕС В L0!!! 🚫
  ntp_server: pool.ntp.org          ← КОНКРЕТНЫЙ СЕРВЕР!!! 🚫
```

### ✅ ПРАВИЛЬНО (новый подход)

```yaml
# L0-meta/_index.yaml (CORRECT!)
defaults:
  primary_network_manager_device_ref: mikrotik-chateau  ← Логический reference!
  primary_dns_resolver_ref: default-dns                 ← Логический reference!
  ntp_source_ref: pool-ntp                              ← Логический reference!
  # (Actual IPs are in L1-Foundation)
```

```yaml
# L1-foundation/devices/routers/mikrotik-chateau.yaml
device:
  id: mikrotik-chateau
  type: router
  ip: 192.168.88.1  ← IP АДРЕС ЗДЕСЬ! ✅

# L1-foundation/devices/network-services/dns.yaml
service:
  id: default-dns
  type: dns
  ip: 192.168.88.1  ← IP АДРЕС ЗДЕСЬ! ✅
```

---

## Что Находится В Каждом Слое

### L0 (Meta) - АБСТРАКТНОЕ
```yaml
✅ Версия
✅ Security polícy (baseline/strict/relaxed)
✅ Operational strategy (backup schedule, monitoring level)
✅ Global defaults (SLA target, encryption requirement)
✅ Logical references (device-ref, not IP)
✅ Feature flags (is HA enabled, is rate limiting enabled)

❌ IP адреса
❌ Конкретные devices
❌ Конкретные порты
❌ Конкретные hostnames
```

### L1 (Foundation) - КОНКРЕТНОЕ
```yaml
✅ IP адреса (192.168.88.1)
✅ Device names (mikrotik-chateau)
✅ Device types (router, switch, storage)
✅ Physical connections
✅ Specific ports
✅ Hostnames

❌ Security polícy (это из L0)
❌ Global defaults (это из L0)
❌ Operational strategy (это из L0)
```

---

## Как L1 Использует L0

```yaml
# L0 определяет ПОЛИТИКУ:
# L0-meta/_index.yaml
security_policy: baseline
firewall_default_action: drop
tls_minimum_version: "1.2"

---

# L1 РЕАЛИЗУЕТ политику:
# L1-foundation/devices/routers/mikrotik.yaml
device:
  id: mikrotik-chateau
  ip: 192.168.88.1          ← Конкретный IP
  security_policy_ref: baseline  ← References L0 polícy
  firewall_default: drop    ← Implements L0 requirement
  tls_minimum: "1.2"        ← Implements L0 requirement
```

---

## Исправленная L0 Philosophy

**L0 отвечает на вопросы:**
- ✅ Какая security política должна быть? (baseline)
- ✅ Нужны ли бэкапы? (yes)
- ✅ Как часто делать бэкапы? (daily)
- ✅ Сколько хранить бэкапы? (30 days)
- ✅ Какой SLA требуется? (99.0%)

**L0 НЕ отвечает на вопросы:**
- ❌ Какой IP у DNS? (это L1)
- ❌ Какой IP у роутера? (это L1)
- ❌ Какой hostname у сервера? (это L1)
- ❌ На каком порту слушает NTP? (это L2/L5)

---

## Практический Пример

### ✅ ПРАВИЛЬНО

```yaml
# L0-meta/_index.yaml
defaults:
  primary_network_manager_device_ref: network-gateway  ← Reference, not IP!
  default_backup_schedule: daily
  firewall_default_action: drop

# L1-foundation/devices/network/network-gateway.yaml
device:
  id: network-gateway
  type: router
  implementation: mikrotik-chateau
  ip: 192.168.88.1  ← Конкретный IP находится здесь
  firewall_default: drop  ← Наследует из L0
```

### ❌ НЕПРАВИЛЬНО

```yaml
# L0-meta/_index.yaml
defaults:
  primary_network_gateway_ip: 192.168.88.1  ← IP в L0!!! 🚫
  primary_router: mikrotik-chateau          ← Конкретный device!!! 🚫
```

---

## Summary

**Исправление:**
- ✅ Убрал IP адреса из L0
- ✅ Убрал конкретные device names из L0
- ✅ Заменил на логические references
- ✅ L0 теперь содержит только абстрактные polícy
- ✅ L1 содержит конкретные IP и devices

**Результат:** Топология теперь соответствует архитектурным принципам!
