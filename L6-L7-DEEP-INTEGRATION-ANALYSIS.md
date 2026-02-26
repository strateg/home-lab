# EXTENDED ANALYSIS: L6→L7 Deep Integration Guide

**Date:** 26 февраля 2026 г.
**Focus:** How L7 Operations layer leverages new L6 Observability structure
**Audience:** DevOps, SRE, Incident Response Engineers

---

## Executive Summary

New L6 structure enables **L7 to become fully data-driven and automated**:

| Aspect | Current (L7 Isolated) | New (L6-Driven L7) | Benefit |
|--------|----------------------|-------------------|---------|
| **Incident Response** | Hardcoded runbooks (SSH to host, restart) | Data-driven (query SLO, check dependencies, auto-heal) | MTTR: 30min → 5min |
| **Escalation** | Manual (PagerDuty, Slack hardcoded) | Policy-based (tier + SLO → auto-escalation) | Faster response |
| **Service Discovery** | Human-maintained list | Auto-discovered from L5 | Always in sync |
| **Runbook Context** | "Nextcloud is down" | "Nextcloud down + SLO critical (0.5% error budget left)" | Informed decisions |
| **Automation** | None (manual step-by-step) | Steps 1–4 auto-execute, step 5 human decision | Faster resolution |

---

## Part 1: How L7 Consumes L6

### 1.1 L6→L7 Data Contract

L6 provides to L7:

```yaml
# L6-observability/planning/l7-consumption-contract.yaml
l7_contract:
  alerts:
    - alert.id              # "alert-web.nextcloud-down"
    - alert.service_ref     # "svc-web.nextcloud"
    - alert.severity        # "critical"
    - alert.triggered_condition  # "healthcheck.status == down"

  sla_slos:
    - slo.service_ref       # "svc-web.nextcloud"
    - slo.target            # 99.9 (availability %)
    - slo.error_budget_remaining  # e.g., 0.5% (urgent!)
    - slo.alert_at          # 50% (escalate when budget hits 50%)

  dashboards:
    - dashboard.id          # "dash-app-web.nextcloud"
    - dashboard.url         # "https://monitoring.lab/d/dash-app-web.nextcloud"
    - dashboard.incident_channel  # Slack channel for posting updates

  incident_response:
    - runbook.id            # "rb-svc-web.nextcloud-down"
    - runbook.trigger_alert_id
    - runbook.steps[]
    - runbook.auto_recovery_actions

  service_dependencies:
    - service.id            # "svc-web.nextcloud"
    - service.dependencies[] # ["svc-db.postgres", "svc-cache.redis"]
    - service.health_endpoint  # "/health"
    - service.readiness_endpoint  # "/readiness"
```

### 1.2 L7 Incident Flow (Data-Driven)

**Scenario: Nextcloud goes down at 14:00 UTC**

**Timeline:**

```
14:00:00 - Alert triggered in L6
  ├─ alert-web.nextcloud-down (critical)
  ├─ Service: svc-web.nextcloud
  ├─ SLO: 99.9% (error budget: 0.5% remaining = CRITICAL)
  └─ Dashboard: dash-app-web.nextcloud
     ├─ Shows: Nextcloud down, all dependencies healthy
     ├─ Shows: Error budget at 0.5% remaining (red flag!)
     └─ Shows: Dependencies (Postgres + Redis) running OK

14:00:30 - L6 Escalation Policy Triggered
  ├─ Severity: critical
  ├─ Policy: escalation-slo-critical
  ├─ Step 1 (immediate): Slack #ops + PagerDuty alert
  ├─ Step 2 (15min): Page on-call engineer if not ack'd
  └─ Step 3 (30min): Escalate to manager

14:00:45 - L7 Runbook Starts (Auto-Fetched)
  ├─ Operator clicks "View Runbook" from dashboard
  ├─ L7 queries L6: get runbook for alert-web.nextcloud-down
  ├─ Returns: rb-svc-web.nextcloud-down
  └─ Loads runbook with data-driven context:

     Step 1: Query Dashboard Context
     ├─ Dashboard: dash-app-web.nextcloud
     ├─ Status: Service DOWN, Dependencies HEALTHY
     └─ Error budget: 0.5% (critical, escalate NOW)

     Step 2: SLO Check
     ├─ SLO: 99.9% availability
     ├─ Error budget remaining: 0.5%
     ├─ Decision: ESCALATE IMMEDIATELY (too risky to wait)
     └─ Next: Manual failover or exec auto-recovery

     Step 3: Check Dependencies (Auto-Execute)
     ├─ Query L5 service.dependencies → [svc-db.postgres, svc-cache.redis]
     ├─ Query L6 SLOs for each
     ├─ Check health endpoints: /health on each
     ├─ Result: All dependencies healthy ✓
     └─ Clear to restart Nextcloud

     Step 4: Attempt Auto-Recovery (Auto-Execute)
     ├─ Service type: LXC (from L5)
     ├─ Command: lxc restart lxc-nextcloud
     ├─ Check health: curl https://nextcloud.home.local/health
     ├─ Wait 30s, retry if failed
     ├─ Result: SUCCESS ✓ (service recovered)
     └─ Time: 2 minutes from alert → recovered

     Step 5: Incident Resolution (Human)
     ├─ SLO check: Did we stay within 99.9%?
     ├─ Error budget burned: 2min / 2592000min = 0.0008% (acceptable)
     ├─ Update dashboard: Resolution logged
     ├─ Close incident: svc-web.nextcloud resolved
     └─ Post-mortem: Why did it crash? (check logs, add monitoring)

14:02:50 - Incident Closed
  ├─ Total time: 2min 50sec (well within SLO)
  ├─ Error budget consumed: 0.0008% (leaves 0.49% for rest of month)
  └─ Status: RESOLVED ✅
```

---

## Part 2: L7 Use Cases Enabled by L6

### Use Case 1: SLO-Aware Incident Triage

**Before (Current L7 - Manual):**
```
Operator sees Nextcloud down alert
├─ Checks dashboard manually (already on dashboard, good)
├─ Thinks: "Is this urgent? No idea... let me ask colleague"
├─ Meanwhile: 10 minutes pass
└─ Finally decides: "Restart it"
```

**After (New L6-Driven L7):**
```
Operator sees alert with SLO context
├─ Alert shows: "SLO: 99.9%, Error budget: 0.5% LEFT (CRITICAL)"
├─ Thinks: "0.5% error budget left? Every second matters!"
├─ Decision: "Immediate auto-restart + escalate"
├─ Runbook auto-executes steps 1–4
└─ Resolved in 3 minutes
```

**L6 data used:** `slo.error_budget_remaining`, `slo.target`, `slo.alert_at`

---

### Use Case 2: Dependency-Aware Recovery

**Before (Current L7 - Manual):**
```
Runbook says: "Restart Nextcloud"
Operator: "But wait... does it depend on Postgres? Let me check..."
Meanwhile: Nextcloud crashes again (Postgres still down)
```

**After (New L6-Driven L7):**
```
Runbook executes (auto):
  1. Query L5: svc-web.nextcloud.dependencies → [svc-db.postgres, svc-cache.redis]
  2. Check L6 health for each: /health endpoints
  3. If any unhealthy: abort restart (fix dependency first)
  4. If all healthy: proceed with restart
Result: No cascading failures
```

**L6 data used:** `service.dependencies[]`, `service.health_endpoint`, `service.readiness_endpoint`

---

### Use Case 3: Auto-Escalation Based on SLO Breach

**Before (Current L7 - Manual):**
```
Service down for 10 minutes
Operator manually decides: "Should I page someone?"
By the time paging happens: 15 minutes elapsed
```

**After (New L6-Driven L7):**
```
L6 escalation policy (auto-triggered):
├─ Step 0 (immediate): Post alert to Slack
├─ Step 1 (5min): If not ack'd → check SLO
├─ Step 2 (at 5min): SLO shows "error budget < 50%" → auto-page on-call
├─ Step 3 (at 15min): Escalate to manager if still down
Result: Escalation happens automatically, no operator delay
```

**L6 data used:** `escalation_policy`, `slo.error_budget_remaining`, `slo.alert_at`

---

### Use Case 4: Automated Runbook Instantiation

**Before (Current L7 - Manual):**
```
Operator maintains 50 runbooks manually
├─ "svc-nextcloud-down.txt"
├─ "svc-postgres-down.txt"
├─ "svc-redis-down.txt"
└─ ... (manually updated when service changes)
```

**After (New L6-Driven L7):**
```
Runbook template: "svc-service-down.yaml" (ONE template)
  ├─ Instantiated for each L5 service automatically
  ├─ Parameters: service_ref, service_type, dependencies, SLO
  ├─ Generated at L6 validation time (every regen)
  └─ Always in sync with L5 (add new service → new runbook auto-generated)
Result: 0 manual runbook maintenance
```

**L6 data used:** `service.type`, `service.dependencies[]`, `slo.*`, `runbook_template`

---

### Use Case 5: Incident Post-Mortem Automation

**Before (Current L7 - Manual):**
```
Operator manually fills: "What happened? What changed?"
Often: incomplete, inaccurate, or never filled
```

**After (New L6-Driven L7):**
```
Incident resolution (auto-logged from L6):
├─ Timestamp: incident created, recovered
├─ Alert ID triggered: alert-web.nextcloud-down
├─ Runbook executed: rb-svc-web.nextcloud-down
├─ Recovery action: lxc restart (auto-recovery step 4)
├─ SLO compliance: "Did we meet 99.9%?" YES
├─ Error budget consumed: 0.0008%
├─ Root cause indicators: (query logs from L6/incident-response/)
└─ Dashboard link: dash-app-web.nextcloud
Result: Incident fully documented automatically
```

**L6 data used:** `incident_log.*`, `alert.id`, `runbook.id`, `slo.target`, all timestamps from L6

---

## Part 3: L7 Operational Patterns (New Possibilities)

### Pattern 1: Policy-Based Incident Response

```yaml
# L7-operations/incident-response-policies.yaml
incident_policies:

  # Tier-based auto-remediation
  critical_tier_policy:
    applies_to: services.tier == "critical"
    on_alert_severity: critical
    actions:
      - step: check_dependencies
      - step: health_check_all_deps  # Auto-execute
      - step: attempt_auto_recovery  # Auto-execute (lxc restart)
      - step: human_decision_on_failover  # Manual (requires skill/judgment)

  # Time-based escalation
  escalation_by_time:
    at_5min: "Page on-call"
    at_15min: "Escalate to manager"
    at_30min: "Page VP engineering"

  # Error-budget-based urgency
  escalation_by_slo:
    if_budget < 50%: "CRITICAL - escalate immediately"
    if_budget < 20%: "EMERGENCY - page VP engineering"
    if_budget < 5%: "CALL 911 (failover now!)"
```

**L6 integration:** L7 queries `slo.error_budget_remaining` to determine urgency

---

### Pattern 2: Service-Aware Logging & Tracing

```yaml
# L7-operations/incident-context.yaml
when_incident_detected:
  auto_actions:
    - fetch_dashboard: "dash-{{ alert.service_ref }}"
    - fetch_logs: "logs from L6 for service {{ alert.service_ref }} (last 5min)"
    - fetch_metrics: "metrics from L6 for service {{ alert.service_ref }}"
    - check_dependency_health: "for each service in {{ service.dependencies }}"
    - check_recent_changes: "terraform apply logs, ansible playbook logs"

  provide_to_operator:
    - "What service? {{ alert.service_ref }}"
    - "Why urgent? Error budget {{ slo.error_budget_remaining }}% left"
    - "Can we fix it? Dependencies healthy: {{ dep_health_status }}"
    - "What to do? Run: {{ runbook.id }}"
    - "What happened before? Recent changes: {{ change_log }}"
```

**L6 integration:** L7 queries L6 dashboards, logs, metrics, incident history

---

### Pattern 3: Cross-Service Incident Correlation

```yaml
# L7-operations/multi-service-incidents.yaml
if_multiple_alerts_in_5min:

  # Scenario: Postgres + Nextcloud both down
  postgres_down: alert-db.postgres-availability
  nextcloud_down: alert-web.nextcloud-availability

  correlation_check:
    - "Is Nextcloud dependent on Postgres?"
      → "{{ svc-web.nextcloud.dependencies contains svc-db.postgres }}"
    - "If yes → root cause is Postgres, not Nextcloud!"
    - "Prioritize fixing Postgres first"

  auto_response:
    - Set priority: "Fix Postgres (svc-db.postgres)"
    - Suppress secondary alert: "alert-web.nextcloud-availability"
      reason: "Suppressed due to dependency (Postgres down)"
    - Provide context: "Fixing Postgres should auto-recover Nextcloud"
```

**L6 integration:** L7 queries `service.dependencies[]` + `alert.service_ref` to correlate

---

## Part 4: L7 New Requirements (For Full Integration)

### 4.1 L7 Schema Changes Needed

```yaml
# topology/L7-operations/schema-enhancements.yaml
new_required_fields:

  incident_templates:
    - triggered_by: alert_id         # Link to L6 alert
    - service_ref: service_id         # Link to L5 service
    - slo_aware: true                # Query L6 SLO
    - auto_recovery_actions: []      # From L6 incident-response/
    - escalation_policy_ref: policy_id  # From L6 escalation-policies/

  runbook_templates:
    - parameter: service_ref          # Data-driven instantiation
    - parameter: service_type         # From L5 (LXC vs VM vs device)
    - parameter: dependencies[]       # From L5 service.dependencies
    - parameter: slo_target           # From L6 SLO
    - parameter: error_budget_alert   # From L6 SLO
    - action: query_dashboard         # L6 dashboard.url
    - action: check_health_endpoints  # L5 service.health_endpoint
    - action: execute_recovery_script # From L6 incident-response/automated-responses/
    - action: log_to_incident_channel # L6 dashboard.incident_channel

  post_incident_analysis:
    - recovery_time_seconds: computed
    - slo_compliance: boolean
    - error_budget_consumed: percentage
    - root_cause_indicators: from L6 logs + L5 changes
    - preventive_actions: suggested (add monitoring? increase timeout?)
```

### 4.2 L7 New Modules

```
L7-operations/
├── incident-response-policies/
│   ├── critical-services.yaml    # Auto-recovery for critical tier
│   ├── escalation-by-time.yaml   # 5min, 15min, 30min escalations
│   └── escalation-by-slo.yaml    # Escalate if error budget low
│
├── service-aware-runbooks/
│   ├── _templates/
│   │   ├── svc-down-recovery.yaml          # Template
│   │   ├── disk-full-recovery.yaml
│   │   └── dependency-failure-recovery.yaml
│   │
│   └── _generated/  (auto-generated at L6 validation)
│       ├── svc-web.nextcloud-down.yaml
│       ├── svc-db.postgres-down.yaml
│       └── ...
│
├── integration/
│   ├── l6-alert-handler.py       # Consume L6 alerts, route to runbooks
│   ├── l6-slo-monitor.py         # Monitor error budget, auto-escalate
│   ├── l6-incident-logger.py     # Log incidents back to L6
│   └── l6-correlation-engine.py  # Correlate multi-service incidents
│
└── automation/
    ├── auto-recovery-executor.py      # Execute auto-recovery steps
    ├── escalation-policy-engine.py    # Policy-based escalation
    └── dependency-health-checker.py   # Check service dependencies
```

---

## Part 5: Implementation Phases for L7 Integration

### Phase 1 (Week 1–2): Read-Only Integration

**What L7 reads from L6:**

```python
# L7 loads L6 data at startup (read-only)
from l6_observability import (
    load_alerts,        # Load alert definitions + policies
    load_slos,          # Load SLO targets + error budgets
    load_dashboards,    # Load dashboard IDs + URLs
    load_incident_responses,  # Load runbook templates
)

# L7 builds indices
alert_index = {alert.id: alert for alert in load_alerts()}
slo_index = {slo.service_ref: slo for slo in load_slos()}
dashboard_index = {dash.service_ref: dash for dash in load_dashboards()}
runbook_templates = load_incident_responses()
```

**Use cases enabled:**
- Runbook instantiation from templates
- SLO-aware decision making
- Service dependency awareness

**Effort:** 1–2 weeks (build L7 data loader + indices)

---

### Phase 2 (Week 3–4): Incident Response Integration

**What L7 sends back to L6:**

```yaml
# After incident resolves, L7 logs back to L6
post_incident:
  timestamp: 2026-02-26T14:02:50Z
  alert_id: alert-web.nextcloud-down
  service_ref: svc-web.nextcloud
  recovery_action: lxc-restart
  recovery_duration_seconds: 170
  slo_compliance: true
  error_budget_consumed: 0.0008%
  runbook_executed: rb-svc-web.nextcloud-down
  escalation_steps_triggered: [0, 1]  # Slack, page on-call
  notes: "LXC container restarted successfully"
```

**L6 consumption:**
- Incident log used by dashboards (show resolution context)
- Error budget tracking (deduct consumed budget)
- Runbook audit trail (improve runbooks over time)

**Effort:** 1 week (build incident logger + L6 integration)

---

### Phase 3 (Week 5): Policy-Based Automation

**What L7 executes automatically (based on L6 policies):**

```python
# L7 incident handler (auto-triggered by L6 alerts)
def handle_alert(alert_id):
    alert = alert_index[alert_id]
    service = services[alert.service_ref]
    slo = slo_index[alert.service_ref]

    # Auto-execute steps based on policy
    policy = get_policy_for_service(service.tier)

    for step in policy.auto_recovery_steps:
        # Step 1: Check dependencies (auto)
        deps_healthy = check_service_health(service.dependencies)

        # Step 2: Attempt recovery (auto)
        if deps_healthy:
            recover_service(service, runbook_templates[service.type])

        # Step 3: Escalate if urgent (auto)
        if slo.error_budget_remaining < policy.escalation_threshold:
            escalate(alert, slo)

    # Step 4: Await human decision (manual)
    if not recovered:
        notify_oncall(f"Manual failover needed for {service.id}")
```

**Effort:** 1–2 weeks (build policy engine + auto-executor)

---

### Phase 4 (Week 6): Observability Loop Closure

**Full bidirectional L6↔L7:**

```
L6 (Observability) ↔ L7 (Operations)
├─ L6 → L7: alerts, SLOs, dashboards, incident-response playbooks
├─ L7 → L6: incident logs, error budget consumed, resolution context
├─ L6 learns from L7: runbook effectiveness, escalation timing accuracy
└─ L7 learns from L6: service health patterns, predictive alerts
```

**Effort:** 1–2 weeks (build feedback loops + learning)

---

## Part 6: Concrete Examples (L7 Code After Integration)

### Example 1: Incident Handler (Auto-Triggered)

```python
# L7-operations/handlers/incident_handler.py
from l6_observability import get_alert, get_slo, get_dashboard, get_runbook_template
from l5_application import get_service

def handle_incident(alert_id: str):
    """Auto-triggered when L6 alert fires"""

    # Load context from L6
    alert = get_alert(alert_id)
    service = get_service(alert.service_ref)
    slo = get_slo(alert.service_ref)
    dashboard = get_dashboard(alert.service_ref)
    runbook_template = get_runbook_template(service.type, "service-down")

    # Build context
    context = {
        'alert_id': alert.id,
        'service_ref': service.id,
        'service_type': service.type,
        'service_tier': service.tier,
        'slo_target': slo.target,
        'error_budget_remaining': slo.error_budget_remaining,
        'dependencies': service.dependencies,
        'dashboard_url': dashboard.url,
        'incident_channel': dashboard.incident_channel,
    }

    # Instantiate runbook from template
    runbook = runbook_template.instantiate(**context)

    # Execute auto-recovery steps
    for step in runbook.auto_recovery_steps:
        if step.name == "check_dependencies":
            health_status = check_dependencies_health(service.dependencies)
            if not health_status['all_healthy']:
                log_incident("Cannot recover: dependency down")
                escalate_to_human(context)
                return

        elif step.name == "auto_restart":
            success = execute_service_restart(service)
            if success:
                log_incident(f"Service recovered via {step.name}")
                notify_slack(context['incident_channel'],
                            f"✅ {service.id} recovered (downtime: 2min)")
                return

    # If we get here, auto-recovery failed
    escalate_to_human(context)

def escalate_to_human(context):
    """Escalate to on-call engineer"""
    escalation_policy = get_escalation_policy(context['service_tier'])

    if context['error_budget_remaining'] < 50:
        # Critical: escalate immediately
        page_oncall(context, urgency='critical')
    else:
        # Notify Slack first, escalate if not ack'd in 5min
        notify_slack(context, urgency='high')
        schedule_escalation(at=5_minutes, context=context)
```

### Example 2: SLO-Aware Decision Making

```python
# L7-operations/handlers/slo_decision_maker.py
def decide_recovery_strategy(service_ref: str) -> str:
    """Decide recovery strategy based on SLO urgency"""

    slo = get_slo(service_ref)
    service = get_service(service_ref)

    error_budget_pct = slo.error_budget_remaining

    if error_budget_pct > 50:
        # Plenty of budget: try graceful recovery first
        return "graceful_restart"

    elif error_budget_pct > 20:
        # Low budget: restart quickly, then check health
        return "quick_restart_with_validation"

    elif error_budget_pct > 5:
        # Critical budget: failover to backup immediately
        return "immediate_failover"

    else:
        # Emergency: already violating SLO
        return "emergency_failover_and_escalate_vp"
```

### Example 3: Runbook Auto-Generation

```python
# L7-operations/generators/runbook_generator.py
def generate_runbook_from_service(service_id: str) -> dict:
    """Generate runbook from L5 service + L6 templates"""

    service = get_service(service_id)
    slo = get_slo(service_id)
    runbook_template = get_runbook_template("service-down")

    # Instantiate template with service-specific data
    runbook = {
        'id': f"rb-{service.id}-down",
        'service_ref': service.id,
        'triggered_by': f"alert-{service.id}-down",
        'steps': [
            {
                'step': 1,
                'action': 'query_dashboard',
                'dashboard_ref': f"dash-app-{service.id}",
                'context': f"Verify {service.id} down state"
            },
            {
                'step': 2,
                'action': 'check_slo',
                'slo_target': slo.target,
                'error_budget_threshold': 50,
                'decision_if_critical': "escalate_immediately"
            },
            {
                'step': 3,
                'action': 'check_dependencies',
                'dependencies': service.dependencies,
                'health_check_endpoint': service.health_endpoint,
                'decision_if_unhealthy': "abort_and_escalate"
            },
            {
                'step': 4,
                'action': 'execute_recovery',
                'recovery_script': f"recover-{service.type}.sh",
                'service_id': service.id,
                'max_retries': 3,
                'decision_if_failed': "escalate_to_human"
            },
            {
                'step': 5,
                'action': 'human_decision',
                'context': "Manual failover or further escalation?",
                'options': ['failover_to_backup', 'escalate_to_oncall', 'escalate_to_manager']
            },
            {
                'step': 6,
                'action': 'post_resolution',
                'slo_check': f"Did we meet {slo.target}%?",
                'log_to_incident_channel': True,
                'update_runbook_effectiveness': True
            }
        ]
    }

    return runbook
```

---

## Part 7: Benefits Summary (L6→L7 Integration)

| Benefit | Impact | Example |
|---------|--------|---------|
| **Data-Driven Runbooks** | No more hardcoded SSH commands | "restart {{ service_name }}" instead of "ssh orangepi5 restart nextcloud" |
| **SLO-Aware Decisions** | Operator knows urgency immediately | "Error budget 0.5% left → escalate NOW" |
| **Dependency Intelligence** | No cascading failures | "Can't restart Nextcloud because Postgres is down" |
| **Auto-Recovery** | MTTR: 30min → 5min | Steps 1–4 auto-execute, step 5 human decision |
| **Policy-Based Automation** | Consistent responses | Critical services: auto-failover; High: quick restart; Medium: manual |
| **Incident Audit Trail** | Full context stored | "Alert → Runbook → Recovery → SLO check → Logged" |
| **Predictive Escalation** | Don't wait for manual escalation | "Error budget at 20%? → Auto-page VP eng in 5min" |
| **Runbook Self-Generation** | Zero maintenance | Add new service → runbook auto-generated |

---

## Part 8: Integration Checklist

### Prerequisites (From L6 Modularization - ADR 0047)
- [ ] L6 alerts modularized (template + policy pattern)
- [ ] L6 SLOs defined (per service, by tier)
- [ ] L6 dashboards auto-generated
- [ ] L6 incident-response module created
- [ ] L6 escalation-policies defined
- [ ] L5 service schema extended (type, tier, dependencies, health_endpoint)

### L7 Integration Tasks
- [ ] Build L6 data loader (read alerts, SLOs, dashboards)
- [ ] Build incident handler (auto-triggered by alerts)
- [ ] Build SLO decision engine (urgency-based strategy selection)
- [ ] Build runbook template system (service-aware, data-driven)
- [ ] Build auto-recovery executor (execute runbook steps 1–4)
- [ ] Build incident logger (log resolution back to L6)
- [ ] Build escalation policy engine (time-based + SLO-based)
- [ ] Build dependency health checker
- [ ] Build incident correlation (multi-service incidents)
- [ ] Tests: integration tests for all handlers

---

## Part 9: Migration Path (Old L7 → New L7)

### Phase 1: Read-Only (Week 1–2)
L7 reads L6 data, but still uses old hardcoded runbooks
- Runbooks side-by-side (old + new)
- L6 alerts route to both old and new handlers
- Operator can choose which runbook to use

### Phase 2: Parallel (Week 3–4)
L7 uses new data-driven runbooks
- Old runbooks deprecated (but still available)
- New runbooks from templates + L6 data
- Incident logs written back to L6

### Phase 3: Migration (Week 5–6)
Old hardcoded runbooks removed
- Full reliance on L6-driven L7
- All incidents handled by policy engine
- Zero manual runbook maintenance

### Phase 4: Optimization (Week 7+)
Machine learning on incident patterns
- Learn which recovery strategies work best
- Predict incidents before they happen
- Auto-tune escalation policies

---

**Next:** Prepare for L7 Implementation Phase 1 (Data Loader + Incident Handler)

Ready to code L7 integration? Let's start with the data loader module.
