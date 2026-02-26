# STEP 4: L7 Operations Integration Mapping

**Date:** 26 февраля 2026 г.

---

## Current L7 State

**L7 contains:**
- Workflows (fresh_install, update_topology, service_deploy, failover, etc.)
- Runbooks (manual procedures for human operators)
- Backup policies
- Power outage policies
- Automation rules

**Problem:** L7 is **isolated** from L5/L6 data.

Example:
```yaml
# L7-operations/workflows/service-failover.yaml
workflows:
  service_failover:
    name: Service Failover
    description: Failover service to standby host
    steps:
      - step: 1
        manual: true
        notes: Check service status on primary host (operator must remember which service!)
      - step: 2
        manual: true
        notes: Switch DNS to backup IP (operator hardcodes IP, no ref to L5!)
```

**Impact:**
- Operator has no context (which service? where is backup IP? what's SLO?)
- Runbook steps are hardcoded, not data-driven
- Incident response happens blind (no L6 dashboard link)

---

## Proposed L7↔L6 Contract

### Contract Layer: `L7-operations/contracts/`

```yaml
# L7-operations/contracts/service-failover-contract.yaml
contracts:
  service_failover:
    triggered_by:
      - alert_ids: [alert-svc-*-down, alert-svc-*-unreachable]
    inputs:
      - service_ref       # Which service to failover
      - target_host_ref   # Which backup host
    outputs:
      - new_status: failover_completed
      - metrics_ref: dash-service-failover-metrics  # Link to L6 dashboard

    requires_from_L5:
      - service.id
      - service.dependencies[]
      - service.sla_ref   # Which SLO applies? (99.9% needs 30min decision)
      - service.backup_location  # Where is replica/standby?

    requires_from_L6:
      - sla_slo.target    # SLO: 99.9% → can afford 2.16hr downtime/month
      - sla_slo.alert_at  # Alert at 50% error budget used → escalate failover
      - alert_service_bindings  # Which alerts triggered this?
      - dashboard.failover_status  # Show operator real-time status
      - incident_response.runbooks[failover]

    provides_to_L5:
      - service.active_location  # Update after failover

    provides_to_L6:
      - incident_log.failover_completed  # For dashboard/audit
```

### Runbook Refactoring: Data-Driven

**Before (hardcoded, isolated):**
```yaml
# L7-operations/runbooks/svc-nextcloud-down.yaml
runbooks:
  svc-nextcloud-down:
    name: Nextcloud Service Down
    steps:
      - step: 1
        manual: true
        notes: "SSH to orangepi5 (192.168.1.100), check if Nextcloud container is running"
      - step: 2
        manual: true
        notes: "If down, restart Docker: docker restart nextcloud"
```

**After (data-driven, linked to L5/L6):**
```yaml
# L7-operations/runbooks/svc-service-down.yaml (generic template)
runbook_templates:
  svc-down-recovery:
    name: Service Down Recovery
    triggered_by:
      - alert_type: availability_check_failed

    parameters:
      - service_ref: $service_id
      - severity: $alert_severity

    steps:
      - step: 1
        action: query_l6_dashboard
        dashboard_ref: "dash-{{ service_ref }}"  # Data-driven dashboard lookup
        context: "Verify service down state, check metrics"

      - step: 2
        condition: "sla_slo[{{ service_ref }}].error_budget_remaining < 50%"
        action: escalate_immediately
        message: "Error budget critical; escalate failover decision to manager"

      - step: 3
        action: check_dependencies
        dependencies: "{{ service[service_ref].dependencies }}"  # From L5
        context: "Ensure dependent services won't break on restart"

      - step: 4
        action: execute_script
        script_ref: "auto-restart-{{ service[service_ref].platform_type }}"
        # For LXC: auto-restart-lxc.sh, for VM: auto-restart-vm.sh, etc.
        context: "Attempt automated recovery (LXC restart, health check)"

      - step: 5
        condition: "step_4.status != success"
        action: trigger_incident
        incident_severity: "{{ alert_severity }}"
        dashboard_ref: "dash-{{ service_ref }}"
        message: "Manual intervention required; opening incident dashboard"

      - step: 6
        manual: true
        context: "Decision point: failover to backup or escalate?"
        options:
          - failover_to_backup:  # Link to service.backup_location (L5)
              target_host: "{{ service[service_ref].backup_location }}"
              runbook: failover-contract (STEP 4 contract)
          - escalate_to_oncall:
              incident_url: "{{ dashboard[service_ref].incident_channel }}"

      - step: 7
        action: post_resolution
        slo_check: "Did we stay within {{ sla_slo[service_ref].target }}?"
        update_incident: "Mark resolution in {{ dashboard[service_ref].incident_log }}"
```

**Instantiation for specific services:**
```yaml
# Auto-generated at L7 startup:
# L7-operations/generated/runbooks/svc-nextcloud-down.yaml
runbooks:
  svc-nextcloud-down:
    name: "Nextcloud Service Down Recovery"
    service_ref: svc-nextcloud
    dashboard_ref: dash-svc-nextcloud
    backup_location: proxmox-pve  # From L5
    slo_target: 99.9%  # From L6
    error_budget_alert_threshold: 50%  # From L6
    platform_type: lxc
    dependencies: [svc-postgres]

    # Steps as above, with resolved refs
```

---

## L7 Dependency Map: What L7 Needs from L5/L6

### From L5 (Services):
```yaml
# L7 reads:
service:
  id
  type
  tier  # critical/high/medium/low
  backup_location  # Where is replica? (host_ref or vm_ref)
  dependencies[]  # Dependent services
  host_ref
  port  # For network testing
  health_endpoint  # For readiness checks
```

### From L6 (Observability):
```yaml
# L7 reads:
sla_slo:
  service_ref
  target  # Availability target %
  error_budget_remaining  # How much buffer left?
  alert_at  # Alert when budget X% used

alert:
  id
  service_ref
  severity
  triggered_condition

dashboard:
  service_ref
  url  # Link for operator reference
  incident_log_channel  # Where to post resolution

incident_response:
  runbook_id
  trigger_alert_id
  steps[]  # Auto-recovery actions
```

### From L7 Back to L6 (Feedback Loop):
```yaml
# L7 writes:
incident_log:
  timestamp
  service_ref
  alert_id_triggered
  action_taken
  resolution
  slo_compliance  # Did we meet SLO? Y/N
  error_budget_used  # How much budget burned?
```

---

## Incident Response Workflow: Full Example

**Scenario:** Nextcloud goes down at 14:00 UTC

**L6 perspective:**
1. Healthcheck failure → alert-svc-nextcloud-down (critical)
2. Alert routing → escalation_policy-critical → Slack to #ops
3. Dashboard auto-opens: https://monitoring.lab/dash-svc-nextcloud
4. Shows: Error budget 30% remaining (critical), all dependencies healthy

**L7 perspective:**
1. Operator clicks runbook link from dashboard
2. Runbook loaded: svc-nextcloud-down (auto-generated from template)
3. Step 1: Dashboard context shown (already open)
4. Step 2: SLO check → error_budget < 50% → escalate NOW
5. Step 3: Check dependencies → svc-postgres running, svc-redis running (OK)
6. Step 4: Auto-restart LXC svc-nextcloud (script executed)
7. Step 5: Check if restart successful (health endpoint returns 200 OK) → recovered!
8. Step 6-7: Post-incident → update dashboard, close alert

**Feedback to L6:**
```yaml
incident_log:
  timestamp: 2026-02-26T14:05:30Z
  service_ref: svc-nextcloud
  alert_id: alert-svc-nextcloud-down
  action_taken: auto-restart-lxc
  resolution: "LXC container restarted, health check passed"
  slo_compliance: "Yes (5min downtime, SLO allows 2.16hr)"
  error_budget_used: "0.39% (5min / 1440min per month)"
```

L6 dashboard updates: Error budget now 29.61% remaining

---

## L7 Contract Enforcement: Validator Rules

```yaml
# topology-tools/validators/l7-operations-validator.py
validators:
  - name: service_refs_in_runbooks
    rule: All service_refs in L7 runbooks exist in L5
    affected_files: [L7-operations/runbooks/*, L7-operations/workflows/*]

  - name: sla_refs_in_incidents
    rule: All sla_refs in L7 incidents exist in L6
    affected_files: [L7-operations/incident-response/*]

  - name: alert_refs_in_contracts
    rule: All alert_ids in L7 contracts exist in L6
    affected_files: [L7-operations/contracts/*]

  - name: backup_location_valid
    rule: service.backup_location must refer to valid L1/L4 host
    affected_files: [L5-application/services/*]

  - name: health_endpoint_exists
    rule: service.health_endpoint must be reachable (L5 + L6 healthcheck)
    affected_files: [L5-application/services/*, L6-observability/healthchecks/*]
```

---

## L7 Automation: From Manual Runbooks to Auto-Recovery

**Phase 1 (Current):** Manual runbooks, operator decision at each step

**Phase 2 (Near-term):** Auto-recovery with operator oversight
- Steps 1–5 automated (query, check, restart, verify)
- Operator decides at step 6 (failover Y/N)

**Phase 3 (Future):** Full automation with guardrails
- Failover auto-executes if SLO breach imminent
- Policy-based (tier: critical → auto-failover, tier: low → wait for operator)

---

## Summary: L7↔L6 Integration Benefits

| Benefit | Impact |
|---------|--------|
| **Data-driven runbooks** | Operator doesn't hardcode IPs/hosts; templates auto-instantiate |
| **SLO-aware decisions** | Operator knows urgency (error budget remaining) |
| **Incident audit trail** | Every resolution logged, linked to alerts/dashboards |
| **Auto-recovery** | Reduce MTTR (mean time to recover) from 30min → 5min |
| **Scaling to 10x** | 200 services × generic runbook templates = no manual overhead |

---

**Next:** Proceed to STEP 5 (Growth Readiness: 10x Simulation)
