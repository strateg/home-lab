# Service Chain Evidence (maintenance-check)

**Generated:** 2026-03-28 19:47:24Z
**Operator:** Dmitri
**Commit SHA:** 2ba7d3b0e2bb4c870b5aec3234b0e62e61cdfe03
**Project:** home-lab
**Environment:** production
**Mode:** maintenance-check
**Decision:** planned

Summary: executed=0/14, passed=0, failed=0, plan_only=true

| # | Step | Command | Result | Duration (s) |
|---|------|---------|--------|--------------|
| 1 | `framework.strict` | `task framework:strict` | not-run | - |
| 2 | `validate.v5` | `task validate:v5` | not-run | - |
| 3 | `compile.generated` | `C:\Python313\python.exe topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode inject --artifacts-root generated` | not-run | - |
| 4 | `terraform.proxmox.init` | `terraform -chdir=generated/home-lab/terraform/proxmox init -backend=false -input=false` | not-run | - |
| 5 | `terraform.proxmox.validate` | `terraform -chdir=generated/home-lab/terraform/proxmox validate` | not-run | - |
| 6 | `terraform.proxmox.plan` | `terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false` | not-run | - |
| 7 | `terraform.mikrotik.init` | `terraform -chdir=generated/home-lab/terraform/mikrotik init -backend=false -input=false` | not-run | - |
| 8 | `terraform.mikrotik.validate` | `terraform -chdir=generated/home-lab/terraform/mikrotik validate` | not-run | - |
| 9 | `terraform.mikrotik.plan` | `terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false` | not-run | - |
| 10 | `ansible.runtime` | `task ansible:runtime-inject` | not-run | - |
| 11 | `ansible.syntax` | `task ansible:syntax` | not-run | - |
| 12 | `ansible.execute` | `task ansible:check-site-inject` | not-run | - |
| 13 | `acceptance.all` | `task acceptance:tests-all` | not-run | - |
| 14 | `cutover.readiness` | `task framework:cutover-readiness` | not-run | - |
