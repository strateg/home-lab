# Home-Lab Ansible Service Layer

This directory contains project-scoped Ansible assets integrated with v5 inventory/runtime flow.

## Structure

```
ansible/
├── playbooks/           # Service deployment playbooks
│   ├── site.yml
│   ├── vpn-gateway.yml  # VPS WireGuard gateway configuration
│   └── ...
├── roles/               # Role implementations
│   ├── common/
│   ├── wireguard_gateway/  # WireGuard VPN gateway role
│   └── ...
├── inventory/           # Static inventory for cloud hosts
│   └── production/
│       ├── hosts.yml
│       └── host_vars/
├── group_vars/all/      # Default and secret-example variables
├── inventory-overrides/ # Operator overrides for generated inventory
└── scripts/             # Helper scripts
    └── get-vps-ip.sh    # Dynamic VPS IP discovery
```

## Runtime Inventory

Inventory is generated into:

- `generated/home-lab/ansible/inventory/production/hosts.yml`
- `generated/home-lab/ansible/runtime/production/hosts.yml` (after runtime assembly)

## Quick Commands

```powershell
task ansible:install-collections
task ansible:runtime
task ansible:runtime-inject
task ansible:syntax
task ansible:check-site
task ansible:check-site-inject
```

To enable monitoring stack container apply:

```powershell
ansible-playbook -i generated/home-lab/ansible/runtime/production/hosts.yml projects/home-lab/ansible/playbooks/monitoring.yml -e monitoring_apply=true
```

## VPN Gateway Configuration

Configure OCI VPS as WireGuard gateway for VPN-Germany VLAN:

```bash
# Via WireGuard tunnel (when tunnel is up)
ansible-playbook -i inventory/production/hosts.yml playbooks/vpn-gateway.yml

# Via public IP (when tunnel is down)
export VPS_ORACLE_FRANKFURT_IP=$(./scripts/get-vps-ip.sh)
ansible-playbook -i inventory/production/hosts.yml playbooks/vpn-gateway.yml \
  -e "ansible_host=$VPS_ORACLE_FRANKFURT_IP"
```

See [VPN Gateway Ansible Guide](../../docs/guides/VPN-GATEWAY-ANSIBLE.md) for full documentation.

## Runtime Note

If `ansible-playbook` fails on Windows with `OSError: [WinError 87]`, run the playbook lane from Linux/WSL where `ansible-core` CLI is fully supported.

## Secrets Injection

For maintenance windows where decrypted service secrets are required at runtime:

1. Unlock secrets (`scripts/secrets/unlock-secrets.*`) so `sops -d` can read `projects/home-lab/secrets/ansible/vault.yaml`.
2. Run `task ansible:runtime-inject` (or `task ansible:check-site-inject`).
3. Runtime writes decrypted vars to:
   - `generated/home-lab/ansible/runtime/production/group_vars/all/99-secrets.runtime.yml`

This file is runtime-only and regenerated on each run.
