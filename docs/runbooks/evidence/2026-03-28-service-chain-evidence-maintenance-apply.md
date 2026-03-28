# Service Chain Evidence (maintenance-apply)

**Generated:** 2026-03-28 21:45:29Z
**Operator:** Dmitri
**Commit SHA:** 94bb9978da2b3b4b16442f784cc2758e5c19f6a5
**Project:** home-lab
**Environment:** production
**Mode:** maintenance-apply
**Decision:** no-go

Summary: executed=17/17, passed=16, failed=1, plan_only=false

| # | Step | Command | Result | Duration (s) |
|---|------|---------|--------|--------------|
| 1 | `framework.lock-refresh` | `task framework:lock-refresh` | PASS | 0.73 |
| 2 | `framework.strict` | `task framework:strict` | PASS | 5.57 |
| 3 | `validate.v5` | `task validate:v5` | PASS | 6.89 |
| 4 | `compile.generated` | `C:\Python313\python.exe topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated` | PASS | 9.44 |
| 5 | `terraform.proxmox.init` | `terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false` | PASS | 0.65 |
| 6 | `terraform.proxmox.validate` | `terraform -chdir=generated/home-lab/terraform/proxmox validate` | PASS | 2.90 |
| 7 | `terraform.proxmox.apply` | `terraform -chdir=generated/home-lab/terraform/proxmox apply -auto-approve -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\proxmox\terraform.tfvars.example` | PASS | 0.96 |
| 8 | `terraform.proxmox.plan` | `terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\proxmox\terraform.tfvars.example` | PASS | 0.62 |
| 9 | `terraform.mikrotik.init` | `terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false` | PASS | 0.78 |
| 10 | `terraform.mikrotik.validate` | `terraform -chdir=generated/home-lab/terraform/mikrotik validate` | PASS | 0.95 |
| 11 | `terraform.mikrotik.apply` | `terraform -chdir=generated/home-lab/terraform/mikrotik apply -auto-approve -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\mikrotik\terraform.tfvars.example` | PASS | 0.98 |
| 12 | `terraform.mikrotik.plan` | `terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\mikrotik\terraform.tfvars.example` | PASS | 1.07 |
| 13 | `ansible.runtime` | `task ansible:runtime` | PASS | 0.65 |
| 14 | `ansible.syntax` | `wsl bash -lc cd '/mnt/d/Workspaces/PycharmProjects/home-lab' && export ANSIBLE_CONFIG='/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/ansible.cfg' && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/site.yml' --syntax-check && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/postgresql.yml' --syntax-check && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/redis.yml' --syntax-check && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/nextcloud.yml' --syntax-check && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/monitoring.yml' --syntax-check` | PASS | 13.34 |
| 15 | `ansible.execute` | `wsl bash -lc cd '/mnt/d/Workspaces/PycharmProjects/home-lab' && ANSIBLE_CONFIG='/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/ansible.cfg' ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/site.yml'` | FAIL(4) | 26.48 |
| 16 | `acceptance.all` | `task acceptance:tests-all` | PASS | 10.86 |
| 17 | `cutover.readiness` | `task framework:cutover-readiness` | PASS | 286.72 |

## Failure Details

### `ansible.execute`

```text
[stdout]
PLAY [Apply common configuration] **********************************************

TASK [Gathering Facts] *********************************************************
fatal: [lxc-docker]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-docker: Temporary failure in name resolution'
  unreachable: true
fatal: [lxc-gitea]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-gitea: Temporary failure in name resolution'
  unreachable: true
fatal: [lxc-grafana]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-grafana: Temporary failure in name resolution'
  unreachable: true
fatal: [lxc-homeassistant]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-homeassistant: Temporary failure in name resolution'
  unreachable: true
fatal: [lxc-nextcloud]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-nextcloud: Temporary failure in name resolution'
  unreachable: true
fatal: [lxc-nginx-proxy]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-nginx-proxy: Temporary failure in name resolution'
  unreachable: true
fatal: [lxc-postgresql]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-postgresql: Temporary failure in name resolution'
  unreachable: true
fatal: [lxc-prometheus]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-prometheus: Temporary failure in name resolution'
  unreachable: true
fatal: [lxc-redis]: UNREACHABLE! => changed=false
  msg: 'Failed to connect to the host via ssh: ssh: Could not resolve hostname lxc-redis: Temporary failure in name resolution'
  unreachable: true

PLAY RECAP *********************************************************************
lxc-docker                 : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
lxc-gitea                  : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
lxc-grafana                : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
lxc-homeassistant          : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
lxc-nextcloud              : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
lxc-nginx-proxy            : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
lxc-postgresql             : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
lxc-prometheus             : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
lxc-redis                  : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0

[stderr]
[DEPRECATION WARNING]: community.general.yaml has been deprecated. The plugin
has been superseded by the the option `result_format=yaml` in callback plugin
ansible.builtin.default from ansible-core 2.13 onwards. This feature will be
removed from community.general in version 13.0.0. Deprecation warnings can be
disabled by setting deprecation_warnings=False in ansible.cfg.
```
