# Monitoring Alert Runbooks

**Status:** Active
**Updated:** 2026-03-28
**Scope:** Alert response procedures for home-lab runtime

---

## 1. Alert Priorities

1. **P1 (Critical):** service down, unreachable gateway/router, storage failure.
2. **P2 (High):** degraded performance, repeated backup failures, certificate expiry warning.
3. **P3 (Medium):** non-blocking telemetry gaps, single-check flaps.

---

## 2. Generic Alert Handling Flow

1. Acknowledge alert in monitoring system.
2. Confirm signal validity (avoid false positives).
3. Classify impact and assign priority.
4. Execute component-specific checks.
5. Apply remediation or rollback.
6. Capture incident evidence and close with root-cause note.

---

## 3. Component Runbooks

### 3.1 Network/Router Alerts

Checks:

```powershell
task validate:v5-layers
terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false
```

Actions:

1. Validate interface/VLAN/firewall topology references.
2. Roll back last router Terraform apply if regression confirmed.

### 3.2 Compute/Virtualization Alerts

Checks:

```powershell
terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false
```

Actions:

1. Validate VM/LXC resource declarations.
2. Restore from previous known-good infra plan if drift is unsafe.

### 3.3 Service Runtime Alerts

Checks:

```powershell
python topology-tools/assemble-ansible-runtime.py --topology topology/topology.yaml --env production
ansible-inventory -i generated/home-lab/ansible/runtime/production/hosts.yml --list
```

Actions:

1. Verify runtime target bindings and host vars.
2. Execute service playbook `--check` before apply.

### 3.4 Backup/Storage Alerts

Checks:

```powershell
task framework:cutover-readiness-quick
```

Actions:

1. Validate latest backup artifact integrity.
2. Trigger restore rehearsal if backup integrity is uncertain.

---

## 4. Post-Incident Closure

Each closed incident must include:

- detection timestamp,
- impacted components,
- remediation steps,
- validation command outputs,
- follow-up task for permanent fix.
