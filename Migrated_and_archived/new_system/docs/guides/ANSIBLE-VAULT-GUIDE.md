# Ansible Vault Guide

Complete guide to managing secrets with Ansible Vault in the home lab infrastructure.

---

## Table of Contents

1. [Overview](#overview)
2. [Initial Setup](#initial-setup)
3. [Creating Encrypted Secrets](#creating-encrypted-secrets)
4. [Working with Vault](#working-with-vault)
5. [Using Vault in Playbooks](#using-vault-in-playbooks)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)
8. [Security Considerations](#security-considerations)

---

## Overview

Ansible Vault encrypts sensitive data (passwords, API tokens, SSH keys) while keeping the rest of your infrastructure code in plain text.

### What's Encrypted

All secrets are stored in `ansible/group_vars/all/vault.yml` (encrypted):

- **Proxmox**: API tokens, root password
- **PostgreSQL**: Superuser password, app passwords
- **Nextcloud**: Admin password, database password, secrets
- **Redis**: requirepass password
- **OPNsense**: Root password, API credentials
- **VPN**: WireGuard/AmneziaWG private keys
- **Email**: SMTP credentials
- **Backups**: Encryption passwords
- **SSL/TLS**: Private keys (if stored in vault)

### What's NOT Encrypted

Non-sensitive configuration in `ansible/group_vars/all/vars.yml`:

- IP addresses
- Port numbers
- Package names
- Service configurations (without credentials)

---

## Initial Setup

### Step 1: Create Vault Password

```bash
cd ansible

# Generate strong vault password
VAULT_PASSWORD=$(openssl rand -base64 32)
echo "$VAULT_PASSWORD" > .vault_pass
chmod 600 .vault_pass

# IMPORTANT: Back up this password securely!
# Store in password manager (1Password, Bitwarden, etc.)
echo "Vault password: $VAULT_PASSWORD"
```

**⚠️ WARNING**: If you lose `.vault_pass`, you cannot decrypt vault.yml!

### Step 2: Create Vault File

```bash
# Copy example template
cp group_vars/all/vault.yml.example group_vars/all/vault.yml

# Edit with your secrets (use strong passwords!)
vim group_vars/all/vault.yml
```

### Step 3: Encrypt Vault

```bash
# Encrypt vault.yml with AES256
ansible-vault encrypt group_vars/all/vault.yml

# Verify encryption
file group_vars/all/vault.yml
# Output: group_vars/all/vault.yml: ASCII text
head -1 group_vars/all/vault.yml
# Output: $ANSIBLE_VAULT;1.1;AES256
```

### Step 4: Test Ansible Access

```bash
# Test that Ansible can decrypt vault
ansible all -m ping -i inventory/production/hosts.yml

# View encrypted content (requires vault password)
ansible-vault view group_vars/all/vault.yml
```

---

## Creating Encrypted Secrets

### Generate Strong Passwords

```bash
# General passwords (32 characters, base64)
openssl rand -base64 32

# Alphanumeric only (64 characters)
pwgen -s 64 1

# Hex passwords (for API tokens)
openssl rand -hex 32

# WireGuard keys
wg genkey

# PostgreSQL password (special chars safe for SQL)
pwgen -s -y -r "'\"\`" 32 1
```

### Recommended Password Strengths

| Service | Length | Complexity | Example Command |
|---------|--------|-----------|-----------------|
| Proxmox root | 32+ | High | `pwgen -s -y 32 1` |
| PostgreSQL | 32+ | High | `openssl rand -base64 32` |
| Nextcloud admin | 24+ | High | `pwgen -s -y 24 1` |
| Redis | 64+ | Very High | `openssl rand -base64 64` |
| API tokens | 64+ | Very High | `openssl rand -hex 32` |
| WireGuard keys | - | Use `wg genkey` | `wg genkey` |

---

## Working with Vault

### View Vault Contents

```bash
# View encrypted vault
ansible-vault view group_vars/all/vault.yml

# View with custom password file
ansible-vault view group_vars/all/vault.yml --vault-password-file=.vault_pass_backup
```

### Edit Vault

```bash
# Edit vault (decrypts, opens editor, re-encrypts on save)
ansible-vault edit group_vars/all/vault.yml

# Edit with specific editor
EDITOR=nano ansible-vault edit group_vars/all/vault.yml
```

### Change Vault Password

```bash
# Change vault password (re-encrypts with new password)
ansible-vault rekey group_vars/all/vault.yml

# Provide old and new passwords
# Old password: (from .vault_pass)
# New password: (enter new password)
# Confirm: (confirm new password)

# Update .vault_pass file
echo "NEW_PASSWORD" > .vault_pass
chmod 600 .vault_pass
```

### Encrypt/Decrypt Files

```bash
# Encrypt an existing file
ansible-vault encrypt group_vars/all/vault.yml

# Decrypt to plain text (DANGEROUS - use temporarily only)
ansible-vault decrypt group_vars/all/vault.yml

# View decrypted content without decrypting file
ansible-vault view group_vars/all/vault.yml

# Encrypt string for inline use
ansible-vault encrypt_string 'my_secret_password' --name 'vault_db_password'
```

---

## Using Vault in Playbooks

### Reference Vault Variables

Vault variables are automatically loaded from `group_vars/all/vault.yml`.

**Example Playbook** (`playbooks/postgresql.yml`):

```yaml
---
- name: Configure PostgreSQL
  hosts: databases
  become: true

  tasks:
    - name: Set PostgreSQL password
      postgresql_user:
        name: postgres
        password: "{{ vault_postgresql_superuser_password }}"  # From vault.yml
        encrypted: true

    - name: Create application user
      postgresql_user:
        name: app
        password: "{{ vault_postgresql_app_password }}"  # From vault.yml
        db: homelab
```

### Using Vault with Templates

**Example Template** (`templates/nextcloud.config.php.j2`):

```php
<?php
$CONFIG = array (
  'instanceid' => '{{ vault_nextcloud_instanceid }}',
  'secret' => '{{ vault_nextcloud_secret }}',
  'dbuser' => 'nextcloud',
  'dbpassword' => '{{ vault_nextcloud_db_password }}',  // From vault
  'dbhost' => '{{ hostvars["postgresql-db"].ansible_host }}',
);
```

### Vault with Conditionals

```yaml
- name: Configure SMTP notifications
  template:
    src: smtp.conf.j2
    dest: /etc/smtp.conf
  when: email_notifications_enabled | default(false)
  vars:
    smtp_password: "{{ vault_smtp_password }}"
```

---

## Best Practices

### 1. **Separate Sensitive and Non-Sensitive Data**

```
group_vars/all/
├── vars.yml          # ✅ Public config (commit to git)
└── vault.yml         # 🔒 Secrets (NEVER commit unencrypted)
```

### 2. **Use Meaningful Variable Names**

```yaml
# ✅ Good - clear and namespaced
vault_postgresql_app_password: "xxx"
vault_nextcloud_admin_password: "xxx"

# ❌ Bad - ambiguous
password: "xxx"
db_pass: "xxx"
```

### 3. **Always Prefix Vault Variables**

Use `vault_` prefix to easily identify encrypted variables:

```yaml
# vars.yml (public)
postgresql_max_connections: 50

# vault.yml (encrypted)
vault_postgresql_superuser_password: "encrypted_secret"
```

### 4. **Document Vault Variables**

Keep `vault.yml.example` up-to-date with all vault variables (without real values):

```bash
# Update example when adding new secrets
vim group_vars/all/vault.yml.example
git add group_vars/all/vault.yml.example
git commit -m "docs: add new vault variable example"
```

### 5. **Never Commit Unencrypted Secrets**

```bash
# ✅ Good - encrypted vault committed
git add group_vars/all/vault.yml
git status
# Output: modified:   group_vars/all/vault.yml (encrypted)

# ❌ DANGER - check before commit!
head -1 group_vars/all/vault.yml
# Must show: $ANSIBLE_VAULT;1.1;AES256
```

### 6. **Use Strong Vault Passwords**

```bash
# ✅ Good - 32+ character random password
openssl rand -base64 32

# ❌ Bad - weak password
echo "password123" > .vault_pass  # DON'T DO THIS!
```

### 7. **Backup Vault Password**

Store vault password in multiple secure locations:

- **Password manager** (1Password, Bitwarden)
- **Encrypted USB drive** (offline backup)
- **Paper backup** (in safe/vault)
- **Shared team secret manager** (if working in team)

### 8. **Use Different Passwords Per Environment**

For multi-environment setups:

```bash
# Production vault
.vault_pass_prod

# Development vault
.vault_pass_dev

# ansible.cfg
vault_identity_list = dev@.vault_pass_dev, prod@.vault_pass_prod
```

---

## Troubleshooting

### Error: "Vault password file not found"

```bash
# Check vault_password_file in ansible.cfg
grep vault_password_file ansible.cfg

# Verify .vault_pass exists
ls -la .vault_pass

# Create if missing
echo "YOUR_VAULT_PASSWORD" > .vault_pass
chmod 600 .vault_pass
```

### Error: "Decryption failed"

```bash
# Wrong password in .vault_pass
# Fix: Get correct password from backup

# Vault file corrupted
# Fix: Restore from git history
git checkout HEAD -- group_vars/all/vault.yml
```

### Error: "Unable to decrypt vault"

```bash
# Check file is encrypted
head -1 group_vars/all/vault.yml
# Should show: $ANSIBLE_VAULT;1.1;AES256

# If not encrypted, encrypt it
ansible-vault encrypt group_vars/all/vault.yml
```

### View Ansible Vault Debug Info

```bash
# Enable verbose output
ansible-playbook -vvv playbooks/site.yml

# Check which vault files are loaded
ANSIBLE_DEBUG=1 ansible all -m ping
```

---

## Security Considerations

### 1. **File Permissions**

```bash
# Vault password file - read-only by owner
chmod 600 .vault_pass

# Vault file - readable by owner and group
chmod 640 group_vars/all/vault.yml

# SSH private keys (if in vault)
chmod 600 ~/.ssh/id_ed25519
```

### 2. **Git Hooks (Pre-commit Protection)**

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Prevent committing unencrypted vault files

if git diff --cached --name-only | grep -q "vault.yml$"; then
    if ! head -1 "$(git diff --cached --name-only | grep vault.yml)" | grep -q "ANSIBLE_VAULT"; then
        echo "ERROR: vault.yml is not encrypted!"
        echo "Run: ansible-vault encrypt group_vars/all/vault.yml"
        exit 1
    fi
fi
```

```bash
chmod +x .git/hooks/pre-commit
```

### 3. **Vault Password Rotation**

Rotate vault password every 90 days:

```bash
# 1. Generate new password
NEW_PASS=$(openssl rand -base64 32)

# 2. Rekey vault
ansible-vault rekey group_vars/all/vault.yml
# Old password: (current)
# New password: $NEW_PASS

# 3. Update .vault_pass
echo "$NEW_PASS" > .vault_pass
chmod 600 .vault_pass

# 4. Update backups (password manager, USB, paper)
```

### 4. **Limit Vault Access**

```bash
# Only specific users can decrypt vault
chown root:ansible-admins group_vars/all/vault.yml
chmod 640 group_vars/all/vault.yml

# Vault password file - owner only
chown root:root .vault_pass
chmod 600 .vault_pass
```

### 5. **Audit Vault Access**

```bash
# Log vault decrypt operations
# Add to ansible.cfg:
[defaults]
log_path = /var/log/ansible/vault-access.log

# Monitor logs
tail -f /var/log/ansible/vault-access.log | grep vault
```

---

## Quick Reference

### Common Commands

```bash
# Create new encrypted file
ansible-vault create group_vars/all/vault.yml

# Encrypt existing file
ansible-vault encrypt group_vars/all/vault.yml

# Edit encrypted file
ansible-vault edit group_vars/all/vault.yml

# View encrypted file
ansible-vault view group_vars/all/vault.yml

# Decrypt file (CAUTION)
ansible-vault decrypt group_vars/all/vault.yml

# Change vault password
ansible-vault rekey group_vars/all/vault.yml

# Encrypt string
ansible-vault encrypt_string 'secret' --name 'vault_var'

# Run playbook with vault
ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml

# Run with different vault password
ansible-playbook --vault-password-file=.vault_pass_prod playbooks/site.yml
```

### Vault Password File Locations

```
ansible/
├── .vault_pass              # Main vault password (in .gitignore)
├── .vault_pass.backup       # Backup (in .gitignore)
├── group_vars/all/
│   ├── vars.yml             # Public variables (commit to git)
│   ├── vault.yml            # Encrypted secrets (commit to git)
│   └── vault.yml.example    # Template (commit to git)
```

---

## Related Documentation

- [Ansible Vault Official Docs](https://docs.ansible.com/ansible/latest/user_guide/vault.html)
- [topology.yaml](../topology.yaml) - Infrastructure source of truth
- [CLAUDE.md](../../CLAUDE.md) - Project architecture guide

---

**Last Updated**: 2025-10-17
**Version**: 2.1.0
**Security Level**: CONFIDENTIAL
