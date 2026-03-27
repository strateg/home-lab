# V5 E2E Dry-Run Runbook

**Status:** Ready for execution
**Last Updated:** 2026-03-24
**Last Validated:** 2026-03-24 (0 errors, 14 warnings)
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

- `project.active` корректно задан в `topology/topology.yaml`
- секреты разблокированы (`sops` + `age`)
- доступны `terraform` и `ansible-core`
- подготовлен тестовый стенд/окно обслуживания

---

## 3. Commands

### 3.1 Validate + compile

```powershell
$env:V5_SECRETS_MODE='inject'
python scripts/orchestration/lane.py validate-v5
```

### 3.2 Generate artifacts (project-qualified)

```powershell
python topology-tools/compile-topology.py `
  --topology topology/topology.yaml `
  --strict-model-lock `
  --secrets-mode inject `
  --parallel-plugins `
  --artifacts-root generated
```

Примечание: `compile-topology.py` использует параллельный запуск плагинов по умолчанию.
Для диагностических прогонов можно добавить `--no-parallel-plugins`.

### 3.3 Assemble ansible runtime

```powershell
python topology-tools/assemble-ansible-runtime.py `
  --topology topology/topology.yaml `
  --env production
```

### 3.4 Terraform checks

```powershell
terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false
terraform -chdir=generated/home-lab/terraform/proxmox fmt -check
terraform -chdir=generated/home-lab/terraform/proxmox validate

terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false
terraform -chdir=generated/home-lab/terraform/mikrotik fmt -check
terraform -chdir=generated/home-lab/terraform/mikrotik validate
```

### 3.5 Terraform dry-run plan

```powershell
terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false
terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false
```

### 3.6 Ansible inventory and check mode

```powershell
ansible-inventory -i generated/home-lab/ansible/runtime/production/hosts.yml --list > $null

ansible-playbook `
  -i generated/home-lab/ansible/runtime/production/hosts.yml `
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

- `build/diagnostics/report.json`
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

---

## 8. Validation History

| Date | Errors | Warnings | Notes |
|------|--------|----------|-------|
| 2026-03-23 | 0 | 39 | Initial E2E with W7844 warnings |
| 2026-03-24 | 0 | 14 | After W7844 fixes (validator + ip_allocations) |

### 2026-03-24 Remaining Warnings (non-blocking)

| Code | Count | Description |
|------|-------|-------------|
| W7816 | 2 | IP reuse (expected: gateway, postgres listen) |
| W7845 | 3 | SSL certificate intent missing |
| W7888 | 9 | Deprecated inline resources in LXC |

### 2026-03-24 E2E Results

```
Terraform Proxmox:  ✅ init + validate
Terraform MikroTik: ✅ init + validate
Ansible inventory:  ✅ 15 hosts loaded
Bootstrap:          ✅ 3 devices (rtr-mikrotik-chateau, srv-gamayun, srv-orangepi5)
```
