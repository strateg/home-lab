# V5 E2E Dry-Run Runbook

**Status:** Ready for execution  
**Last Updated:** 2026-03-20  
**Scope:** ADR0074 Phase 8 (end-to-end dry-run and cutover gate)

---

## 1. Purpose

Проверить полный v5 путь без production apply:

1. compile/validate topology
2. generate Terraform/Ansible artifacts
3. validate Terraform syntax and plan
4. validate Ansible inventory and `--check` run

---

## 2. Preconditions

- `project.active` корректно задан в `v5/topology/topology.yaml`
- секреты разблокированы (`sops` + `age`)
- доступны `terraform` и `ansible-core`
- подготовлен тестовый стенд/окно обслуживания

---

## 3. Commands

### 3.1 Validate + compile

```powershell
$env:V5_SECRETS_MODE='inject'
python v5/scripts/lane.py validate-v5
```

### 3.2 Generate artifacts (project-qualified)

```powershell
python v5/topology-tools/compile-topology.py `
  --topology v5/topology/topology.yaml `
  --strict-model-lock `
  --secrets-mode inject `
  --artifacts-root v5-generated
```

### 3.3 Assemble ansible runtime

```powershell
python v5/topology-tools/assemble-ansible-runtime.py `
  --topology v5/topology/topology.yaml `
  --env production
```

### 3.4 Terraform checks

```powershell
terraform -chdir=v5-generated/home-lab/terraform/proxmox init -backend=false -input=false
terraform -chdir=v5-generated/home-lab/terraform/proxmox fmt -check
terraform -chdir=v5-generated/home-lab/terraform/proxmox validate

terraform -chdir=v5-generated/home-lab/terraform/mikrotik init -backend=false -input=false
terraform -chdir=v5-generated/home-lab/terraform/mikrotik fmt -check
terraform -chdir=v5-generated/home-lab/terraform/mikrotik validate
```

### 3.5 Terraform dry-run plan

```powershell
terraform -chdir=v5-generated/home-lab/terraform/proxmox plan -refresh=false
terraform -chdir=v5-generated/home-lab/terraform/mikrotik plan -refresh=false
```

### 3.6 Ansible inventory and check mode

```powershell
ansible-inventory -i v5-generated/home-lab/ansible/runtime/production/hosts.yml --list > $null

ansible-playbook `
  -i v5-generated/home-lab/ansible/runtime/production/hosts.yml `
  ansible/playbooks/site.yml `
  --check
```

---

## 4. Acceptance Criteria

- compile/validate without errors
- Terraform `fmt` + `validate` green for both targets
- Terraform `plan` returns no contract/runtime shape errors
- `ansible-inventory --list` passes
- `ansible-playbook --check` passes on representative hosts

---

## 5. Evidence to Capture

- `v5-build/diagnostics/report.json`
- `terraform plan` logs for proxmox/mikrotik
- ansible `--check` output
- список intentional diffs/waivers (если есть)

---

## 6. Rollback/No-Go

Если любой gate провален:

1. Не выполнять apply/deploy.
2. Зафиксировать диагностику и failing command.
3. Создать remediation task и повторить dry-run после исправления.

---

## 7. Notes

- Этот runbook фиксирует процедуру. Факт выполнения dry-run должен отмечаться отдельно (release note / change record).
