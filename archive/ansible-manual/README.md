# Archived Manual Ansible Files

**Archived:** 2026-06-09
**Reason:** Replaced by generated artifacts per ADR 0104

## What Was Archived

These files contained manually duplicated data from topology and have been
replaced by generated equivalents from `AnsibleRoleGenerator` plugin.

| Manual File | Generated Replacement |
|-------------|----------------------|
| `inventory/production/host_vars/vps-oracle-frankfurt.yml` | `generated/home-lab/ansible/inventory/production/host_vars/vps-oracle-frankfurt.yml` |
| `playbooks/vpn-gateway.yml` | `generated/home-lab/ansible/playbooks/vpn-gateway.yml` |

## Why Archived (Not Deleted)

Preserved for reference and rollback if needed. The generated files are
functionally equivalent but derived from topology source of truth.

## See Also

- ADR 0104: Ansible Role Generation from Topology
- `adr/0104-analysis/IMPLEMENTATION-PLAN.md`
