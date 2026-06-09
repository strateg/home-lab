# Archived Manual Ansible Files

**Archived:** 2026-06-09
**Reason:** Replaced by generated artifacts per ADR 0104

## What Was Archived

These files contained manually duplicated data from topology and have been
replaced by generated equivalents from `AnsibleRoleGenerator` plugin.

### Phase 1 (2026-06-09): VPN Gateway

| Manual File | Generated Replacement |
|-------------|----------------------|
| `inventory/production/host_vars/vps-oracle-frankfurt.yml` | `generated/home-lab/ansible/inventory/production/host_vars/vps-oracle-frankfurt.yml` |
| `playbooks/vpn-gateway.yml` | `generated/home-lab/ansible/playbooks/vpn-gateway.yml` |

### Phase 2 (2026-06-09): Legacy Playbooks

| Manual File | Status |
|-------------|--------|
| `playbooks/common.yml` | Archived (pending generator) |
| `playbooks/monitoring.yml` | Archived (pending generator) |
| `playbooks/nextcloud.yml` | Archived (pending generator) |
| `playbooks/postgresql.yml` | Archived (pending generator) |
| `playbooks/redis.yml` | Archived (pending generator) |
| `playbooks/site.yml` | Archived (pending generator) |

## Why Archived (Not Deleted)

Preserved for reference and rollback if needed. The generated files are
functionally equivalent but derived from topology source of truth.

## See Also

- ADR 0104: Ansible Role Generation from Topology
- `adr/0104-analysis/IMPLEMENTATION-PLAN.md`
