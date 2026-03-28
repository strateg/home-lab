# Service Chain Evidence (maintenance-check)

**Generated:** 2026-03-28 21:39:08Z
**Operator:** Dmitri
**Commit SHA:** 94bb9978da2b3b4b16442f784cc2758e5c19f6a5
**Project:** home-lab
**Environment:** production
**Mode:** maintenance-check
**Decision:** no-go

Summary: executed=15/15, passed=14, failed=1, plan_only=false

| # | Step | Command | Result | Duration (s) |
|---|------|---------|--------|--------------|
| 1 | `framework.lock-refresh` | `task framework:lock-refresh` | PASS | 1.55 |
| 2 | `framework.strict` | `task framework:strict` | PASS | 5.91 |
| 3 | `validate.v5` | `task validate:v5` | PASS | 10.29 |
| 4 | `compile.generated` | `C:\Python313\python.exe topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated` | PASS | 6.21 |
| 5 | `terraform.proxmox.init` | `terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false` | PASS | 0.55 |
| 6 | `terraform.proxmox.validate` | `terraform -chdir=generated/home-lab/terraform/proxmox validate` | PASS | 0.64 |
| 7 | `terraform.proxmox.plan` | `terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\proxmox\terraform.tfvars.example` | PASS | 0.97 |
| 8 | `terraform.mikrotik.init` | `terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false` | PASS | 0.41 |
| 9 | `terraform.mikrotik.validate` | `terraform -chdir=generated/home-lab/terraform/mikrotik validate` | PASS | 0.49 |
| 10 | `terraform.mikrotik.plan` | `terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false -var-file D:\Workspaces\PycharmProjects\home-lab\generated\home-lab\terraform\mikrotik\terraform.tfvars.example` | PASS | 0.34 |
| 11 | `ansible.runtime` | `task ansible:runtime` | PASS | 0.31 |
| 12 | `ansible.syntax` | `wsl bash -lc cd '/mnt/d/Workspaces/PycharmProjects/home-lab' && export ANSIBLE_CONFIG='/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/ansible.cfg' && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/site.yml' --syntax-check && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/postgresql.yml' --syntax-check && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/redis.yml' --syntax-check && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/nextcloud.yml' --syntax-check && ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/monitoring.yml' --syntax-check` | PASS | 13.44 |
| 13 | `ansible.execute` | `wsl bash -lc cd '/mnt/d/Workspaces/PycharmProjects/home-lab' && ANSIBLE_CONFIG='/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/ansible.cfg' ansible-playbook -i '/mnt/d/Workspaces/PycharmProjects/home-lab/generated/home-lab/ansible/runtime/production/hosts.yml' '/mnt/d/Workspaces/PycharmProjects/home-lab/projects/home-lab/ansible/playbooks/site.yml' --check` | FAIL(4) | 25.74 |
| 14 | `acceptance.all` | `task acceptance:tests-all` | PASS | 18.77 |
| 15 | `cutover.readiness` | `task framework:cutover-readiness` | PASS | 338.26 |

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
