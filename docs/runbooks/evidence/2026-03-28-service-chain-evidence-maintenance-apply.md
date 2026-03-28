# Service Chain Evidence (maintenance-apply)

**Generated:** 2026-03-28 21:06:40Z
**Operator:** Dmitri
**Commit SHA:** 3ab1806c08678279a2883bda704aaa01b33d32f4
**Project:** home-lab
**Environment:** production
**Mode:** maintenance-apply
**Decision:** no-go

Summary: executed=17/17, passed=15, failed=2, plan_only=false

| # | Step | Command | Result | Duration (s) |
|---|------|---------|--------|--------------|
| 1 | `framework.lock-refresh` | `task framework:lock-refresh` | PASS | 0.81 |
| 2 | `framework.strict` | `task framework:strict` | PASS | 5.26 |
| 3 | `validate.v5` | `task validate:v5` | PASS | 7.38 |
| 4 | `compile.generated` | `C:\Python313\python.exe topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated` | PASS | 4.35 |
| 5 | `terraform.proxmox.init` | `terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false` | PASS | 0.53 |
| 6 | `terraform.proxmox.validate` | `terraform -chdir=generated/home-lab/terraform/proxmox validate` | PASS | 0.67 |
| 7 | `terraform.proxmox.apply` | `terraform -chdir=generated/home-lab/terraform/proxmox apply -auto-approve -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\proxmox\terraform.tfvars.example` | PASS | 0.28 |
| 8 | `terraform.proxmox.plan` | `terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\proxmox\terraform.tfvars.example` | PASS | 0.26 |
| 9 | `terraform.mikrotik.init` | `terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false` | PASS | 0.42 |
| 10 | `terraform.mikrotik.validate` | `terraform -chdir=generated/home-lab/terraform/mikrotik validate` | PASS | 0.36 |
| 11 | `terraform.mikrotik.apply` | `terraform -chdir=generated/home-lab/terraform/mikrotik apply -auto-approve -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\mikrotik\terraform.tfvars.example` | PASS | 0.26 |
| 12 | `terraform.mikrotik.plan` | `terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\mikrotik\terraform.tfvars.example` | PASS | 0.26 |
| 13 | `ansible.runtime` | `task ansible:runtime` | PASS | 0.30 |
| 14 | `ansible.syntax` | `task ansible:syntax` | FAIL(201) | 0.74 |
| 15 | `ansible.execute` | `task ansible:apply-site` | FAIL(201) | 0.41 |
| 16 | `acceptance.all` | `task acceptance:tests-all` | PASS | 11.63 |
| 17 | `cutover.readiness` | `task framework:cutover-readiness` | PASS | 292.61 |

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
task: Failed to run task "ansible:apply-site": task: precondition not met
```
