---
@pack: mikrotik-terraform
@version: 1.0
@tokens: ~500
@adr: [0072, 0074, 0110]
---

# AI Rule Pack: MikroTik Terraform

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Import first | Always import existing resources before apply |
| REST API | Use port 80/443, not RouterOS API port 8728 |
| Credentials | Extract from SOPS secrets to temporary tfvars |
| ID mapping | Query REST API for `".id"` values before import |
| Verify | `terraform plan` must show "No changes" after import |

## Load When

- `generated/**/terraform/mikrotik/**`
- First-time MikroTik Terraform setup
- Terraform state drift or corruption
- Adding new MikroTik resources to existing router

## Import Workflow

| Step | Command | Purpose |
|------|---------|---------|
| 1. Credentials | `sops -d .../mikrotik.sops.yaml > /tmp/mikrotik.tfvars.json` | Extract secrets |
| 2. Test API | `curl -s -u user:pass "http://router/rest/system/identity"` | Verify connection |
| 3. Get IDs | `curl ... "/rest/ip/address" \| jq '.[] \| {".id", ...}'` | Map resources |
| 4. Import | `terraform import -var-file=... resource_name "*ID"` | Link state |
| 5. Verify | `terraform plan -var-file=...` | Must show no changes |
| 6. Apply | `terraform apply -var-file=...` | Safe to apply |

## Resource Import Order

| Priority | Resources |
|----------|-----------|
| 1 | VLAN interfaces, WireGuard interface |
| 2 | IP addresses, interface list members |
| 3 | DHCP pools, DHCP servers, DHCP networks |
| 4 | DNS records |
| 5 | Firewall address-lists |
| 6 | Firewall filter rules, mangle rules |
| 7 | Routing tables, routes |
| 8 | NAT rules |

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "already exists" on apply | Resource not imported | Import with correct `".id"` |
| "already have such entry" | Address swap conflict | Remove both from state, re-import with correct mapping |
| "unknown parameter vrf" | RouterOS version mismatch | Add attribute via REST API, then refresh |
| Connection refused 8728 | Wrong port (API vs REST) | Use port 80 for REST API |

## REST API Queries

```bash
# Get resource IDs
curl -s -u user:pass "http://router/rest/ip/address" | jq -c '.[] | {".id", address, interface}'
curl -s -u user:pass "http://router/rest/ip/firewall/address-list" | jq -c '.[] | {".id", list, address}'
curl -s -u user:pass "http://router/rest/interface/vlan" | jq -c '.[] | {".id", name, "vlan-id"}'
curl -s -u user:pass "http://router/rest/ip/firewall/filter" | jq -c '.[] | select(.comment) | {".id", chain, action, comment}'
curl -s -u user:pass "http://router/rest/ip/firewall/mangle" | jq -c '.[] | {".id", chain, action, comment}'
```

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Apply without import | "already exists" errors | Import first |
| Hardcode credentials | Security violation | Use SOPS + tfvars |
| Edit generated .tf files | Lost on regenerate | Edit topology sources |
| Skip plan verification | Unexpected changes | Always verify "No changes" |

## Validation

```bash
terraform plan -var-file=/tmp/mikrotik.tfvars.json   # Must show "No changes"
terraform state list | wc -l                          # Verify resource count
```
