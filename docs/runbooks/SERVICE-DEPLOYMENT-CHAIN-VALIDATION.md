# Service Deployment Chain Validation

**Status:** Active
**Updated:** 2026-03-28
**Purpose:** Evidence checklist for Phase 12 chain: topology -> compile -> generate -> terraform -> ansible

---

## 1. Validation Chain

1. Topology strict validation.
2. Compile with deterministic generated outputs.
3. Terraform validate/plan for Proxmox and MikroTik.
4. Ansible runtime inventory assembly and validation.
5. Service playbook syntax/check/apply.

---

## 2. Command Checklist

```powershell
task framework:strict
task validate:v5
python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated
task terraform:validate-proxmox
task terraform:plan-proxmox
task terraform:validate-mikrotik
task terraform:plan-mikrotik
task ansible:runtime
ansible-inventory -i generated/home-lab/ansible/runtime/production/hosts.yml --list
task ansible:syntax
task ansible:check-site
task acceptance:tests-all
task framework:cutover-readiness
```

---

## 3. Evidence Template

- Date/time:
- Operator:
- Commit SHA:
- Secrets mode:
- Proxmox validate/plan result:
- MikroTik validate/plan result:
- Ansible inventory result:
- Acceptance tests result:
- Cutover readiness result:
- Decision (`go`/`no-go`):
- Follow-up tasks:

---

## 4. Current Known Gap

Integrated service playbook chain is now wired in `projects/home-lab/ansible/playbooks/`.
First execution evidence is recorded in `docs/runbooks/evidence/2026-03-28-wave-d-service-chain-evidence.md`.
Remaining closure work is production execution evidence (`apply` records + recovery validation) per `adr/plan/v5-production-readiness.md`.
