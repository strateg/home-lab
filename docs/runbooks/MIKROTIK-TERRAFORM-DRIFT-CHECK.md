# MikroTik Terraform Drift Check

## Purpose

Validate drift between generated Terraform (`generated/home-lab/terraform/mikrotik`) and live `rtr-mikrotik-chateau` runtime before apply.

## Preconditions

- Compile is green: `task validate:default`
- Terraform artifacts are fresh: `task build`
- MikroTik MCP access is configured:
  - `python3 scripts/orchestration/mcp/setup-mikrotik-mcp-codex.py --check`

## 1. Local Terraform Coverage Check

```bash
task terraform:validate-mikrotik
```

Expected domains in generated files:
- `interfaces.tf`: bridge + VLAN interfaces
- `addresses.tf`: bridge/VLAN gateway addresses
- `dhcp.tf`: LAN + VLAN DHCP sections
- `dns.tf`: DNS servers + gateway DNS records
- `firewall.tf`: filter + NAT resources

## 2. Live Snapshot (MCP)

Collect at least these command outputs from router:
- `/ip/address/print detail without-paging`
- `/interface/bridge/print detail without-paging`
- `/interface/vlan/print detail without-paging`
- `/ip/pool/print detail without-paging`
- `/ip/dhcp-server/print detail without-paging`
- `/ip/dhcp-server/network/print detail without-paging`
- `/ip/dns/print detail` (fallback: `/ip/dns/print` on older RouterOS builds)
- `/ip/route/print detail without-paging`
- `/ip/firewall/filter/print detail without-paging`
- `/ip/firewall/nat/print detail without-paging`

## 3. Drift Review Checklist

Compare live snapshot against generated Terraform by domain:
- L2: bridge/vlan resource set and names.
- L3 addresses: expected gateway addresses per managed network.
- DHCP: LAN server/network + additional VLAN DHCP segments.
- DNS: upstream servers and managed gateway records.
- Firewall filters: policy chain coverage and expected allow/deny semantics.
- NAT: masquerade and dst-nat runtime rules represented in Terraform.

## 4. Classify Drift

- `expected-preapply`: topology intentionally ahead of runtime (first rollout).
- `config-drift`: runtime changed outside topology, must be reconciled.
- `generator-gap`: topology exists but generator did not emit corresponding resource.

## 5. Rollout Guard

Before `terraform apply`:
1. No unresolved `generator-gap` items.
2. `config-drift` items are either merged into topology or explicitly rejected.
3. Apply only during maintenance window for firewall/NAT changes.

## Notes

- Last known successful live comparison flow was documented on 2026-04-08 during ADR0092-0094 hardening cycle.
- If router is unreachable from execution environment, run this runbook from an operator host with network access and attach evidence under `docs/runbooks/evidence/`.
