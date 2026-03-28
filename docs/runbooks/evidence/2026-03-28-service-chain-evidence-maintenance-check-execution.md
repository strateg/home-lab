# Service Chain Evidence (maintenance-check)

**Generated:** 2026-03-28 21:01:04Z
**Operator:** Dmitri
**Commit SHA:** 3ab1806c08678279a2883bda704aaa01b33d32f4
**Project:** home-lab
**Environment:** production
**Mode:** maintenance-check
**Decision:** no-go

Summary: executed=15/15, passed=13, failed=2, plan_only=false

| # | Step | Command | Result | Duration (s) |
|---|------|---------|--------|--------------|
| 1 | `framework.lock-refresh` | `task framework:lock-refresh` | PASS | 0.95 |
| 2 | `framework.strict` | `task framework:strict` | PASS | 6.47 |
| 3 | `validate.v5` | `task validate:v5` | PASS | 7.86 |
| 4 | `compile.generated` | `C:\Python313\python.exe topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated` | PASS | 3.41 |
| 5 | `terraform.proxmox.init` | `terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false` | PASS | 0.60 |
| 6 | `terraform.proxmox.validate` | `terraform -chdir=generated/home-lab/terraform/proxmox validate` | PASS | 0.66 |
| 7 | `terraform.proxmox.plan` | `terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\proxmox\terraform.tfvars.example` | PASS | 0.34 |
| 8 | `terraform.mikrotik.init` | `terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false` | PASS | 0.43 |
| 9 | `terraform.mikrotik.validate` | `terraform -chdir=generated/home-lab/terraform/mikrotik validate` | PASS | 0.41 |
| 10 | `terraform.mikrotik.plan` | `terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\mikrotik\terraform.tfvars.example` | PASS | 0.25 |
| 11 | `ansible.runtime` | `task ansible:runtime` | PASS | 0.31 |
| 12 | `ansible.syntax` | `task ansible:syntax` | FAIL(201) | 0.89 |
| 13 | `ansible.execute` | `task ansible:check-site` | FAIL(201) | 0.41 |
| 14 | `acceptance.all` | `task acceptance:tests-all` | PASS | 10.40 |
| 15 | `cutover.readiness` | `task framework:cutover-readiness` | PASS | 291.98 |

## Failure Details

### `ansible.syntax`

```text
task: [ansible:runtime] .venv/Scripts/python.exe topology-tools/assemble-ansible-runtime.py --topology topology/topology.yaml --project home-lab --env production
task: ansible-playbook CLI is unavailable in current shell. Use Linux/WSL Ansible runtime and retry.
task: Failed to run task "ansible:syntax": task: precondition not met
```

### `ansible.execute`

```text
task: [ansible:runtime] .venv/Scripts/python.exe topology-tools/assemble-ansible-runtime.py --topology topology/topology.yaml --project home-lab --env production
task: ansible-playbook CLI is unavailable in current shell. Use Linux/WSL Ansible runtime and retry.
task: Failed to run task "ansible:check-site": task: precondition not met
```
