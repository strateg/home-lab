# Service Chain Evidence (maintenance-check)

**Generated:** 2026-03-28 20:12:03Z
**Operator:** Dmitri
**Commit SHA:** 456b0de8bba23d950c4da1caff5c31161dc6af1a
**Project:** home-lab
**Environment:** production
**Mode:** maintenance-check
**Decision:** no-go

Summary: executed=15/15, passed=11, failed=4, plan_only=false

| # | Step | Command | Result | Duration (s) |
|---|------|---------|--------|--------------|
| 1 | `framework.lock-refresh` | `task framework:lock-refresh` | PASS | 1.57 |
| 2 | `framework.strict` | `task framework:strict` | PASS | 4.18 |
| 3 | `validate.v5` | `task validate:v5` | PASS | 6.65 |
| 4 | `compile.generated` | `C:\Python313\python.exe topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated` | PASS | 3.85 |
| 5 | `terraform.proxmox.init` | `terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false` | PASS | 0.52 |
| 6 | `terraform.proxmox.validate` | `terraform -chdir=generated/home-lab/terraform/proxmox validate` | PASS | 0.54 |
| 7 | `terraform.proxmox.plan` | `terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false` | FAIL(1) | 0.13 |
| 8 | `terraform.mikrotik.init` | `terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false` | PASS | 0.40 |
| 9 | `terraform.mikrotik.validate` | `terraform -chdir=generated/home-lab/terraform/mikrotik validate` | PASS | 0.44 |
| 10 | `terraform.mikrotik.plan` | `terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false` | FAIL(1) | 0.11 |
| 11 | `ansible.runtime` | `task ansible:runtime` | PASS | 0.27 |
| 12 | `ansible.syntax` | `task ansible:syntax` | FAIL(201) | 0.71 |
| 13 | `ansible.execute` | `task ansible:check-site` | FAIL(201) | 0.41 |
| 14 | `acceptance.all` | `task acceptance:tests-all` | PASS | 8.52 |
| 15 | `cutover.readiness` | `task framework:cutover-readiness` | PASS | 229.85 |

## Failure Details

### `terraform.proxmox.plan`

```text
[31mв•·[0m[0m
[31mв”‚[0m [0m[1m[31mError: [0m[0m[1mNo value for required variable[0m
[31mв”‚[0m [0m
[31mв”‚[0m [0m[0m  on variables.tf line 1:
[31mв”‚[0m [0m   1: [4mvariable "proxmox_api_url"[0m {[0m
[31mв”‚[0m [0m
[31mв”‚[0m [0mThe root module input variable "proxmox_api_url" is not set, and has no
[31mв”‚[0m [0mdefault value. Use a -var or -var-file command line argument to provide a
[31mв”‚[0m [0mvalue for this variable.
[31mв•µ[0m[0m
[31mв•·[0m[0m
[31mв”‚[0m [0m[1m[31mError: [0m[0m[1mNo value for required variable[0m
[31mв”‚[0m [0m
[31mв”‚[0m [0m[0m  on variables.tf line 6:
[31mв”‚[0m [0m   6: [4mvariable "proxmox_api_token"[0m {[0m
[31mв”‚[0m [0m
[31mв”‚[0m [0mThe root module input variable "proxmox_api_token" is not set, and has no
[31mв”‚[0m [0mdefault value. Use a -var or -var-file command line argument to provide a
[31mв”‚[0m [0mvalue for this variable.
[31mв•µ[0m[0m
```

### `terraform.mikrotik.plan`

```text
[31mв•·[0m[0m
[31mв”‚[0m [0m[1m[31mError: [0m[0m[1mNo value for required variable[0m
[31mв”‚[0m [0m
[31mв”‚[0m [0m[0m  on variables.tf line 1:
[31mв”‚[0m [0m   1: [4mvariable "mikrotik_host"[0m {[0m
[31mв”‚[0m [0m
[31mв”‚[0m [0mThe root module input variable "mikrotik_host" is not set, and has no
[31mв”‚[0m [0mdefault value. Use a -var or -var-file command line argument to provide a
[31mв”‚[0m [0mvalue for this variable.
[31mв•µ[0m[0m
[31mв•·[0m[0m
[31mв”‚[0m [0m[1m[31mError: [0m[0m[1mNo value for required variable[0m
[31mв”‚[0m [0m
[31mв”‚[0m [0m[0m  on variables.tf line 12:
[31mв”‚[0m [0m  12: [4mvariable "mikrotik_password"[0m {[0m
[31mв”‚[0m [0m
[31mв”‚[0m [0mThe root module input variable "mikrotik_password" is not set, and has no
[31mв”‚[0m [0mdefault value. Use a -var or -var-file command line argument to provide a
[31mв”‚[0m [0mvalue for this variable.
[31mв•µ[0m[0m
```

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
