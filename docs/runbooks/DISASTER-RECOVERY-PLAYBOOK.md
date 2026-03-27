# Disaster Recovery Playbook

**Status:** Active
**Updated:** 2026-03-28
**Scope:** DR execution for v5 infrastructure lane

---

## 1. DR Objectives

- **RTO target:** 4 hours (initial operational baseline).
- **RPO target:** 24 hours for configuration and generated artifacts.

Targets should be revised after first full DR rehearsal.

---

## 2. Trigger Conditions

Start DR process when one of the following occurs:

1. control-plane host unavailable beyond accepted maintenance window,
2. unrecoverable Terraform state drift,
3. critical storage loss affecting generated/runtime artifacts,
4. security incident requiring full environment rebuild.

---

## 3. DR Execution Steps

1. Declare incident and freeze non-DR changes.
2. Select recovery point (commit/tag + secrets snapshot).
3. Restore repository and encrypted secrets bundle.
4. Rebuild compiled/generated artifacts:

```powershell
python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated
```

5. Validate readiness:

```powershell
task framework:strict
task validate:v5
task framework:cutover-readiness
```

6. Re-apply infrastructure lanes in controlled order:
   - Proxmox Terraform plan/apply,
   - MikroTik Terraform plan/apply,
   - Ansible runtime assembly and service playbook apply (where available).
7. Execute post-restore smoke tests and confirm critical service health.

---

## 4. Communication and Evidence

Record:

- incident start/end timestamps,
- selected recovery point,
- command outputs for all gates,
- deviations from normal procedure,
- final recovery status (`recovered` or `partial`).

---

## 5. DR Rehearsal Cadence

- run tabletop rehearsal monthly,
- run technical restore rehearsal quarterly,
- update this playbook after each rehearsal with measured RTO/RPO.
