# Service Chain Evidence (maintenance-check)

**Generated:** 2026-03-28 20:07:34Z
**Operator:** Dmitri
**Commit SHA:** 456b0de8bba23d950c4da1caff5c31161dc6af1a
**Project:** home-lab
**Environment:** production
**Mode:** maintenance-check
**Decision:** planned

Summary: executed=0/15, passed=0, failed=0, plan_only=true

| # | Step | Command | Result | Duration (s) |
|---|------|---------|--------|--------------|
| 1 | `framework.lock-refresh` | `task framework:lock-refresh` | not-run | - |
| 2 | `framework.strict` | `task framework:strict` | not-run | - |
| 3 | `validate.v5` | `task validate:v5` | not-run | - |
| 4 | `compile.generated` | `C:\Python313\python.exe topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated` | not-run | - |
| 5 | `terraform.proxmox.init` | `terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false` | not-run | - |
| 6 | `terraform.proxmox.validate` | `terraform -chdir=generated/home-lab/terraform/proxmox validate` | not-run | - |
| 7 | `terraform.proxmox.plan` | `terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false` | not-run | - |
| 8 | `terraform.mikrotik.init` | `terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false` | not-run | - |
| 9 | `terraform.mikrotik.validate` | `terraform -chdir=generated/home-lab/terraform/mikrotik validate` | not-run | - |
| 10 | `terraform.mikrotik.plan` | `terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false` | not-run | - |
| 11 | `ansible.runtime` | `task ansible:runtime` | not-run | - |
| 12 | `ansible.syntax` | `task ansible:syntax` | not-run | - |
| 13 | `ansible.execute` | `task ansible:check-site` | not-run | - |
| 14 | `acceptance.all` | `task acceptance:tests-all` | not-run | - |
| 15 | `cutover.readiness` | `task framework:cutover-readiness` | not-run | - |
