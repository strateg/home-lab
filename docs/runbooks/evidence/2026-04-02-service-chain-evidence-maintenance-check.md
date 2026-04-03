# 2026-04-02 Maintenance Check Evidence (MikroTik)

## Scope
- Validate bootstrap flow and RouterOS REST reachability.
- Validate Terraform deploy behavior after firewall template hardening.

## Executed Flow
1. `task framework:compile`
2. Bootstrap run (WSL): `deploy:init-node-run ... PHASE=bootstrap ... RESET=1 CONFIRM_RESET=1`
3. Bootstrap verify (WSL): `deploy:init-node-run ... VERIFY_ONLY=1`
4. Terraform (WSL): `init -> validate -> plan -> apply -> plan`

## Key Outcomes
- Bootstrap succeeded and imported `init-terraform.rsc`.
- Verify checks passed (`ssh_reachable`, `rest_api_reachable`).
- Terraform apply completed and final plan returned no changes.
- Post-check from router:
  - managed forward rules present;
  - WAN-scoped default deny rule present (`in-interface-list=WAN`, `connection-nat-state=!dstnat`);
  - `ping 1.1.1.1` successful;
  - REST HTTPS `:8443` reachable.

## Notes
- Firewall template updated to avoid unconditional `forward` drop and preserve LAN-to-WAN connectivity during deploy.
