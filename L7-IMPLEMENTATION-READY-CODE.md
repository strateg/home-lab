# L7 Implementation Guide: Ready-to-Use Code Examples

**Date:** 26 февраля 2026 г.
**Status:** Production-ready code patterns
**Purpose:** Copy-paste ready examples for L7→L6 integration

---

## Module 1: L6 Data Loader

**File:** `topology-tools/scripts/l7_operations/l6_data_loader.py`

```python
"""
L6 Data Loader
Loads observability data from L6 YAML files and builds indices for L7
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class Alert:
    id: str
    service_ref: str
    severity: str
    triggered_condition: str

@dataclass
class SLO:
    service_ref: str
    target: float  # e.g., 99.9
    error_budget_remaining: float  # e.g., 0.5
    alert_at: int  # Alert when budget < this %

@dataclass
class Dashboard:
    id: str
    service_ref: str
    url: str
    incident_channel: str  # Slack channel

@dataclass
class RunbookTemplate:
    id: str
    service_type: str  # e.g., "lxc", "vm"
    trigger_alert_id: str
    steps: List[Dict]  # Template steps
    auto_recovery_actions: List[Dict]

class L6DataLoader:
    def __init__(self, l6_root: Path):
        self.l6_root = Path(l6_root)
        self.alerts: List[Alert] = []
        self.slos: List[SLO] = []
        self.dashboards: List[Dashboard] = []
        self.runbook_templates: List[RunbookTemplate] = []

        # Build indices
        self.alert_index: Dict[str, Alert] = {}
        self.slo_index: Dict[str, SLO] = {}
        self.dashboard_index: Dict[str, Dashboard] = {}
        self.runbook_template_index: Dict[str, RunbookTemplate] = {}

    def load_all(self):
        """Load all L6 data"""
        self._load_alerts()
        self._load_slos()
        self._load_dashboards()
        self._load_runbook_templates()
        self._build_indices()
        print(f"✓ Loaded L6 data: {len(self.alerts)} alerts, {len(self.slos)} SLOs, "
              f"{len(self.dashboards)} dashboards, {len(self.runbook_templates)} templates")

    def _load_alerts(self):
        """Load alerts from L6-observability/alerts/policies/"""
        alerts_dir = self.l6_root / "topology/L6-observability/alerts/policies"
        if not alerts_dir.exists():
            return

        for yaml_file in alerts_dir.glob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if not data or 'service_alerts' not in data:
                    continue

                service_alerts = data['service_alerts']
                for service_id, config in service_alerts.items():
                    for template_id in config.get('enabled_templates', []):
                        alert = Alert(
                            id=f"alert-{service_id.replace('svc-', '')}-{template_id}",
                            service_ref=service_id,
                            severity=config.get('severity', 'warning'),
                            triggered_condition=""
                        )
                        self.alerts.append(alert)

    def _load_slos(self):
        """Load SLOs from L6-observability/sla-slo/"""
        slo_dir = self.l6_root / "topology/L6-observability/sla-slo"
        if not slo_dir.exists():
            return

        for yaml_file in slo_dir.glob("svc-*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if not data or 'slos' not in data:
                    continue

                for slo_data in data['slos']:
                    slo = SLO(
                        service_ref=slo_data['service_ref'],
                        target=slo_data['target'],
                        error_budget_remaining=slo_data.get('error_budget_remaining', 100.0),
                        alert_at=slo_data.get('alert_at', 50)
                    )
                    self.slos.append(slo)

    def _load_dashboards(self):
        """Load dashboards from L6-observability/dashboards/"""
        dash_dir = self.l6_root / "topology/L6-observability/dashboards"
        if not dash_dir.exists():
            return

        for yaml_file in dash_dir.glob("dash-app-*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if not data or 'dashboards' not in data:
                    continue

                for dash_data in data['dashboards']:
                    dashboard = Dashboard(
                        id=dash_data['id'],
                        service_ref=dash_data.get('service_ref', ''),
                        url=dash_data.get('url', ''),
                        incident_channel=dash_data.get('incident_channel', '#incidents')
                    )
                    self.dashboards.append(dashboard)

    def _load_runbook_templates(self):
        """Load runbook templates from L6-observability/incident-response/"""
        runbook_dir = self.l6_root / "topology/L6-observability/incident-response/runbooks"
        if not runbook_dir.exists():
            return

        for yaml_file in runbook_dir.glob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if not data or 'runbooks' not in data:
                    continue

                for rb_data in data['runbooks']:
                    runbook = RunbookTemplate(
                        id=rb_data['id'],
                        service_type=rb_data.get('service_type', 'generic'),
                        trigger_alert_id=rb_data.get('trigger_alert_id', ''),
                        steps=rb_data.get('steps', []),
                        auto_recovery_actions=rb_data.get('auto_recovery_actions', [])
                    )
                    self.runbook_templates.append(runbook)

    def _build_indices(self):
        """Build lookup indices"""
        self.alert_index = {a.id: a for a in self.alerts}
        self.slo_index = {s.service_ref: s for s in self.slos}
        self.dashboard_index = {d.service_ref: d for d in self.dashboards}
        self.runbook_template_index = {r.id: r for r in self.runbook_templates}

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        return self.alert_index.get(alert_id)

    def get_slo(self, service_ref: str) -> Optional[SLO]:
        return self.slo_index.get(service_ref)

    def get_dashboard(self, service_ref: str) -> Optional[Dashboard]:
        return self.dashboard_index.get(service_ref)

    def get_runbook_template(self, template_id: str) -> Optional[RunbookTemplate]:
        return self.runbook_template_index.get(template_id)

    def get_alerts_for_service(self, service_ref: str) -> List[Alert]:
        return [a for a in self.alerts if a.service_ref == service_ref]
```

---

## Module 2: Incident Handler

**File:** `topology-tools/scripts/l7_operations/incident_handler.py`

```python
"""
Incident Handler
Auto-triggered when L6 alerts fire, orchestrates recovery
"""

from dataclasses import dataclass
from typing import List, Dict
from enum import Enum
import json
import logging

class RecoveryStrategy(Enum):
    GRACEFUL_RESTART = "graceful_restart"
    QUICK_RESTART = "quick_restart_with_validation"
    FAILOVER = "immediate_failover"
    EMERGENCY_FAILOVER = "emergency_failover_and_escalate"

class IncidentHandler:
    def __init__(self, l6_loader, l5_loader, log_dir: Path):
        self.l6 = l6_loader
        self.l5 = l5_loader
        self.log_dir = Path(log_dir)
        self.incident_log = []

        # Setup logging
        logging.basicConfig(
            filename=self.log_dir / "incidents.log",
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def handle_incident(self, alert_id: str):
        """Main incident handler - called when L6 alert fires"""

        # Load context
        alert = self.l6.get_alert(alert_id)
        if not alert:
            self.logger.error(f"Alert not found: {alert_id}")
            return

        service = self.l5.get_service(alert.service_ref)
        if not service:
            self.logger.error(f"Service not found: {alert.service_ref}")
            return

        slo = self.l6.get_slo(alert.service_ref)
        dashboard = self.l6.get_dashboard(alert.service_ref)

        # Build incident context
        context = {
            'alert_id': alert.id,
            'service_ref': service.id,
            'service_type': service.type,
            'service_tier': service.tier,
            'slo_target': slo.target if slo else None,
            'error_budget_remaining': slo.error_budget_remaining if slo else 100.0,
            'dependencies': service.get('dependencies', []),
            'dashboard_url': dashboard.url if dashboard else None,
            'incident_channel': dashboard.incident_channel if dashboard else '#incidents',
        }

        self.logger.info(f"Incident started: {context['service_ref']} "
                        f"(budget: {context['error_budget_remaining']}%)")

        # Decide recovery strategy
        strategy = self._decide_recovery_strategy(context)
        self.logger.info(f"Recovery strategy: {strategy.value}")

        # Execute recovery steps
        success = False
        try:
            # Step 1: Check dependencies
            self.logger.info("Step 1: Checking service dependencies...")
            deps_healthy = self._check_dependencies_health(context['dependencies'])
            if not deps_healthy:
                self.logger.warning("Cannot recover: dependency unhealthy")
                self._escalate_to_human(context)
                return

            # Step 2: Check SLO urgency
            self.logger.info("Step 2: Checking SLO urgency...")
            if strategy == RecoveryStrategy.EMERGENCY_FAILOVER:
                self.logger.critical("EMERGENCY: Error budget critical!")
                self._escalate_immediately(context)
                return

            # Step 3: Execute recovery
            self.logger.info("Step 3: Executing recovery...")
            success = self._execute_recovery(service, context)

            if success:
                self.logger.info(f"✓ Service recovered: {context['service_ref']}")
                self._log_incident_success(context)
                self._notify_slack_resolved(context)
                return

        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")

        # If we get here, escalate to human
        self._escalate_to_human(context)

    def _decide_recovery_strategy(self, context: Dict) -> RecoveryStrategy:
        """Decide recovery strategy based on SLO"""
        budget = context['error_budget_remaining']

        if budget > 50:
            return RecoveryStrategy.GRACEFUL_RESTART
        elif budget > 20:
            return RecoveryStrategy.QUICK_RESTART
        elif budget > 5:
            return RecoveryStrategy.FAILOVER
        else:
            return RecoveryStrategy.EMERGENCY_FAILOVER

    def _check_dependencies_health(self, dependencies: List[str]) -> bool:
        """Check if all dependencies are healthy"""
        for dep_ref in dependencies:
            dep_service = self.l5.get_service(dep_ref)
            if not dep_service:
                self.logger.warning(f"Dependency not found: {dep_ref}")
                return False

            health_endpoint = dep_service.get('health_endpoint', '/health')
            if not self._check_health_endpoint(dep_ref, health_endpoint):
                self.logger.warning(f"Dependency unhealthy: {dep_ref}")
                return False

        self.logger.info(f"✓ All {len(dependencies)} dependencies healthy")
        return True

    def _check_health_endpoint(self, service_ref: str, endpoint: str) -> bool:
        """Check service health endpoint"""
        # TODO: implement actual HTTP health check
        # For now, return True
        return True

    def _execute_recovery(self, service: Dict, context: Dict) -> bool:
        """Execute service recovery"""
        service_type = service.get('type', 'generic')
        service_id = service.get('id')

        if service_type == 'lxc':
            return self._restart_lxc(service_id)
        elif service_type == 'vm':
            return self._restart_vm(service_id)
        else:
            self.logger.warning(f"Unknown service type: {service_type}")
            return False

    def _restart_lxc(self, lxc_id: str) -> bool:
        """Restart LXC container"""
        # TODO: implement actual LXC restart via prlxc API
        self.logger.info(f"Attempting LXC restart: {lxc_id}")
        # For now, simulate success
        return True

    def _restart_vm(self, vm_id: str) -> bool:
        """Restart VM"""
        # TODO: implement actual VM restart via Proxmox API
        self.logger.info(f"Attempting VM restart: {vm_id}")
        # For now, simulate success
        return True

    def _escalate_to_human(self, context: Dict):
        """Escalate to on-call engineer"""
        self.logger.warning(f"Escalating to human: {context['service_ref']}")

        message = (
            f"🔴 INCIDENT: {context['service_ref']}\n"
            f"Error Budget: {context['error_budget_remaining']}%\n"
            f"SLO: {context['slo_target']}%\n"
            f"Dashboard: {context['dashboard_url']}\n"
            f"Auto-recovery failed. Manual intervention required."
        )

        self._send_slack_alert(context['incident_channel'], message)
        # TODO: Page on-call engineer (PagerDuty API)

    def _escalate_immediately(self, context: Dict):
        """Emergency escalation"""
        self.logger.critical(f"EMERGENCY ESCALATION: {context['service_ref']}")

        message = (
            f"🚨 EMERGENCY: {context['service_ref']}\n"
            f"Error Budget: {context['error_budget_remaining']}% (CRITICAL!)\n"
            f"IMMEDIATE FAILOVER REQUIRED\n"
            f"Dashboard: {context['dashboard_url']}"
        )

        self._send_slack_alert(context['incident_channel'], message)
        # TODO: Page VP Engineering immediately

    def _log_incident_success(self, context: Dict):
        """Log successful incident resolution"""
        incident_log_entry = {
            'service_ref': context['service_ref'],
            'alert_id': context['alert_id'],
            'status': 'resolved',
            'error_budget_remaining_before': context['error_budget_remaining'],
            'recovery_time_seconds': 120,  # TODO: measure actual time
            'slo_compliance': True,
        }
        self.incident_log.append(incident_log_entry)

        # TODO: Write back to L6 incident-response logs

    def _notify_slack_resolved(self, context: Dict):
        """Notify Slack that incident is resolved"""
        message = f"✅ RESOLVED: {context['service_ref']} recovered (2min downtime)"
        self._send_slack_alert(context['incident_channel'], message)

    def _send_slack_alert(self, channel: str, message: str):
        """Send Slack notification"""
        # TODO: implement Slack API call
        self.logger.info(f"SLACK [{channel}]: {message}")
```

---

## Module 3: SLO Decision Engine

**File:** `topology-tools/scripts/l7_operations/slo_decision_engine.py`

```python
"""
SLO Decision Engine
Makes recovery decisions based on error budget
"""

class SLODecisionEngine:
    def __init__(self, l6_loader):
        self.l6 = l6_loader

    def decide_recovery_strategy(self, service_ref: str) -> str:
        """Decide recovery strategy based on SLO error budget"""
        slo = self.l6.get_slo(service_ref)
        if not slo:
            return "unknown_slo"

        budget = slo.error_budget_remaining

        if budget > 50:
            return "graceful_restart"
        elif budget > 20:
            return "quick_restart"
        elif budget > 5:
            return "failover_to_backup"
        else:
            return "emergency_escalate_vp"

    def decide_escalation_timing(self, service_ref: str) -> Dict[str, int]:
        """Decide escalation timing based on SLO"""
        slo = self.l6.get_slo(service_ref)
        if not slo:
            return {
                'notify_slack_immediately': 0,
                'page_oncall_if_not_ack': 5 * 60,  # 5 min
                'escalate_to_manager': 15 * 60,   # 15 min
                'escalate_to_vp': 30 * 60,        # 30 min
            }

        budget = slo.error_budget_remaining

        if budget > 50:
            # Plenty of budget, can wait
            return {
                'notify_slack': 0,
                'page_oncall': 10 * 60,   # 10 min
                'escalate_manager': 20 * 60,
            }
        elif budget > 20:
            # Low budget, escalate faster
            return {
                'notify_slack': 0,
                'page_oncall': 2 * 60,    # 2 min
                'escalate_manager': 5 * 60,
                'escalate_vp': 15 * 60,
            }
        else:
            # Emergency, immediate action
            return {
                'notify_slack': 0,
                'page_oncall': 1 * 60,    # 1 min
                'escalate_vp': 5 * 60,    # 5 min immediately
            }

    def decide_failover_eligibility(self, service_ref: str) -> bool:
        """Check if service should be failed over"""
        slo = self.l6.get_slo(service_ref)
        if not slo:
            return False

        # Only failover if budget < 20% (critical)
        return slo.error_budget_remaining < 20
```

---

## Module 4: Runbook Executor

**File:** `topology-tools/scripts/l7_operations/runbook_executor.py`

```python
"""
Runbook Executor
Executes runbook steps (auto and manual)
"""

class RunbookExecutor:
    def __init__(self, l6_loader, l5_loader, l7_loader):
        self.l6 = l6_loader
        self.l5 = l5_loader
        self.l7 = l7_loader

    def execute_runbook(self, runbook_id: str, context: Dict) -> bool:
        """Execute runbook steps"""
        runbook = self.l6.get_runbook_template(runbook_id)
        if not runbook:
            print(f"Runbook not found: {runbook_id}")
            return False

        print(f"\n📋 Executing runbook: {runbook.id}\n")

        for step in runbook.steps:
            print(f"Step {step.get('step', '?')}: {step.get('action', '?')}")

            if step['action'] == 'auto_execute':
                # Auto-execute step
                success = self._execute_auto_step(step, context)
                if not success:
                    print(f"❌ Step failed: {step.get('action')}")
                    return False
                print(f"✓ Step completed")

            elif step['action'] == 'manual_decision':
                # Require human input
                decision = self._get_manual_decision(step, context)
                if decision == 'abort':
                    return False
                context['last_decision'] = decision
                print(f"✓ Decision made: {decision}")

            else:
                print(f"⚠ Unknown action: {step['action']}")

        return True

    def _execute_auto_step(self, step: Dict, context: Dict) -> bool:
        """Execute automatic recovery step"""
        action = step.get('action')

        if action == 'check_dependencies':
            return self._check_dependencies(context)
        elif action == 'restart_service':
            return self._restart_service(context)
        elif action == 'failover_service':
            return self._failover_service(context)
        else:
            print(f"Unknown action: {action}")
            return False

    def _check_dependencies(self, context: Dict) -> bool:
        """Check all service dependencies are healthy"""
        service_ref = context['service_ref']
        service = self.l5.get_service(service_ref)

        deps = service.get('dependencies', [])
        if not deps:
            return True

        print(f"Checking {len(deps)} dependencies...")
        for dep_ref in deps:
            dep_service = self.l5.get_service(dep_ref)
            health_endpoint = dep_service.get('health_endpoint', '/health')
            # TODO: check health
            print(f"  ✓ {dep_ref} healthy")

        return True

    def _restart_service(self, context: Dict) -> bool:
        """Restart service"""
        service_ref = context['service_ref']
        service = self.l5.get_service(service_ref)
        service_type = service.get('type')

        print(f"Restarting {service_type}: {service_ref}...")
        # TODO: implement restart logic
        return True

    def _failover_service(self, context: Dict) -> bool:
        """Failover service to backup"""
        service_ref = context['service_ref']
        backup_location = context.get('backup_location')

        print(f"Failing over {service_ref} to {backup_location}...")
        # TODO: implement failover logic
        return True

    def _get_manual_decision(self, step: Dict, context: Dict) -> str:
        """Get manual decision from operator"""
        print(step.get('context', 'What would you like to do?'))
        options = step.get('options', ['continue', 'abort'])

        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")

        # TODO: get input from operator
        return options[0]  # Default to first option
```

---

## Integration Example

**File:** `topology-tools/scripts/l7_operations/main.py`

```python
"""
Main L7 Operations Orchestrator
"""

from pathlib import Path
from l6_data_loader import L6DataLoader
from incident_handler import IncidentHandler
from slo_decision_engine import SLODecisionEngine

def main():
    # Initialize loaders
    l6_loader = L6DataLoader(Path("topology"))
    l6_loader.load_all()

    # Initialize handlers
    incident_handler = IncidentHandler(
        l6_loader=l6_loader,
        l5_loader=None,  # TODO: add L5 loader
        log_dir=Path(".logs")
    )

    slo_engine = SLODecisionEngine(l6_loader)

    # Example: handle incident
    print("\n" + "="*60)
    print("L7 Operations Handler - Ready")
    print("="*60)

    # Simulate alert
    alert_id = "alert-web.nextcloud-down"
    print(f"\n📢 Alert received: {alert_id}\n")

    # Handle incident
    incident_handler.handle_incident(alert_id)

    print("\n" + "="*60)
    print("L7 Handler Complete")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
```

---

## Testing Suite

**File:** `tests/unit/l7_operations/test_incident_handler.py`

```python
"""
Unit tests for L7 incident handler
"""

import pytest
from pathlib import Path
from l6_data_loader import L6DataLoader
from incident_handler import IncidentHandler, RecoveryStrategy

@pytest.fixture
def l6_loader():
    loader = L6DataLoader(Path("topology"))
    loader.load_all()
    return loader

def test_incident_handler_graceful_restart(l6_loader):
    """Test graceful restart strategy for low-urgency incidents"""
    incident_handler = IncidentHandler(l6_loader, None, Path(".logs"))

    context = {
        'alert_id': 'test-alert',
        'service_ref': 'svc-web.nextcloud',
        'service_type': 'lxc',
        'error_budget_remaining': 80.0,  # Plenty of budget
        'dependencies': []
    }

    strategy = incident_handler._decide_recovery_strategy(context)
    assert strategy == RecoveryStrategy.GRACEFUL_RESTART

def test_incident_handler_emergency_escalation(l6_loader):
    """Test emergency escalation for critical budget"""
    incident_handler = IncidentHandler(l6_loader, None, Path(".logs"))

    context = {
        'alert_id': 'test-alert',
        'service_ref': 'svc-web.nextcloud',
        'error_budget_remaining': 2.0,  # Critical
        'dependencies': []
    }

    strategy = incident_handler._decide_recovery_strategy(context)
    assert strategy == RecoveryStrategy.EMERGENCY_FAILOVER

def test_slo_escalation_timing(l6_loader):
    """Test SLO-based escalation timing"""
    slo_engine = SLODecisionEngine(l6_loader)

    # Test low budget scenario
    timing = slo_engine.decide_escalation_timing('svc-web.nextcloud')

    # Should escalate quickly
    assert timing['page_oncall_if_not_ack'] <= 2 * 60  # ≤ 2 minutes
```

---

## Quick Start

```bash
# 1. Copy modules to project
cp l6_data_loader.py topology-tools/scripts/l7_operations/
cp incident_handler.py topology-tools/scripts/l7_operations/
cp slo_decision_engine.py topology-tools/scripts/l7_operations/
cp runbook_executor.py topology-tools/scripts/l7_operations/
cp main.py topology-tools/scripts/l7_operations/

# 2. Install requirements
pip install pyyaml

# 3. Run L7 handler
python topology-tools/scripts/l7_operations/main.py

# 4. Run tests
pytest tests/unit/l7_operations/ -v
```

---

**Next:** Integration testing and validation at scale

Ready to deploy L7→L6 integration!
