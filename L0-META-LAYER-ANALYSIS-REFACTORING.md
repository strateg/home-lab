# L0 Meta Layer: Analysis, Refactoring & Optimization

**Date:** 26 февраля 2026 г.
**Status:** Complete analysis with refactoring recommendations

---

## Executive Summary

L0 (Meta) слой **критичен для масштабирования** — содержит версионирование, defaults и глобальные политики. Текущая структура **монолитна и неструктурирована**, что блокирует:

- ❌ Развитие security policies (смешаны с defaults)
- ❌ Управление многоокружениями (жестко hardcoded `environment: production`)
- ❌ Вариативность в разных регионах (нет region/site policies)
- ❌ Версионирование политик (нет истории изменений)
- ❌ Наследование и переопределение policies

**Рекомендация:** Модульная рефакторизация L0 в 5 отдельных файлов с иерархией и наследованием.

---

## PART 1: Current State Analysis

### L0 Current Structure

```yaml
L0-meta.yaml (монолит, 76 строк)
├── version (1 свойство)
├── metadata (changelog, org, environment)
├── defaults (refs)
└── security_policy (1 базовая политика)
```

### Problems Identified

#### 1. **Monolithic Design**
- Всё в одном файле
- Трудно обновлять отдельные части
- Высокий риск конфликтов при merge

#### 2. **No Policy Hierarchy**
```yaml
security_policy:
  - id: sec-baseline  # Только базовая политика
    # Нет: sec-strict, sec-relaxed, sec-development
```

**Impact:** L1-L7 не могут применять разные policies в зависимости от контекста (production vs staging).

#### 3. **No Multi-Environment Support**
```yaml
environment: production  # Hardcoded!
```

**Impact:** Нельзя использовать один topology.yaml для разных окружений (testing, staging, production).

#### 4. **No Regional/Site Defaults**
```yaml
# Нет:
site: us-east-1
region: north-america
```

**Impact:** Нельзя применять region-specific policies (firewall rules, compliance, etc.).

#### 5. **No Policy Inheritance**
```yaml
# Нет: extends, parent_policy, overrides
```

**Impact:** При добавлении новой политики нужно дублировать все свойства базовой политики.

#### 6. **No Audit Trail**
```yaml
# Нет: created_by, modified_by, modified_at
```

**Impact:** Невозможно отследить, кто и когда изменил политику.

#### 7. **Changelog in Meta**
```yaml
changelog:  # Зачем в L0? Должен быть отдельно
  - version: 1.0.0
    date: '2025-10-06'
```

**Impact:** Смешивание concerns (версионирование и changelog).

---

## PART 2: Proposed Refactored L0 Structure

### New L0 Modular Design

```
L0-meta/
├── _index.yaml              # Главный файл L0 (version, includes)
├── version.yaml             # Version info (semantic versioning)
├── environment-config.yaml  # Multi-env support (prod/staging/dev)
├── defaults/                # Global defaults by type
│   ├── refs.yaml           # Default refs (sec policy, network manager, etc.)
│   ├── compliance.yaml     # Default compliance settings
│   ├── audit.yaml          # Default audit/logging settings
│   └── feature-flags.yaml  # Feature toggles for L1-L7
├── security-policies/       # Modular, hierarchical security policies
│   ├── _base.yaml          # Base/abstract policy template
│   ├── baseline.yaml       # Production baseline
│   ├── strict.yaml         # High-security variant (extends baseline)
│   ├── relaxed.yaml        # Development variant (extends baseline)
│   └── policy-registry.yaml# Policy index + inheritance
├── regional-policies/       # Region-specific overrides
│   ├── us-east.yaml
│   ├── eu-west.yaml
│   └── apac.yaml
├── capability-matrix.yaml   # What features are available per environment/region
└── changelog.yaml           # Version history (separate from meta)
```

### Advantages

1. ✅ **Modularity:** Each concern is separate
2. ✅ **Hierarchy:** Policy inheritance (strict extends baseline)
3. ✅ **Multi-env:** Different policies for prod/staging/dev
4. ✅ **Regional:** Site-specific overrides
5. ✅ **Extensibility:** Easy to add new policy types
6. ✅ **Auditability:** Track who changed what

---

## PART 3: Detailed Refactoring

### File 1: `L0-meta/_index.yaml` (NEW)

```yaml
# L0 Meta - Index and Entry Point
# Version and includes for all L0 sub-modules

L0_version: !include version.yaml

L0_environment: !include environment-config.yaml

L0_defaults:
  refs: !include defaults/refs.yaml
  compliance: !include defaults/compliance.yaml
  audit: !include defaults/audit.yaml
  feature_flags: !include defaults/feature-flags.yaml

L0_security:
  policies: !include_dir_sorted security-policies/
  registry: !include security-policies/policy-registry.yaml

L0_regional:
  policies: !include_dir_sorted regional-policies/

L0_capabilities: !include capability-matrix.yaml

L0_changelog: !include changelog.yaml
```

### File 2: `L0-meta/version.yaml` (NEW)

```yaml
# Semantic versioning for topology

semantic_version: 4.0.0

version_info:
  major: 4
  minor: 0
  patch: 0
  prerelease: null  # alpha, beta, rc, or null for stable
  build_metadata: null

release_cycle:
  release_date: 2026-02-17
  support_until: 2027-02-17  # 1 year support window
  eol_date: 2028-02-17       # Extended support

versioning_policy:
  breaking_changes: false   # Are there breaking changes vs v3.x?
  requires_migration: false # Do L1-L7 need updates?
  terraform_compatible: true
  ansible_compatible: true

api_version: v4  # For generators/validators
```

### File 3: `L0-meta/environment-config.yaml` (NEW)

```yaml
# Multi-environment configuration
# Allows one topology.yaml to work with prod/staging/dev

environments:

  production:
    enabled: true
    description: Production home lab infrastructure
    security_policy_ref: sec-strict
    regional_policy_ref: us-east
    defaults:
      backup_enabled: true
      monitoring_enabled: true
      logging_level: info
      audit_logging: true
    constraints:
      require_high_availability: true
      require_sla: 99.9
      require_encryption: all_traffic

  staging:
    enabled: true
    description: Staging environment for testing
    security_policy_ref: sec-baseline
    regional_policy_ref: us-east
    defaults:
      backup_enabled: true
      monitoring_enabled: true
      logging_level: debug
      audit_logging: false  # Optional in staging
    constraints:
      require_high_availability: false
      require_sla: 99.0
      require_encryption: critical_only

  development:
    enabled: true
    description: Local development environment
    security_policy_ref: sec-relaxed
    regional_policy_ref: local
    defaults:
      backup_enabled: false
      monitoring_enabled: false
      logging_level: debug
      audit_logging: false
    constraints:
      require_high_availability: false
      require_sla: none
      require_encryption: none

# Current active environment (can be overridden via CLI: --environment=staging)
active_environment: production
```

### File 4: `L0-meta/defaults/refs.yaml` (NEW)

```yaml
# Global default references
# Used as fallback when specific L1-L7 components don't specify overrides

defaults:

  security:
    policy_ref: sec-baseline
    ssh_key_ref: default-ssh-key
    firewall_policy_ref: fw-default

  network:
    manager_device_ref: mikrotik-chateau
    ntp_server_ref: ntp-pool
    dns_server_ref: dns-primary
    trust_zone_ref: internal

  storage:
    backup_pool_ref: backup-nfs
    log_storage_ref: logs-lv

  monitoring:
    alert_policy_ref: alert-baseline
    slo_ref: slo-default
    dashboard_ref: dash-overview

  compliance:
    audit_policy_ref: audit-baseline
    retention_policy_ref: retention-1year

  operational:
    incident_response_runbook_ref: rb-default
    escalation_policy_ref: esc-standard
    change_management_policy_ref: cm-standard
```

### File 5: `L0-meta/security-policies/_base.yaml` (NEW)

```yaml
# Base security policy template
# All other policies inherit from this

_abstract_policy_template:
  # Metadata
  id: null  # Override in child
  description: null
  parent_policy: null  # For inheritance
  version: 1.0.0
  created_at: null
  created_by: null
  last_modified_at: null
  last_modified_by: null

  # Password policy
  password_policy:
    min_length: 12
    require_special_chars: false
    require_numbers: false
    require_uppercase: false
    max_age_days: null
    history_count: 0
    lockout_threshold: null

  # SSH policy
  ssh_policy:
    permit_root_login: null  # prohibit-password, no, yes
    password_authentication: false
    pubkey_authentication: true
    port: 22
    max_auth_tries: 3
    timeout_seconds: 300

  # Firewall policy
  firewall_policy:
    default_action: drop  # drop or accept
    log_blocked: false
    rate_limiting: false
    connection_tracking: true

  # Encryption policy
  encryption_policy:
    tls_minimum_version: "1.2"
    cipher_suites: []  # Use system defaults if empty
    certificate_validation: true

  # Audit policy
  audit_policy:
    log_authentication: false
    log_authorization: false
    log_configuration_changes: false
    log_retention_days: 30

  # API policy
  api_policy:
    rate_limiting_enabled: false
    api_key_rotation_days: null
    api_token_expiry_days: null
```

### File 6: `L0-meta/security-policies/baseline.yaml` (NEW)

```yaml
# Production baseline security policy
# Standard security for production infrastructure

id: sec-baseline
description: Production baseline security policy
parent_policy: null  # No parent, this is base
version: 4.0.0
created_at: 2026-02-16
created_by: dmitri@home-lab
last_modified_at: 2026-02-26
last_modified_by: dmitri@home-lab

password_policy:
  min_length: 16
  require_special_chars: true
  require_numbers: true
  require_uppercase: true
  max_age_days: 90
  history_count: 5
  lockout_threshold: 5

ssh_policy:
  permit_root_login: prohibit-password
  password_authentication: false
  pubkey_authentication: true
  port: 22
  max_auth_tries: 3
  timeout_seconds: 600

firewall_policy:
  default_action: drop
  log_blocked: true
  rate_limiting: true
  connection_tracking: true

encryption_policy:
  tls_minimum_version: "1.2"
  cipher_suites: [TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384, TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256]
  certificate_validation: true

audit_policy:
  log_authentication: true
  log_authorization: true
  log_configuration_changes: true
  log_retention_days: 365

api_policy:
  rate_limiting_enabled: true
  api_key_rotation_days: 90
  api_token_expiry_days: 30
```

### File 7: `L0-meta/security-policies/strict.yaml` (NEW)

```yaml
# Strict/High-security policy
# Extends baseline with additional hardening

id: sec-strict
description: High-security variant (extends baseline)
parent_policy: sec-baseline
version: 4.0.0
created_at: 2026-02-26
created_by: dmitri@home-lab

# Overrides (inherits rest from parent)
password_policy:
  min_length: 20  # Stricter
  max_age_days: 60  # More frequent rotation
  history_count: 10  # Remember more

ssh_policy:
  permit_root_login: no  # No root SSH at all
  password_authentication: false
  port: 2222  # Non-standard port

firewall_policy:
  default_action: drop
  log_blocked: true
  rate_limiting: true
  geo_blocking: true  # New!

audit_policy:
  log_authentication: true
  log_authorization: true
  log_configuration_changes: true
  log_retention_days: 730  # 2 years
  encryption_of_logs: required  # New!
```

### File 8: `L0-meta/security-policies/relaxed.yaml` (NEW)

```yaml
# Relaxed/Development policy
# Extends baseline with development-friendly settings

id: sec-relaxed
description: Development variant (extends baseline)
parent_policy: sec-baseline
version: 4.0.0
created_at: 2026-02-26

# Overrides
password_policy:
  min_length: 8  # Shorter for dev
  require_special_chars: false  # Optional
  max_age_days: null  # Never expire in dev

ssh_policy:
  permit_root_login: yes  # Allow root for convenience
  password_authentication: true  # Allow password
  max_auth_tries: 10  # More lenient

firewall_policy:
  default_action: accept  # Default accept in dev
  log_blocked: false
  rate_limiting: false

audit_policy:
  log_authentication: false
  log_authorization: false
  log_configuration_changes: false
  log_retention_days: 7  # Short retention
```

### File 9: `L0-meta/security-policies/policy-registry.yaml` (NEW)

```yaml
# Policy registry and inheritance map
# Shows all available policies and their relationships

policy_registry:

  sec-baseline:
    type: production
    parent: null
    description: Standard production security policy
    applicable_to:
      environments: [staging, production]
      regions: [all]
    approved_by: security-team
    approved_date: 2026-02-16

  sec-strict:
    type: production
    parent: sec-baseline
    description: High-security variant for sensitive data
    applicable_to:
      environments: [production]
      regions: [all]
    approved_by: security-team
    approved_date: 2026-02-26

  sec-relaxed:
    type: development
    parent: sec-baseline
    description: Development-friendly variant
    applicable_to:
      environments: [development]
      regions: [all]
    approved_by: dev-team
    approved_date: 2026-02-26

# Inheritance tree
inheritance_graph:
  sec-baseline:
    children: [sec-strict, sec-relaxed]
    depth: 0
  sec-strict:
    parent: sec-baseline
    depth: 1
  sec-relaxed:
    parent: sec-baseline
    depth: 1
```

### File 10: `L0-meta/changelog.yaml` (NEW - MOVED from metadata)

```yaml
# Version changelog
# Separate from meta for clarity

changelog:

  - version: 4.0.0
    date: 2026-02-17
    released_by: dmitri@home-lab
    changes:
      - Layered OSI-like architecture (L0-L7), strict downward references
      - Modular L0 structure (version, environment, security policies)
      - Multi-environment support (prod/staging/dev)
      - Policy inheritance hierarchy
    breaking_changes:
      - Topology refs changed from flat to hierarchical
      - Security policy now environment-specific
    migration_guide: "See docs/MIGRATION-4.0.0.md"

  - version: 3.0.0
    date: 2026-02-16
    released_by: dmitri@home-lab
    changes:
      - Major architecture redesign
      - MikroTik Chateau as central router
      - Orange Pi 5 as dedicated app server

  - version: 2.1.0
    date: 2025-10-10
    changes: Phase 2 improvements

  - version: 2.0.0
    date: 2025-10-09
    changes: Restructured with separation of concerns

  - version: 1.1.0
    date: 2025-10-09
    changes: Trust zones and metadata enhancements

  - version: 1.0.0
    date: 2025-10-06
    changes: Initial Infrastructure-as-Data structure

# Release notes
release_notes:
  current: 4.0.0
  latest_stable: 4.0.0
  lts_version: 3.0.0
  lts_support_until: 2027-02-16

# Upgrade path
upgrade_path:
  "1.x to 2.x": "Requires ref refactoring, see docs/UPGRADE-2.0.0.md"
  "2.x to 3.x": "MikroTik router migration, see docs/UPGRADE-3.0.0.md"
  "3.x to 4.x": "Modular L0, policy inheritance, see docs/UPGRADE-4.0.0.md"
```

---

## PART 4: Migration Path (L0 Refactoring)

### Phase 1: Preparation (Week 1)
- [ ] Create L0-meta/ directory
- [ ] Create version.yaml, environment-config.yaml, defaults/
- [ ] Review security policies (baseline, strict, relaxed)
- [ ] Document current L0-meta.yaml for reference

### Phase 2: Implementation (Week 2)
- [ ] Create all policy files
- [ ] Implement policy registry and inheritance
- [ ] Create _index.yaml that includes all modules
- [ ] Update topology-tools validators to load modular L0

### Phase 3: Migration (Week 3)
- [ ] Update L0-meta.yaml to use `!include L0-meta/_index.yaml`
- [ ] Test with all generators (Terraform, Ansible, Docs)
- [ ] Verify multi-environment support works
- [ ] Update documentation

### Phase 4: Validation (Week 4)
- [ ] Run full validator suite
- [ ] Test with staging environment
- [ ] Test with production environment
- [ ] Create migration guide for team

---

## PART 5: Benefits for Upper Layers (L1-L7)

### How L1 Uses New L0

```yaml
# L1-foundation/devices/proxmox/pve-01.yaml
device:
  id: pve-01
  type: proxmox-node

  # Now can reference security policy
  security_policy_ref: sec-baseline  # From L0

  # Can inherit defaults from L0
  ssh_port: ${L0.defaults.refs.security.ssh_port}
  ntp_servers: ${L0.defaults.refs.network.ntp_servers}
```

### How L2 Uses New L0

```yaml
# L2-network/firewall/policies/_index.yaml
firewall_policies:
  - id: policy-default
    base_policy_ref: ${L0.security.policies.baseline.firewall_policy}
    # Customize per policy without duplication
    rate_limiting: true
```

### How L5 Uses New L0

```yaml
# L5-application/services/core-services.yaml
services:
  - id: svc-nextcloud
    # Inherits audit requirements from L0
    audit_policy_ref: ${L0.defaults.refs.audit}
    # Gets environment-specific SLO from L0
    slo_ref: ${L0.environments[active].constraints.require_sla}
```

### How L6 Uses New L0

```yaml
# L6-observability/alerts/policies/
service_alerts:
  svc-nextcloud:
    # Inherits logging from L0
    log_enabled: ${L0.environments[active].defaults.audit_logging}
    retention: ${L0.security.baseline.audit_policy.log_retention_days}
```

### How L7 Uses New L0

```yaml
# L7-operations/incident-response/
incident_policies:
  - id: critical-incident
    # Uses SLA from active environment in L0
    escalation_sla_minutes: ${L0.environments[active].constraints.require_sla}
    audit_required: ${L0.environments[active].defaults.audit_logging}
```

---

## PART 6: Validation & Testing

### New Validators for L0

```python
# topology-tools/validators/l0_validators.py

def validate_policy_inheritance(l0_policies):
    """Ensure policy inheritance is acyclic"""
    for policy_id, policy in l0_policies.items():
        if policy.get('parent_policy'):
            parent = l0_policies[policy['parent_policy']]
            assert parent is not None, f"Parent {policy['parent_policy']} not found"
    # Check for cycles
    ...

def validate_environment_config(l0_env):
    """Ensure all environments reference valid policies"""
    for env_name, env_config in l0_env.items():
        policy_ref = env_config['security_policy_ref']
        assert policy_ref in l0_policies, f"Policy {policy_ref} not found"

def validate_defaults_refs(l0_defaults):
    """Ensure all default refs point to valid entities"""
    # Check that network_manager_device_ref points to real device
    # Check that security_policy_ref points to real policy
    ...
```

---

## Summary: L0 Refactoring Impact

| Aspect | Before | After | Benefit |
|--------|--------|-------|---------|
| **Structure** | Monolith (76 lines) | Modular (9 files) | Clear separation of concerns |
| **Policies** | 1 hardcoded | 3+ hierarchical with inheritance | Policy reuse, no duplication |
| **Environments** | Hardcoded production | 3 full configs (prod/staging/dev) | One topology for all envs |
| **Defaults** | Mixed in meta | Separate L0/defaults/ | Easy to find and override |
| **Versioning** | In meta | Separate changelog.yaml | Clean git history |
| **Auditability** | Who changed? | created_by, modified_by | Full audit trail |

---

**Next:** Create ADR 0049 for this L0 refactoring
