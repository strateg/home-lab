# ADR 0057 Hardware E2E Validation Checklist

Date: 2026-03-05
Scope: real-device validation for `netinstall-cli -> bootstrap -> Terraform handover`

## Test Context

- Router model / board: ____________________
- RouterOS package version: ____________________
- Package SHA256 used: ____________________
- Control node OS: ____________________
- Netinstall interface: ____________________
- Netinstall client IP: ____________________
- Target MAC: ____________________
- Restore path: `minimal` (default) / `backup` / `rsc`

## Preflight Gate

- [ ] `make bootstrap-preflight RESTORE_PATH=minimal ...` passes with no errors
- [ ] Preflight confirms bootstrap script path exists in `.work/native/bootstrap/rtr-mikrotik-chateau/`
- [ ] Preflight confirms `netinstall-cli` in `PATH`
- [ ] Preflight confirms package exists
- [ ] Preflight checksum verification passes (if SHA supplied)

Evidence:
- command: ______________________________________________
- output snippet: _______________________________________

## Netinstall Execution

- [ ] Router placed into Etherboot/Netinstall mode
- [ ] `make bootstrap-netinstall RESTORE_PATH=minimal ...` completed
- [ ] Target MAC in logs matches expected device
- [ ] Router reboots after install

Evidence:
- command: ______________________________________________
- output snippet: _______________________________________

## Post-Bootstrap Contract

- [ ] Router reachable on expected management IP
- [ ] `make bootstrap-postcheck MIKROTIK_MGMT_IP=... MIKROTIK_TERRAFORM_PASSWORD_FILE=...` passes
- [ ] REST API check returns HTTP 200 on `/rest/system/identity`

Evidence:
- command: ______________________________________________
- output snippet: _______________________________________

## Terraform Handover

- [ ] `.work/native/terraform/mikrotik/terraform.tfvars` present and valid
- [ ] `make bootstrap-terraform-check` passes (`plan-mikrotik`)
- [ ] No manual day-0 patching needed before first plan

Evidence:
- command: ______________________________________________
- output snippet: _______________________________________

## Contract Boundary Check

- [ ] Bootstrap script contains only day-0 handover logic
- [ ] No required day-2 config remains trapped in bootstrap
- [ ] Terraform remains source of truth for ongoing config

Reviewer notes:
- ________________________________________________________
- ________________________________________________________

## Result

- [ ] PASS: ADR 0057 Phase 4 exit gate met on hardware
- [ ] FAIL: gaps remain

Remaining gaps (if any):
1. ______________________________________________
2. ______________________________________________
3. ______________________________________________
