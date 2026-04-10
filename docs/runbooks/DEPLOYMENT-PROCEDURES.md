# Deployment Procedures

**Status:** Active
**Updated:** 2026-03-28
**Scope:** V5 deployment path for infrastructure and service runtime

---

## 1. Preconditions

1. Working tree is clean (except approved local files such as `.secrets.baseline`).
2. `topology/topology.yaml` points to the intended active project.
3. `framework.lock.yaml` is current and strict-valid.
4. Required tooling is installed: Python, `task`, Terraform, Ansible, `sops`/`age` (if inject mode is used).

---

## 2. Baseline Strict Gates

```powershell
task framework:strict
task validate:default
task framework:release-tests
```

Stop on first failure and remediate before deploy planning.

---

## 3. Generate Deployment Artifacts

```powershell
.venv/bin/python topology-tools/compile-topology.py `
  --topology topology/topology.yaml `
  --strict-model-lock `
  --secrets-mode passthrough `
  --artifacts-root generated
```

If operational window requires resolved secrets, use `--secrets-mode inject`.

---

## 4. Proxmox Terraform Lane

```powershell
terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false
terraform -chdir=generated/home-lab/terraform/proxmox fmt -check
terraform -chdir=generated/home-lab/terraform/proxmox validate
terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false
```

Apply is executed only in approved maintenance window:

```powershell
terraform -chdir=generated/home-lab/terraform/proxmox apply
```

Task shortcut:

```powershell
task terraform:validate-proxmox
task terraform:plan-proxmox
```

Optional remote state mode (when `backend.tf` is generated):

```powershell
terraform -chdir=generated/home-lab/terraform/proxmox init -reconfigure -input=false `
  -backend-config=../../../../projects/home-lab/secrets/terraform/proxmox.backend.tfbackend
terraform -chdir=generated/home-lab/terraform/proxmox plan
```

---

## 5. MikroTik Terraform Lane

```powershell
terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false
terraform -chdir=generated/home-lab/terraform/mikrotik fmt -check
terraform -chdir=generated/home-lab/terraform/mikrotik validate
terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false
```

Apply in maintenance window:

```powershell
terraform -chdir=generated/home-lab/terraform/mikrotik apply
```

Task shortcut:

```powershell
task terraform:validate-mikrotik
task terraform:plan-mikrotik
```

Optional remote state mode (when `backend.tf` is generated):

```powershell
terraform -chdir=generated/home-lab/terraform/mikrotik init -reconfigure -input=false `
  -backend-config=../../../../projects/home-lab/secrets/terraform/mikrotik.backend.tfbackend
terraform -chdir=generated/home-lab/terraform/mikrotik plan
```

---

## 6. Service Runtime Lane

Runtime inventory assembly:

```powershell
task ansible:runtime
```

Inventory validation:

```powershell
ansible-inventory -i generated/home-lab/ansible/runtime/production/hosts.yml --list > $null
```

Service playbook quality gates:

```powershell
task ansible:syntax
task ansible:check-site
```

If Windows-native `ansible-playbook` is unavailable, run syntax lane via WSL:

```powershell
wsl bash -lc "cd /mnt/d/Workspaces/PycharmProjects/home-lab && ANSIBLE_ROLES_PATH=projects/home-lab/ansible/roles ansible-playbook -i generated/home-lab/ansible/runtime/production/hosts.yml projects/home-lab/ansible/playbooks/site.yml --syntax-check"
```

Integrated service playbooks:

- `projects/home-lab/ansible/playbooks/site.yml`
- `projects/home-lab/ansible/playbooks/postgresql.yml`
- `projects/home-lab/ansible/playbooks/redis.yml`
- `projects/home-lab/ansible/playbooks/nextcloud.yml`
- `projects/home-lab/ansible/playbooks/monitoring.yml`

---

## 7. Cutover Readiness Confirmation

```powershell
task acceptance:tests-all
task framework:cutover-readiness
```

Record:

1. timestamp and operator,
2. commit SHA,
3. diagnostics artifact paths,
4. go/no-go decision.
