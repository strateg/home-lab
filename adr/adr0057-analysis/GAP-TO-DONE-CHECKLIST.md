# ADR 0057 Gap-to-Done Checklist

Date: 2026-03-05
Scope: `adr/0057-migration-plan.md` -> section "Target End State"

## Target End State Checklist

- [x] 1. Supported control-node workflow can run `netinstall-cli` by target MAC
  - Closed by: `deploy/playbooks/bootstrap-netinstall.yml` + wired targets in `deploy/Makefile`.
  - Smoke: targets execute and fail on real prerequisite checks, not on missing files.

- [x] 2. Workflow performs hard prerequisites checks before install
  - Closed by: `deploy/phases/00-bootstrap-preflight.sh` + variable guards in `deploy/Makefile`.
  - Checks: `netinstall-cli`, bootstrap script path, install interface, client IP, RouterOS package.

- [x] 3. Bootstrap script remains minimal for Terraform handover only
  - Closed by: generator now renders `init-terraform-minimal.rsc.j2` by default.
  - Added: `mgmt_network` extraction and wiring into template context.

- [x] 4. Secret-bearing scripts are rendered only into ignored execution roots
  - Evidence: tracked templates remain secret-free; runtime roots are in `.gitignore` (`local/`, `.work/`).

- [x] 5. First post-bootstrap step is Terraform connectivity check/plan/apply
  - Closed by: `deploy/phases/00-bootstrap-postcheck.sh` bound to `make bootstrap-postcheck`.
  - Check: validates RouterOS API endpoint and Terraform credentials before moving to Terraform phase.

- [x] 6. Docs/operator entrypoints present Netinstall as default day-0 mechanism
  - Evidence: `deploy/phases/00-bootstrap.sh`, `docs/guides/MIKROTIK-TERRAFORM.md`, `docs/guides/DEPLOYMENT-STRATEGY.md`.

- [x] 7. Manual import path is clearly fallback, not primary
  - Evidence: explicit fallback wording in `deploy/phases/00-bootstrap.sh` and `docs/guides/MIKROTIK-TERRAFORM.md`.

## Immediate Closure Plan

1. Implement missing runtime files:
   - `deploy/phases/00-bootstrap-preflight.sh`
   - `deploy/phases/00-bootstrap-postcheck.sh`
   - `deploy/playbooks/bootstrap-netinstall.yml`
2. Harden `deploy/Makefile` variables and pass explicit params into playbook.
3. Make minimal template canonical in generator path and wire `mgmt_network`.
4. Run smoke checks for all three bootstrap targets and generator output profile.
