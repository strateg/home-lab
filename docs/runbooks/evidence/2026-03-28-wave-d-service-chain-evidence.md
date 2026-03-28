# Wave D Service-Chain Evidence (2026-03-28)

**Date:** 2026-03-28
**Scope:** Wave D / Phase 12 service deployment chain validation evidence
**Commit Context:** post `c59e768` (runbooks + service playbook integration)

---

## 1. Executed Gates

1. `task framework:strict` -> PASS
2. `task validate:v5` -> PASS
3. `python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated` -> PASS
4. `terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false` -> PASS
5. `terraform -chdir=generated/home-lab/terraform/proxmox validate` -> PASS
6. `terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false` -> PASS
7. `terraform -chdir=generated/home-lab/terraform/mikrotik validate` -> PASS
8. `task ansible:runtime` -> PASS
9. WSL syntax lane (all integrated playbooks) -> PASS:
   - `postgresql.yml`
   - `redis.yml`
   - `nextcloud.yml`
   - `monitoring.yml`
   - `site.yml`
10. `task framework:cutover-readiness-quick` -> PASS
11. `task framework:cutover-readiness` -> PASS

---

## 2. Controlled No-Go Findings (Expected in this environment)

1. `terraform plan` for Proxmox fails without runtime secrets/vars:
   - missing `proxmox_api_url`
   - missing `proxmox_api_token`
2. `terraform plan` for MikroTik fails without runtime secrets/vars:
   - missing `mikrotik_host`
   - missing `mikrotik_password`
3. Native Windows `ansible-playbook` CLI is not usable in current shell (`WinError 87`); syntax validation executed via WSL Ansible runtime.

These are environment/credential constraints, not topology/model contract failures.

---

## 3. Closure Status

1. Dry-run service chain evidence is recorded.
2. Full execution closure still requires maintenance-window run with:
   - injected secret var-files for Terraform plan/apply,
   - reachable target hosts for Ansible `--check`/apply,
   - operational change record with go/no-go decision.
