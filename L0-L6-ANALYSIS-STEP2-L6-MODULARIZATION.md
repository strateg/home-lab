# STEP 2: L6 Observability Modularization Design

**Date:** 26 февраля 2026 г.

---

## Current L6 Structure (Flat)

```
L6-observability/
├── healthchecks.yaml
├── network-monitoring.yaml
├── alerts.yaml
├── notification-channels.yaml
└── dashboard.yaml
```

---

## Proposed L6 Structure (Modular + Three-Layer)

```
L6-observability/
│
├── _index.yaml                          # L6 entry point (includes all submodules)
│
├── metrics-definitions/                 # NEW: Metric types & aggregation rules
│   ├── _index.yaml
│   ├── system-metrics.yaml              # CPU, memory, disk, network
│   ├── application-metrics.yaml         # Service-level: req/sec, latency, errors
│   ├── storage-metrics.yaml             # IOPS, throughput, capacity
│   └── custom-metrics.yaml              # User-defined metrics
│
├── healthchecks/                        # MOVED/EXPANDED: Liveness & readiness
│   ├── _index.yaml
│   ├── by-service/
│   │   ├── _index.yaml
│   │   ├── svc-nextcloud.yaml
│   │   ├── svc-postgres.yaml
│   │   └── svc-*.yaml
│   └── by-component/
│       ├── network.yaml                 # Network health (ping, MTU, routing)
│       ├── storage.yaml                 # Storage health (SMART, space, R/W)
│       └── system.yaml                  # System health (load, processes)
│
├── alerts/                              # REFACTORED: Hierarchical alert rules
│   ├── _index.yaml
│   ├── definitions/                     # Alert type definitions (templates)
│   │   ├── availability.yaml            # Service up/down alerts
│   │   ├── performance.yaml             # CPU/memory/latency high alerts
│   │   ├── capacity.yaml                # Disk/network capacity alerts
│   │   ├── security.yaml                # Firewall blocks, auth failures
│   │   └── custom.yaml
│   │
│   └── policies/                        # Alert instantiation & routing
│       ├── svc-nextcloud-alerts.yaml
│       ├── svc-postgres-alerts.yaml
│       ├── infrastructure-alerts.yaml
│       └── _service-alert-bindings.yaml # INDEX: service_id → alert_ids
│
├── dashboards/                          # REFACTORED: Named by purpose
│   ├── _index.yaml
│   ├── overview.yaml                    # System health overview (1 dashboard)
│   ├── by-service/
│   │   ├── svc-nextcloud.yaml
│   │   ├── svc-postgres.yaml
│   │   └── svc-*.yaml
│   └── by-component/
│       ├── infrastructure.yaml          # CPU, memory, disk, network
│       ├── storage.yaml                 # Storage performance & capacity
│       └── network.yaml                 # Traffic, latency, errors
│
├── notification-channels/               # REFACTORED: Grouped by type
│   ├── _index.yaml
│   ├── by-type/
│   │   ├── email.yaml                   # Slack, Discord, email-to-list
│   │   ├── sms.yaml
│   │   ├── webhook.yaml                 # Webhook for external systems
│   │   └── in-app.yaml                  # In-app notifications
│   │
│   └── escalation-policies.yaml         # NEW: Escalation rules & routing
│
├── network-monitoring/                  # KEPT/EXPANDED: Network-specific
│   ├── _index.yaml
│   ├── tap-points.yaml                  # Mirror/TAP interfaces on bridges
│   ├── traffic-analysis.yaml            # DPI rules, flows, SLA metrics
│   └── anomaly-detection.yaml           # Baseline traffic patterns
│
├── sla-slo/                             # NEW: SLA/SLO definitions
│   ├── _index.yaml
│   ├── service-sla-templates.yaml       # Availability SLA templates (99.9%, 99.99%)
│   ├── svc-nextcloud-slo.yaml           # Service-specific SLOs
│   ├── svc-postgres-slo.yaml
│   └── svc-*.yaml
│
├── incident-response/                   # NEW: Runbooks & automation
│   ├── _index.yaml
│   ├── runbooks/
│   │   ├── svc-nextcloud-down.yaml      # Steps to recover nextcloud
│   │   ├── svc-postgres-disk-full.yaml  # Steps to handle disk-full
│   │   ├── network-degradation.yaml
│   │   └── cascade-failure.yaml
│   │
│   └── automated-responses/             # Auto-remediation rules
│       ├── disk-cleanup.yaml            # Auto-delete old logs
│       ├── service-restart.yaml         # Auto-restart failed services
│       └── failover.yaml                # Auto-failover to standby
│
└── planning/                            # NEW: Registries & contracts
    ├── _index.yaml
    ├── alert-strategy.yaml              # Global alert severity, dedup rules
    ├── metric-collection-strategy.yaml  # Which metrics to collect (cost/benefit)
    ├── dashboard-coverage.yaml          # Which services/components have dashboards
    ├── notification-routing.yaml        # How to route alerts to channels
    └── service-observability-contract.yaml  # What L5 services MUST provide (logs, metrics, health endpoints)
```

---

## Module API Contracts

### metrics-definitions/ API
**Exported:**
- `metrics[*].id` — unique metric identifier (e.g., `cpu-utilization`)
- `metrics[*].type` — type (gauge, counter, histogram)
- `metrics[*].unit` — unit (%, bytes, requests, seconds)
- `metrics[*].aggregation` — aggregation rules (avg, max, sum)

**Consumed by:** alerts (threshold definitions), dashboards (query specs), sla-slo (SLO targets)

---

### healthchecks/ API
**Exported:**
- `healthchecks[*].id` — unique ID (e.g., `hc-nextcloud-http`)
- `healthchecks[*].type` — type (http, tcp, icmp, custom-script)
- `healthchecks[*].target_ref` — L4/L5 reference (lxc_id, service_id)
- `healthchecks[*].interval` — check interval (seconds)

**Consumed by:** alerts (trigger on healthcheck failure), dashboards (health status indicator)

---

### alerts/ API
**Definition API (`alerts/definitions/*.yaml`):**
- `alert_templates[*].id` — e.g., `alert-tpl-cpu-high`
- `alert_templates[*].condition` — threshold or expression (metric > 80%)
- `alert_templates[*].severity` — critical, warning, info
- `alert_templates[*].description`

**Policy API (`alerts/policies/*.yaml`):**
- `service_alerts[*].service_ref` — L5 service ID
- `service_alerts[*].enabled_templates` — which templates apply to this service
- `service_alerts[*].thresholds_override` — service-specific values (CPU-high: 85% vs default 80%)

**Index API (`alerts/policies/_service-alert-bindings.yaml`):**
```yaml
service_alert_bindings:
  svc-nextcloud:
    alert_ids: [alert-nextcloud-http-down, alert-nextcloud-disk-full]
  svc-postgres:
    alert_ids: [alert-postgres-connection-pool-high, alert-postgres-replication-lag]
```

---

### dashboards/ API
**Exported:**
- `dashboards[*].id` — unique ID (e.g., `dash-svc-nextcloud`)
- `dashboards[*].title` — display title
- `dashboards[*].panels[*]` — panels (each with metric query, alert refs)
- `dashboards[*].tags` — labels (service, component, infrastructure)

**Consumed by:** incident-response (runbooks link to dashboards), planning (coverage tracking)

---

### notification-channels/ API
**Channel API:**
- `channels[*].id` — e.g., `ch-slack-ops`
- `channels[*].type` — slack, email, sms, webhook
- `channels[*].config` — channel-specific config (webhook URL, email list)

**Escalation Policy API (`escalation-policies.yaml`):**
- `escalation_policies[*].id` — policy ID (e.g., `esc-critical`)
- `escalation_policies[*].severity_level` — critical, warning, info
- `escalation_policies[*].channels` — list of channels in order
- `escalation_policies[*].timers` — escalate after 15min, 1hr, etc.

---

### sla-slo/ API
**Exported:**
- `slos[*].id` — unique SLO ID (e.g., `slo-nextcloud-availability`)
- `slos[*].service_ref` — L5 service ID
- `slos[*].target` — availability target (99.9%)
- `slos[*].error_budget` — max downtime per month (2.16 hours for 99.9%)
- `slos[*].alert_at` — alert when error budget used X%

**Consumed by:** alerts (SLO breach alert), dashboards (error budget tracker), incident-response (SLO-driven incident priority)

---

### incident-response/ API
**Runbook API:**
- `runbooks[*].id` — e.g., `rb-nextcloud-down`
- `runbooks[*].trigger_alert_id` — which alert triggers this runbook
- `runbooks[*].steps[*]` — ordered steps (manual or automated)
- `runbooks[*].escalation_after_min` — escalate if not resolved in N minutes

**Automated Response API:**
- `automations[*].id` — e.g., `auto-disk-cleanup`
- `automations[*].trigger_condition` — "disk_usage > 95%"
- `automations[*].actions` — what to execute (script, API call)

---

### planning/ API
**Alert Strategy:**
- `alert_deduplication_rules` — dedup similar alerts from same service
- `alert_grouping_rules` — group related alerts (e.g., all network alerts together)
- `noise_suppression` — suppress transient alerts (flapping rules)

**Service Observability Contract:**
- `required_metrics` — metrics all services must expose (req/sec, error rate, latency)
- `required_health_endpoints` — all services must have /health, /readiness
- `required_logging` — structured JSON logs to stdout
- `optional_dashboards` — recommended dashboard panels for each service type

---

## Interdependencies Matrix

```
metrics-definitions
    ↓ (threshold specs)
   alerts, sla-slo, dashboards
    ↓
healthchecks → alerts → dashboards, incident-response
    ↓
dashboards → incident-response
    ↓
notification-channels ← alerts (routing)
    ↓
escalation-policies (manage channel order/timing)
    ↓
incident-response (runbooks consume alerts, dashboards, SLOs)
    ↓
planning (covers all: alert strategy, contract, coverage)
```

---

## Missing Modules (To Add)

| Module | Purpose | Example Fields |
|--------|---------|-----------------|
| `metrics-definitions/` | Define metric types & units | metric_id, unit, aggregation |
| `sla-slo/` | Service level objectives | service_ref, target %, error_budget |
| `incident-response/` | Runbooks & automated responses | trigger_alert_id, steps[], automations[] |
| `notification-channels/escalation-policies.yaml` | Routing & escalation | severity, channels[], timers[] |
| `planning/` | Registries & contracts | alert strategy, service contract, coverage |

---

## Benefits of This Structure

1. **Scalability:** L6 can grow to 1000+ alerts (10x) without file-size explosion
2. **Clarity:** Alert definitions separate from instantiation (template + policy pattern)
3. **Reusability:** Alert templates shared across services; SLO templates reused
4. **Service-centric:** All service monitoring grouped together (by-service/)
5. **Integration:** Incident-response uses alerts + dashboards + SLOs (no duplication)
6. **Contracts:** planning/ layer enforces service-observability expectations

---

**Next:** Proceed to STEP 3 (Cross-Layer Redundancy & Optimization Analysis)
