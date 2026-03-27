# Home-Lab Ansible Service Layer

This directory contains project-scoped Ansible assets integrated with v5 inventory/runtime flow.

## Structure

- `playbooks/` - service deployment playbooks (`site.yml`, `postgresql.yml`, `redis.yml`, `nextcloud.yml`, `monitoring.yml`)
- `roles/` - role implementations (`common`, `postgresql`, `redis`, `nextcloud`, `monitoring_stack`)
- `group_vars/all/` - default and secret-example variables
- `inventory-overrides/` - operator overrides merged into generated runtime inventory

## Runtime Inventory

Inventory is generated into:

- `generated/home-lab/ansible/inventory/production/hosts.yml`
- `generated/home-lab/ansible/runtime/production/hosts.yml` (after runtime assembly)

## Quick Commands

```powershell
task ansible:install-collections
task ansible:runtime
task ansible:syntax
task ansible:check-site
```

To enable monitoring stack container apply:

```powershell
ansible-playbook -i generated/home-lab/ansible/runtime/production/hosts.yml projects/home-lab/ansible/playbooks/monitoring.yml -e monitoring_apply=true
```

## Runtime Note

If `ansible-playbook` fails on Windows with `OSError: [WinError 87]`, run the playbook lane from Linux/WSL where `ansible-core` CLI is fully supported.
