# ADR 0047: L6 Observability Modularization & Service-Centric Architecture

**Date:** 2026-02-26
**Status:** Proposed
**Stakeholders:** Infrastructure team, DevOps, Monitoring engineers

---

## Context

Current L6 observability layer (healthchecks, alerts, dashboards, notifications) is **monolithic and unstructured**:
- Alert naming flat (1000+ at 10x scale, collision risk)
- Service↔alert binding unvalidated (loose coupling)
- Alert definitions mixed with instantiation (hard to reuse)
- Missing modules: SLA/SLO, incident-response playbooks, metrics definitions
- No integration with L5 services (alerts don't know service type/tier)
- L7 operations isolated (runbooks hardcoded, not data-driven)

**Constraints:**
- Backward compatibility: generated Grafana dashboards must remain valid
- Validator complexity: avoid O(n²) reference resolution
- Storage: YAML must remain human-readable at 1000+ alerts

---

## Decision

### 1. Modularize L6 into Three Sub-Layers

```
L6-observability/
├── metrics-definitions/       # Metric types & aggregation rules
├── healthchecks/              # Liveness & readiness checks (by service, by component)
├── alerts/                    # Alert definitions (templates) + policies (instantiation)
├── dashboards/                # Named by purpose (overview, by-service, by-component)
├── notification-channels/     # Channels + escalation policies
├── network-monitoring/        # Network-specific (TAP points, DPI, anomaly detection)
├── sla-slo/                   # SLA/SLO definitions per service
├── incident-response/         # Runbooks & automated recovery actions
└── planning/                  # Registries & contracts (alert strategy, service contract, coverage)
```

### 2. Template + Policy Pattern for Alerts

**Alert definitions (reusable templates):**
```yaml
# L6-observability/alerts/definitions/availability.yaml
alert_templates:
  - id: alert-tpl-availability
    condition: healthcheck.status == down
    severity: critical
    description: "Service {{ service_name }} is down"
```

**Alert policies (service-specific instantiation):**
```yaml
# L6-observability/alerts/policies/svc-web.nextcloud-alerts.yaml
service_alerts:
  svc-web.nextcloud:
    enabled_templates: [alert-tpl-availability, alert-tpl-disk-full]
    thresholds_override:
      disk_full_threshold: 95%  # Service-specific override
```

**Auto-generated index:**
```yaml
# L6-observability/alerts/policies/_service-alert-bindings.yaml (validator-generated)
service_alert_bindings:
  svc-web.nextcloud:
    alert_ids: [alert-web.nextcloud-availability, alert-web.nextcloud-disk-full]
```

**Benefit:** Template reuse; service-specific tuning; no duplication

### 3. Hierarchical Namespacing for Naming Safety

```yaml
# Service ID (L5): svc-<domain>.<name>
svc-web.nextcloud
svc-db.postgres

# Alert ID (L6): alert-<domain>.<service>-<type>
alert-web.nextcloud-availability
alert-db.postgres-replication-lag

# Dashboard ID (L6): dash-<layer>-<domain>.<service>
dash-app-web.nextcloud
dash-infra-network
```

**Validator rule:** Enforce naming regex across L5/L6

**Benefit:** Collision-free at 100x scale

### 4. Service-Observability Contract

```yaml
# L6-observability/planning/service-observability-contract.yaml
contract:
  all_services_must_provide:
    metrics:
      - req_rate        # requests per second
      - error_rate      # errors per second
      - latency_p99     # 99th percentile latency
    health_endpoints:
      - /health         # liveness (am I up?)
      - /readiness      # readiness (am I ready for traffic?)
    logging:
      - format: JSON    # structured logs
      - output: stdout  # logs to stdout (captured by container runtime)
    dashboards:
      - type: service_dashboard  # auto-generated from L6 modules
      - metrics_shown: [req_rate, error_rate, latency, cpu, memory]
```

**Benefit:** Clear expectations for service developers; auto-dashboard generation

### 5. Data-Driven Alert, Dashboard, Runbook Generation

L5 service definition **single source of truth:**
```yaml
# L5-application/services/core-services.yaml
services:
  - id: svc-web.nextcloud
    type: web-app
    tier: critical        # Tier drives SLO, alert templates, dashboard type
    dependencies: [svc-db.postgres]
    alert_templates: [availability, disk-full, cpu-high]  # Apply these templates
    dashboard_type: web-service
    resource_profile_ref: profile-web-medium
```

**Validators auto-generate at L6 validation time:**
- L6-observability/alerts/policies/svc-web.nextcloud-alerts.yaml (from alert_templates)
- L6-observability/dashboards/dash-app-web.nextcloud.yaml (from dashboard_type)
- L6-observability/sla-slo/svc-web.nextcloud-slo.yaml (from tier: critical → 99.99%)

**Benefit:** Single definition point; cascading consistency; 10x-ready

---

## Consequences

### Positive

1. **Scalability:** L6 can grow to 1000+ alerts without explosion (template reuse)
2. **Service-centric:** All observability (alerts, dashboards, SLOs) grouped by service
3. **Data-driven:** Alert/dashboard definitions auto-generated from service type/tier
4. **Integration:** L7 runbooks use L6 data (SLO-aware, incident-responsive)
5. **Validation:** Service↔alert bindings enforced; no orphaned alerts
6. **Clarity:** Hierarchy (by-service/, by-component/) makes navigation easy

### Trade-offs

1. **Complexity:** More modules + contracts to understand (mitigated by documentation)
2. **Migration effort:** Rename ~1000 alerts to hierarchical names (2–3 days automated)
3. **Generator updates:** Need template-to-YAML generator (2 days dev)
4. **Validation overhead:** Binding index generation adds ~1s to validation (acceptable)

### Migration Path (Backward Compatibility)

**Phase 1:** Implement new structure in parallel; old structure still works
**Phase 2:** Auto-migrate alerts (rename flat → hierarchical)
**Phase 3:** Deprecate old alert naming; remove in v4.1.0

---

## Implementation Plan

### Phase 1 (Week 1): Preparation
- [ ] Create L6 directory structure (empty modules)
- [ ] Write service-observability contract
- [ ] Update validators to check hierarchical naming
- [ ] Document migration guide

### Phase 2 (Week 2): Generator & Template System
- [ ] Implement alert template system (template + policy pattern)
- [ ] Build dashboard template generator
- [ ] Build SLO auto-generator (from service tier)
- [ ] Build runbook template system (linked to alerts)

### Phase 3 (Week 3): Migration & Validation
- [ ] Migrate existing alerts to new structure
- [ ] Validate all service↔alert bindings
- [ ] Test auto-generated dashboards + runbooks
- [ ] Update documentation + runbooks

### Phase 4 (Ongoing): Optimization
- [ ] Lazy-load alert rules (only for enabled services)
- [ ] Cache alert bindings (for fast incident response)
- [ ] Enhance incident-response automation

---

## References

- ADR 0026: L3/L4 taxonomy (established modularization patterns)
- ADR 0034: L4 modularization (resource profiles, templates)
- ADR 0045: Project improvements (CI, testing, logging)
- STEP 2 Analysis: L6 modularization design
- STEP 3 Analysis: Cross-layer redundancy (service naming, alert binding)
- STEP 4 Analysis: L7 integration mapping (data-driven runbooks)

---

**Approval:** Pending architecture review
