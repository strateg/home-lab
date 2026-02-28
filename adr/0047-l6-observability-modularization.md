# ADR 0047: L6 Observability Modularization

**Date:** 2026-02-26
**Updated:** 2026-03-01
**Status:** Partially Implemented
**Trigger:** Implement remaining phases when alerts > 50 OR services > 30

---

## Context

Current L6 observability layer has simple flat structure:
- `alerts.yaml` - 11 alerts
- `healthchecks.yaml` - health checks
- `dashboard.yaml` - dashboard definitions
- `network-monitoring.yaml` - network monitoring
- `notification-channels.yaml` - notification channels

**Total:** ~600 lines across 5 files.

This structure is **sufficient for current scale**. This ADR documents future modularization plan when growth requires it.

---

## Current State (Phase 1 + Phase 2 Partial)

**Structure:**
```
L6-observability/
├── alerts.yaml              # 11 alerts, hierarchical naming
├── healthchecks.yaml        # IP derivation via target_ref
├── dashboard.yaml
├── network-monitoring.yaml  # IP derivation via target_ref
└── notification-channels.yaml
```

**Naming:** Hierarchical per ADR 0048 (e.g., `alert-infra.router-down`, `alert-app.service-down`).

**IP Derivation:** Implemented via `target_ref` pattern (ADR 0044 extension to L6).

---

## Implemented Changes (2026-03-01)

### Phase 2: Naming Convention - COMPLETED

**Actions taken:**
1. Renamed all 11 alerts to hierarchical naming pattern:
   - `alert-<domain>.<service>-<type>`
   - Domains: `infra`, `app`, `power`, `ops`, `security`

2. Updated JSON Schema pattern:
   - From: `^alert-[a-z0-9-]+$`
   - To: `^alert-[a-z]+\.[a-z0-9_-]+-[a-z-]+$`

**Alert rename mapping:**
| Old ID | New ID | Domain |
|--------|--------|--------|
| `alert-router-down` | `alert-infra.router-down` | infra |
| `alert-internet-down` | `alert-infra.internet-down` | infra |
| `alert-lte-failover-active` | `alert-infra.lte-failover` | infra |
| `alert-disk-full` | `alert-infra.disk-critical` | infra |
| `alert-memory-critical` | `alert-infra.memory-critical` | infra |
| `alert-temperature-high` | `alert-infra.temperature-high` | infra |
| `alert-service-down` | `alert-app.service-down` | app |
| `alert-ups-on-battery` | `alert-power.ups-battery` | power |
| `alert-ups-low-battery` | `alert-power.ups-low` | power |
| `alert-backup-failed` | `alert-ops.backup-failed` | ops |
| `alert-certificate-expiry` | `alert-security.cert-expiry` | security |

### IP Derivation Extension to L6 - COMPLETED

**Actions taken:**
1. Replaced hardcoded IPs with `target_ref` objects in healthchecks.yaml
2. Replaced hardcoded IPs with `target_ref` objects in network-monitoring.yaml
3. Added `url_ref` pattern for HTTP checks

**Pattern:**
```yaml
# Before (hardcoded)
- type: ping
  target: 192.168.88.1

# After (derived)
- type: ping
  target_ref:
    device_ref: rtr-mikrotik-chateau
    network_ref: net-lan
```

**Benefits:**
- Single source of truth for IPs (L2 ip_allocations)
- Automatic propagation when IPs change
- Validated refs at topology validation time

---

## Future Design (When Triggered)

### Phase 3: Template System (alerts > 100)

**Trigger:** Alert count exceeds 100 OR significant duplication detected.

**Action:** Implement Template + Policy pattern:

```yaml
# alerts/definitions/availability.yaml (reusable template)
alert_templates:
  - id: alert-tpl-availability
    condition: healthcheck.status == down
    severity: critical
    description: "Service {{ service_name }} is down"

# alerts/policies/web.nextcloud.yaml (service-specific)
service_alerts:
  svc-web.nextcloud:
    enabled_templates: [alert-tpl-availability, alert-tpl-disk-full]
    thresholds_override:
      disk_full_threshold: 95%
```

**Structure:**
```
L6-observability/
├── alerts/
│   ├── definitions/     # Reusable templates
│   └── policies/        # Service-specific bindings
├── healthchecks/
├── dashboards/
├── notification-channels/
├── network-monitoring/
└── sla-slo/             # SLA/SLO definitions
```

### Phase 4: Auto-Generation (services > 50)

**Trigger:** Service count exceeds 50.

**Action:** Generate L6 artifacts from L5 service definitions:

```yaml
# L5 service definition (source of truth)
services:
  - id: svc-web.nextcloud
    tier: critical              # -> SLO 99.9%
    alert_templates: [availability, disk-full]
    dashboard_type: web-service

# Auto-generated at validation time:
# - L6-observability/alerts/policies/svc-web.nextcloud.yaml
# - L6-observability/dashboards/dash-app-web.nextcloud.yaml
# - L6-observability/sla-slo/svc-web.nextcloud.yaml
```

---

## Out of Scope

The following belong to **L7 Operations**, not L6:
- Incident response runbooks
- Operational planning
- Recovery automation

See L7-operations.yaml for these concerns.

---

## Consequences

### Implemented (Current)

**Positive:**
- Hierarchical naming prevents collisions at scale
- IP derivation reduces maintenance burden
- Validated refs catch errors early
- Alerts grouped by domain for clarity

**Trade-offs:**
- Schema update required for new naming pattern
- Generators need IP resolution logic (future)

### If Fully Implemented (Future)

**Positive:**
- Scalability to 1000+ alerts via template reuse
- Service-centric organization
- Reduced duplication
- Validated service<->alert bindings

**Trade-offs:**
- Migration effort for existing alerts
- Generator development required
- Additional validator complexity

---

## References

- ADR 0044: IP Derivation from Refs
- ADR 0048: Naming conventions and scalability strategy
- `topology/L6-observability/` - Current implementation
- `topology-tools/schemas/topology-v4-schema.json` - Updated schema

---

**Review Date:** When alert count approaches 50
