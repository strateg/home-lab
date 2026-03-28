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

Automated evidence capture lanes:

```powershell
# dry lane (non-maintenance)
task framework:service-chain-evidence-dry

# maintenance check lane (plan + ansible --check with injected secrets/runtime)
task framework:service-chain-evidence-check -- CONTINUE_ON_FAILURE=1 ANSIBLE_VIA_WSL=1 INJECT_SECRETS=1 PROXMOX_BACKEND_CONFIG=projects/home-lab/secrets/terraform/proxmox.backend.tfbackend MIKROTIK_BACKEND_CONFIG=projects/home-lab/secrets/terraform/mikrotik.backend.tfbackend PROXMOX_VAR_FILE=generated/home-lab/terraform/proxmox/terraform.tfvars.example MIKROTIK_VAR_FILE=generated/home-lab/terraform/mikrotik/terraform.tfvars.example

# maintenance apply lane (destructive; requires explicit confirmation variable)
task framework:service-chain-evidence-apply -- ALLOW_APPLY=YES CONTINUE_ON_FAILURE=1 ANSIBLE_VIA_WSL=1 TERRAFORM_AUTO_APPROVE=1 INJECT_SECRETS=1 PROXMOX_BACKEND_CONFIG=projects/home-lab/secrets/terraform/proxmox.backend.tfbackend MIKROTIK_BACKEND_CONFIG=projects/home-lab/secrets/terraform/mikrotik.backend.tfbackend PROXMOX_VAR_FILE=generated/home-lab/terraform/proxmox/terraform.tfvars.example MIKROTIK_VAR_FILE=generated/home-lab/terraform/mikrotik/terraform.tfvars.example
```

Reports are generated under `docs/runbooks/evidence/` by `topology-tools/record-service-chain-evidence.py`.

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
Automated maintenance-check execution evidence is recorded in
`docs/runbooks/evidence/2026-03-28-service-chain-evidence-maintenance-check-execution.md`.
Automated maintenance-apply execution evidence is recorded in
`docs/runbooks/evidence/2026-03-28-service-chain-evidence-maintenance-apply.md`.
Windows-native Ansible CLI remains unavailable in this shell; maintenance lanes are executed via WSL runtime.
Current remaining blocker for final `go`: host reachability/resolution (`lxc-*` inventory targets unreachable from this execution context).
