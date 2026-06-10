# Simplified State Management: Industry Best Practices

**ADR Reference:** 0105 (Revision)
**Date:** 2026-06-10

---

## Принцип

Вместо изобретения собственной системы state commit используем проверенные практики каждого инструмента:

| Tool | State Management | Rollback | Validation |
|------|------------------|----------|------------|
| Terraform | Remote backend + versioning | VCS revert + re-apply | `terraform plan` |
| Ansible | Git + block/rescue/always | Re-apply previous playbook | `--check` mode |
| MikroTik | Safe-mode + export backup | Auto-revert on disconnect | API health check |
| Proxmox | Terraform state + VM snapshots | State restore | API health check |

---

## 1. Terraform State Management

### Remote Backend (выбрать один)

**Option A: GitLab Managed State** (рекомендуется для home-lab)
```hcl
# backend.tf
terraform {
  backend "http" {
    address        = "https://gitlab.com/api/v4/projects/<PROJECT_ID>/terraform/state/<STATE_NAME>"
    lock_address   = "https://gitlab.com/api/v4/projects/<PROJECT_ID>/terraform/state/<STATE_NAME>/lock"
    unlock_address = "https://gitlab.com/api/v4/projects/<PROJECT_ID>/terraform/state/<STATE_NAME>/lock"
    username       = "gitlab-ci-token"
    password       = "${CI_JOB_TOKEN}"  # or personal access token
  }
}
```

**Option B: S3 с native locking** (Terraform 1.10+)
```hcl
terraform {
  backend "s3" {
    bucket       = "homelab-terraform-state"
    key          = "mikrotik/terraform.tfstate"
    region       = "eu-frankfurt-1"
    use_lockfile = true  # Native S3 locking, no DynamoDB needed
  }
}
```

**Option C: Local с Git** (простой вариант)
```hcl
terraform {
  backend "local" {
    path = ".work/terraform-state/mikrotik/terraform.tfstate"
  }
}
```
+ Добавить `.work/terraform-state/` в `.gitignore`
+ Backup в отдельную директорию перед apply

### Rollback Pattern

```bash
# 1. Identify last good commit
git log --oneline generated/home-lab/terraform/mikrotik/

# 2. Revert to previous config
git revert <bad_commit>

# 3. Re-apply
terraform plan   # Always plan first!
terraform apply
```

### Blast Radius Reduction

Разделять state по устройствам:
```
generated/home-lab/terraform/
├── mikrotik/          # Separate state
│   └── terraform.tfstate
├── proxmox/           # Separate state
│   └── terraform.tfstate
└── oracle/            # Separate state
    └── terraform.tfstate
```

---

## 2. MikroTik Safe-Mode Integration

### Встроенный механизм отката

MikroTik Safe-Mode = автоматический rollback при потере соединения.

```
Workflow:
1. Enter safe-mode (Ctrl+X or API)
2. Make changes (Terraform apply)
3. Verify connectivity
4. Exit safe-mode with save (or auto-revert on timeout)
```

### Интеграция с Terraform

```bash
#!/bin/bash
# scripts/mikrotik-safe-apply.sh

ROUTER_IP="192.168.88.1"
ROUTER_USER="automator"

# 1. Enter safe-mode via API
curl -k -u "$ROUTER_USER:$MIKROTIK_PASSWORD" \
  -X POST "https://$ROUTER_IP/rest/system/safe-mode"

# 2. Apply Terraform
cd generated/home-lab/terraform/mikrotik
terraform apply -auto-approve

# 3. Health check
if curl -k -s -o /dev/null -w "%{http_code}" \
   "https://$ROUTER_IP/rest/system/resource" | grep -q "200"; then
  echo "Health check passed, exiting safe-mode with save"
  # Exit safe-mode - changes saved
  curl -k -u "$ROUTER_USER:$MIKROTIK_PASSWORD" \
    -X POST "https://$ROUTER_IP/rest/system/safe-mode" \
    -d '{"action":"release"}'
else
  echo "Health check failed, waiting for auto-revert (9 min timeout)"
  exit 1
fi
```

### Export Backup Before Apply

```bash
# Backup current config before any changes
ssh admin@192.168.88.1 "/export file=backup-$(date +%Y%m%d-%H%M%S)"
```

### Ограничения Safe-Mode

- Timeout: 9 минут (TCP timeout)
- History limit: 100 actions
- Не помогает при hardware failure
- Только для изменений, влияющих на connectivity

---

## 3. Ansible Rollback Patterns

### Block/Rescue/Always

```yaml
- name: Apply configuration with rollback
  block:
    - name: Apply new config
      community.routeros.api:
        # ... configuration tasks

    - name: Verify connectivity
      wait_for:
        host: "{{ mikrotik_host }}"
        port: 443
        timeout: 30

  rescue:
    - name: Rollback on failure
      include_tasks: rollback-mikrotik.yml

  always:
    - name: Log result
      debug:
        msg: "Configuration {{ 'applied' if ansible_failed_task is not defined else 'rolled back' }}"
```

### Previous State Playbook

```yaml
# Store previous config before changes
- name: Backup current state
  community.routeros.api:
    hostname: "{{ mikrotik_host }}"
    path: "/export"
  register: current_config

- name: Save backup to file
  copy:
    content: "{{ current_config.msg }}"
    dest: ".work/backups/mikrotik-{{ ansible_date_time.iso8601 }}.rsc"
  delegate_to: localhost
```

### Check Mode

```bash
# Dry-run before apply
ansible-playbook playbook.yml --check --diff
```

---

## 4. Proxmox State Management

### Terraform State

Использовать remote backend (см. раздел 1).

### VM/LXC Snapshots Before Changes

```hcl
# Создать snapshot перед изменениями
resource "proxmox_virtual_environment_vm_snapshot" "pre_change" {
  node_name = "pve"
  vm_id     = proxmox_virtual_environment_vm.example.vm_id
  name      = "pre-terraform-${formatdate("YYYYMMDD-hhmm", timestamp())}"
}
```

### Lifecycle Protection

```hcl
resource "proxmox_virtual_environment_vm" "critical_vm" {
  # ...

  lifecycle {
    prevent_destroy = true  # Protect critical VMs
  }
}
```

### HA Cluster Drift

Если VM мигрирует между нодами (HA):
```bash
# Refresh state to match actual location
terraform refresh
```

---

## 5. Unified Workflow

### Pre-Apply Checklist

```bash
# task deploy:pre-check
1. terraform validate
2. terraform plan (review changes)
3. ansible-playbook --check --diff
4. Backup current state (export/snapshot)
```

### Apply Workflow

```bash
# task deploy:apply DEVICE=mikrotik
1. Enter MikroTik safe-mode (if applicable)
2. terraform apply
3. Health check (API reachable)
4. Exit safe-mode with save (or auto-revert)
5. Git commit state metadata
```

### Rollback Workflow

```bash
# task deploy:rollback DEVICE=mikrotik COMMIT=<sha>
1. git checkout <commit> -- generated/home-lab/terraform/mikrotik/
2. terraform plan (verify rollback)
3. Enter safe-mode
4. terraform apply
5. Health check
6. Exit safe-mode
```

---

## 6. Рекомендуемая структура

```
.work/
├── terraform-state/           # Local state (gitignored)
│   ├── mikrotik/
│   ├── proxmox/
│   └── oracle/
├── backups/                   # Config backups
│   ├── mikrotik/
│   │   └── export-20260610.rsc
│   └── proxmox/
│       └── vzdump-*.tar.zst
└── deploy-log/                # Apply history (git-tracked metadata only)
    └── history.yaml
```

### history.yaml (git-tracked)

```yaml
# Только metadata, без secrets
applies:
  - timestamp: "2026-06-10T12:00:00Z"
    device: "rtr-mikrotik-chateau"
    git_commit: "8f85cfe4"
    terraform_plan_hash: "sha256:abc123..."
    status: "success"

  - timestamp: "2026-06-10T10:00:00Z"
    device: "hv-proxmox-xps"
    git_commit: "fb0e465c"
    terraform_plan_hash: "sha256:def456..."
    status: "success"
```

---

## 7. Taskfile Integration

```yaml
# taskfiles/deploy.yaml
tasks:
  pre-check:
    desc: Validate before apply
    cmds:
      - terraform -chdir=generated/home-lab/terraform/{{.DEVICE}} validate
      - terraform -chdir=generated/home-lab/terraform/{{.DEVICE}} plan -out=tfplan

  apply:
    desc: Apply with safe-mode (MikroTik)
    cmds:
      - ./scripts/mikrotik-safe-apply.sh
    vars:
      DEVICE: '{{.DEVICE | default "mikrotik"}}'

  backup:
    desc: Export current config
    cmds:
      - ssh admin@192.168.88.1 "/export file=backup-$(date +%Y%m%d)"
```

---

## Sources

### Terraform
- [Terraform State Rollback Guide](https://spacelift.io/blog/terraform-state-rollback)
- [Terraform Best Practices 2026](https://www.env0.com/blog/terraform-best-practices-state-management-reusability-security-and-beyond)
- [AWS S3 Backend Best Practices](https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/backend.html)
- [GitLab Managed Terraform State](https://docs.gitlab.com/user/infrastructure/iac/terraform_state/)
- [Terraform S3 Backend](https://spacelift.io/blog/terraform-s3-backend)

### MikroTik
- [MikroTik Safe Mode](https://help.mikrotik.com/docs/spaces/ROS/pages/328155/Configuration+Management)
- [Safe Mode Best Practices](https://mikrotikusers.com/lesson-1-4-safe-mode-undo-your-safety-net/)
- [MikroTik Terraform IaC](https://emerconnelly.com/mikrotik/routeros/terraform/terraform-create-manage-routeros-network-infrastructure/)
- [Ansible MikroTik Playbooks](https://github.com/narrowin/ansible-mikrotik)

### Ansible
- [Ansible Block/Rescue/Always](https://www.ansiblepilot.com/articles/ansible-block-rescue-always-error-handling-complete-guide/)
- [Ansible Best Practices 2025](https://toxigon.com/ansible-best-practices-for-devops-in-2025)
- [Ansible Disaster Recovery](https://oneuptime.com/blog/post/2026-02-21-how-to-use-ansible-for-disaster-recovery-planning/view)

### Proxmox
- [bpg/proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [Proxmox Terraform Advanced](https://harryvasanth.com/posts/proxmox-terraform-advanced-provider/)
- [VM Lifecycle Management](https://bpg.sh/docs/guides/vm-lifecycle/)
