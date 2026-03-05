# NetInstall CLI Quick Reference

## Automatic Provisioning - 3 Ways

### ✅ Recommended: Bash Script (Fastest)

```bash
cd deploy
make setup-control-node
```

What it does:
- Auto-detects your OS (Linux, macOS, Windows WSL2)
- Downloads & installs `netinstall-cli` from MikroTik
- Installs: `python3`, `curl`, `wget`, `git`, `terraform`, `ansible`
- Shows verification summary

---

### Ansible Playbook (More Control)

```bash
cd deploy
make setup-control-node-ansible
```

Or directly:
```bash
ansible-playbook deploy/playbooks/provision-control-node.yml
```

---

### Manual Download (If Needed)

```bash
# Download
wget https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz

# Extract
tar xzf netinstall-7.20.8.tar.gz

# Install
sudo mv netinstall /usr/local/bin/netinstall-cli
sudo chmod +x /usr/local/bin/netinstall-cli

# Verify
netinstall-cli --version
```

---

## Full Bootstrap Flow

```bash
# Step 1: Install netinstall-cli and dependencies
cd deploy
make setup-control-node

# Step 2: Validate all prerequisites
make bootstrap-preflight RESTORE_PATH=minimal

# Step 3: Execute MikroTik bootstrap
make bootstrap-netinstall \
  RESTORE_PATH=minimal \
  MIKROTIK_BOOTSTRAP_MAC="00:11:22:33:44:55"

# Step 4: Verify bootstrap success
make bootstrap-postcheck \
  MIKROTIK_MGMT_IP="192.168.88.1" \
  MIKROTIK_TERRAFORM_PASSWORD_FILE="local/terraform/mikrotik/password.txt" # pragma: allowlist secret
make bootstrap-terraform-check
```

---

## Bootstrap Paths

### Path A: Minimal (Clean Install)
Best for fresh installations, no existing config
```bash
make bootstrap-netinstall RESTORE_PATH=minimal \
  MIKROTIK_BOOTSTRAP_MAC="<mac-address>"
```

### Path B: Backup Restoration
Restore from previous backup + apply overrides
```bash
make bootstrap-netinstall RESTORE_PATH=backup \
  ALLOW_NON_MINIMAL_RESTORE=true \
  MIKROTIK_BOOTSTRAP_MAC="<mac-address>"
```

### Path C: Safe Exported Config
Import full exported configuration
```bash
make bootstrap-netinstall RESTORE_PATH=rsc \
  ALLOW_NON_MINIMAL_RESTORE=true \
  MIKROTIK_BOOTSTRAP_MAC="<mac-address>"
```

---

## Troubleshooting

### netinstall-cli not in PATH
```bash
# Find it
which netinstall-cli

# Fix PATH or create symlink
sudo ln -s /path/to/netinstall /usr/local/bin/netinstall-cli
```

### Wrong platform/architecture
```bash
# Check your system
uname -m  # Output: x86_64, arm64, etc.

# Download correct version from:
# https://download.mikrotik.com/routeros/7.20.8/
```

### Network timeout during download
```bash
# Retry with wget options
wget --tries=5 --waitretry=10 \
  https://download.mikrotik.com/routeros/7.20.8/netinstall-7.20.8.tar.gz
```

### Permission denied
```bash
# Add execute permission
chmod +x /usr/local/bin/netinstall-cli
```

---

## Environment Variables

Set in `.env.local` or pass as `make` variables:

```bash
# RouterOS version to download
NETINSTALL_VERSION=7.20.8

# Installation location
INSTALL_PREFIX=/usr/local/bin

# RouterOS package path (used by bootstrap)
ROUTEROS_PACKAGE_PATH=/srv/routeros/routeros-7.20.8-arm64.npk

# Netinstall interface (control node network interface)
NETINSTALL_INTERFACE=eth0

# Client IP during netinstall
NETINSTALL_CLIENT_IP=192.168.88.3
```

---

## Useful Make Targets

```bash
cd deploy

# Show all available targets
make help

# Show bootstrap instructions
make bootstrap-info

# Setup control node (ONE COMMAND)
make setup-control-node

# Run all bootstrap checks and execution
make bootstrap-preflight RESTORE_PATH=minimal
make bootstrap-netinstall RESTORE_PATH=minimal MIKROTIK_BOOTSTRAP_MAC=<mac>
make bootstrap-postcheck MIKROTIK_MGMT_IP=192.168.88.1 MIKROTIK_TERRAFORM_PASSWORD_FILE=local/terraform/mikrotik/password.txt
make bootstrap-terraform-check

# Verify status
make status
```

---

## Files Modified

Your project now has these new files:

### Setup Script
`deploy/phases/00-bootstrap-setup-control-node.sh`
- Auto-detects OS and installs all dependencies
- Downloads netinstall-cli from MikroTik if not in package manager
- Multi-platform support

### Ansible Playbook
`deploy/playbooks/provision-control-node.yml`
- Alternative to bash script
- Good for CI/CD integration
- Supports Debian, RedHat, macOS

### Documentation
`docs/NETINSTALL-CLI-PROVISIONING.md`
- Comprehensive provisioning guide
- Multiple installation methods
- Troubleshooting section

### Makefile Updates
`deploy/Makefile`
- `setup-control-node` - Run bash setup script
- `setup-control-node-ansible` - Run Ansible playbook
- Updated `bootstrap-info` with setup instructions

---

## One-Liner Installation

```bash
cd deploy && make setup-control-node && make bootstrap-info
```

This:
1. Installs netinstall-cli and all dependencies
2. Shows detailed bootstrap instructions

---

## Next Steps

1. **Install netinstall-cli:**
   ```bash
   cd deploy
   make setup-control-node
   ```

2. **Check Prerequisites:**
   ```bash
   make bootstrap-preflight RESTORE_PATH=minimal
   ```

3. **Put MikroTik in Netinstall Mode**
   - Hold reset button during power-up, or
   - Use existing bootloader menu

4. **Run Bootstrap:**
   ```bash
   make bootstrap-netinstall \
     RESTORE_PATH=minimal \
     MIKROTIK_BOOTSTRAP_MAC="<router-mac-address>"
   ```

5. **Verify Success:**
   ```bash
   make bootstrap-postcheck \
     MIKROTIK_MGMT_IP="192.168.88.1" \
     MIKROTIK_TERRAFORM_PASSWORD_FILE="local/terraform/mikrotik/password.txt" # pragma: allowlist secret
   make bootstrap-terraform-check
   ```

---

## Support

- Full guide: `docs/NETINSTALL-CLI-PROVISIONING.md`
- ADR 0057: `adr/0057-*` (MikroTik Netinstall Bootstrap)
- Bootstrap playbook: `deploy/playbooks/bootstrap-netinstall.yml`
- Preflight checks: `deploy/phases/00-bootstrap-preflight.sh`
