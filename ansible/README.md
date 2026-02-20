# Ansible Configuration

Ansible automation for home lab infrastructure.

---

## Quick Start

### 1. Initialize Ansible Vault

```bash
# First time setup
./vault-helper.sh init

# Edit vault with real secrets
./vault-helper.sh edit
```

### 2. Test Connectivity

```bash
# Ping all hosts
ansible all -m ping -i inventory/production/hosts.yml

# Check specific group
ansible lxc_containers -m ping -i inventory/production/hosts.yml
```

### 3. Run Playbooks

```bash
# Run all playbooks
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml

# Run specific playbook
ansible-playbook -i inventory/production/hosts.yml playbooks/postgresql.yml

# Dry run (check mode)
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --check

# Verbose output
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml -vvv
```

---

## Directory Structure

```
ansible/
├── ansible.cfg                    # Ansible configuration
├── vault-helper.sh                # Vault management script
├── requirements.yml               # External roles/collections
│
├── inventory/
│   └── production/
│       ├── hosts.yml              # Generated from topology.yaml
│       ├── group_vars/
│       │   └── all.yml            # Generated group variables
│       └── host_vars/             # Generated host-specific variables
│           ├── postgresql-db.yml
│           ├── redis-cache.yml
│           └── nextcloud.yml
│
├── group_vars/
│   └── all/
│       ├── vars.yml               # Public variables (safe to commit)
│       ├── vault.yml              # Encrypted secrets (create this!)
│       └── vault.yml.example      # Template
│
├── playbooks/                     # Ansible playbooks
│   ├── site.yml                   # Main playbook (runs all)
│   ├── common.yml                 # Common configuration
│   ├── postgresql.yml             # PostgreSQL setup
│   ├── redis.yml                  # Redis setup
│   └── nextcloud.yml              # Nextcloud setup
│
└── roles/                         # Ansible roles
    ├── common/                    # Common OS configuration
    ├── postgresql/                # PostgreSQL role
    ├── redis/                     # Redis role
    └── nextcloud/                 # Nextcloud role
```

---

## Ansible Vault

### Commands

```bash
# Initialize vault (first time)
./vault-helper.sh init

# Edit encrypted vault
./vault-helper.sh edit

# View vault contents
./vault-helper.sh view

# Validate vault
./vault-helper.sh validate

# Generate strong password
./vault-helper.sh generate-pass

# Backup vault
./vault-helper.sh backup

# Show vault status
./vault-helper.sh status
```

### Available Vault Variables

See `group_vars/all/vault.yml.example` for complete list:

- `vault_proxmox_api_token` - Proxmox API token
- `vault_postgresql_app_password` - PostgreSQL app password
- `vault_nextcloud_admin_password` - Nextcloud admin password
- `vault_redis_password` - Redis password
- `vault_opnsense_root_password` - OPNsense root password
- And more...

**Full documentation**: [docs/ANSIBLE-VAULT-GUIDE.md](../docs/ANSIBLE-VAULT-GUIDE.md)

---

## Common Tasks

### Install/Update Roles

```bash
# Install required roles and collections
ansible-galaxy install -r requirements.yml

# Update roles
ansible-galaxy install -r requirements.yml --force
```

### Run Ad-Hoc Commands

```bash
# Check disk space
ansible all -m shell -a "df -h" -i inventory/production/hosts.yml

# Restart service
ansible postgresql-db -m systemd -a "name=postgresql state=restarted" -i inventory/production/hosts.yml

# Update packages
ansible all -m apt -a "upgrade=dist update_cache=yes" -i inventory/production/hosts.yml
```

### Limit Execution

```bash
# Run only on specific host
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --limit postgresql-db

# Run only on specific group
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --limit lxc_containers

# Run on multiple hosts
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --limit "postgresql-db,redis-cache"
```

### Tags

```bash
# List available tags
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --list-tags

# Run specific tags
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --tags "setup,config"

# Skip specific tags
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --skip-tags "backup"
```

---

## Inventory

### Generated from topology.yaml

Inventory files are **auto-generated** from `topology.yaml`:

```bash
# Regenerate inventory
cd ..
python3 topology-tools/generate-ansible-inventory.py
```

### Host Groups

- `lxc_containers` - All LXC containers
- `virtual_machines` - All VMs
- `databases` - Database servers (PostgreSQL)
- `cache_servers` - Cache servers (Redis)
- `web_applications` - Web apps (Nextcloud)
- Trust zones: `internal_zone`, `management_zone`, etc.

### Host Variables

Each host has auto-generated variables:
- `ansible_host` - IP address
- `ansible_user` - SSH user
- `vmid` - Proxmox VM/LXC ID
- `trust_zone` - Security zone
- `playbook` - Associated playbook

---

## Troubleshooting

### Vault Issues

```bash
# Check vault status
./vault-helper.sh status

# Validate vault encryption
./vault-helper.sh validate

# View vault password file
cat .vault_pass  # Should be 32+ character random string
```

### Connection Issues

```bash
# Test SSH connectivity
ssh -i ~/.ssh/id_ed25519 postgres@10.0.30.10

# Check host key
ssh-keyscan -H 10.0.30.10

# Verbose Ansible connection
ansible postgresql-db -m ping -i inventory/production/hosts.yml -vvv
```

### Playbook Errors

```bash
# Syntax check
ansible-playbook playbooks/site.yml --syntax-check

# Dry run
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --check

# Step-by-step execution
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml --step
```

---

## Best Practices

### 1. Always Use Vault for Secrets

```yaml
# ✅ Good - secret in vault
password: "{{ vault_postgresql_password }}"

# ❌ Bad - hardcoded secret
password: "my_secret_password"
```

### 2. Use Inventory Groups

```yaml
# ✅ Good - use groups
- hosts: databases
  tasks: ...

# ❌ Bad - hardcode hosts
- hosts: postgresql-db
  tasks: ...
```

### 3. Idempotency

```yaml
# ✅ Good - idempotent
- name: Ensure PostgreSQL is started
  systemd:
    name: postgresql
    state: started

# ❌ Bad - not idempotent
- name: Start PostgreSQL
  shell: service postgresql start
```

### 4. Use Tags

```yaml
- name: Install packages
  apt:
    name: "{{ item }}"
  tags: [setup, packages]

- name: Configure service
  template:
    src: config.j2
    dest: /etc/config
  tags: [config]
```

### 5. Check Mode Support

```yaml
- name: Create directory
  file:
    path: /etc/myapp
    state: directory
  check_mode: yes  # Safe in --check mode
```

---

## Configuration

### ansible.cfg

Key settings:
- **Inventory**: `./inventory/production/hosts.yml`
- **Vault password**: `.vault_pass`
- **SSH**: `StrictHostKeyChecking=no` (lab environment)
- **Callbacks**: `profile_tasks`, `timer`
- **Forks**: 10 (parallel execution)

### Environment Variables

```bash
# Use custom inventory
export ANSIBLE_INVENTORY=./inventory/development/hosts.yml

# Use different vault password
export ANSIBLE_VAULT_PASSWORD_FILE=.vault_pass_dev

# Enable debug
export ANSIBLE_DEBUG=1

# Custom Python interpreter
export ANSIBLE_PYTHON_INTERPRETER=/usr/bin/python3
```

---

## Related Documentation

- **Vault Guide**: [docs/ANSIBLE-VAULT-GUIDE.md](../docs/ANSIBLE-VAULT-GUIDE.md)
- **Topology**: [topology.yaml](../topology.yaml)
- **Project Guide**: [CLAUDE.md](../../CLAUDE.md)

---

## Support

For issues or questions:
- Check logs: `cat ansible.log`
- Verbose mode: `-vvv`
- Dry run: `--check`
- Documentation: `docs/`

---

**Last Updated**: 2025-10-17
**Ansible Version**: 2.14+
