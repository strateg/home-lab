# MikroTik Drift Report (2026-04-08)

## Inputs

- Live snapshot: `docs/runbooks/evidence/2026-04-08-mikrotik-live-snapshot.json`
- Generated Terraform: `generated/home-lab/terraform/mikrotik/`
- Router identity: `rtr-mikrotik-chateau`

## Summary

Topology and generator are ahead of current device rollout.
No critical generator gaps were found for baseline domains already active on router.

## Classification

- `expected-preapply`:
  - VLAN interfaces expected by topology (`vlan30`, `vlan40`, `vlan50`, `vlan99`) are not yet present live.
  - VLAN gateway addresses and VLAN DHCP segments are generated but not yet present live.
  - Additional topology firewall policy rules are generated and not yet applied live.
- `config-drift`:
  - Live firewall still contains duplicated managed forward rules (historical defconf + manual duplicates).
  - Live DNS command compatibility issue observed when using `/ip/dns/print detail without-paging`.
- `generator-gap`:
  - None detected for checked domains (interfaces, addresses, DHCP, DNS, NAT, firewall).

## Domain Check

- Interfaces:
  - Live has `bridge` and `containers`, no VLAN interfaces.
  - Terraform includes `containers` bridge and managed VLAN interfaces.
- Addresses:
  - Live has `192.168.88.1/24`, `172.18.0.1/24`, dynamic WAN `192.168.0.17/24`.
  - Terraform includes LAN + containers + staged VLAN gateways.
- DHCP:
  - Live has `defconf` on `bridge` with `default-dhcp` pool.
  - Terraform includes LAN DHCP and staged VLAN DHCP servers.
- DNS:
  - Snapshot DNS command failed with parser error on `without-paging` variant.
  - Runbook updated to `print detail`/`print` fallback.
- NAT:
  - Live rules match topology baseline (`srcnat masquerade`, `dstnat 8080 -> 172.18.0.2:80`).
  - Terraform emits equivalent runtime NAT resources.
- Firewall:
  - Live includes defconf chain + duplicated managed rules.
  - Terraform emits topology-managed forward policy and NAT baseline.

## Decision

Proceed with controlled apply in maintenance window. Treat VLAN/DHCP/policy diffs as planned rollout (`expected-preapply`), not defects.
