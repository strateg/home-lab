# Orange Pi 5: SSH Access Setup

**Device**: srv-orangepi5 (10.0.99.20)
**Status**: Requires bootstrap of automator user

## Architecture

Per ADR 0072 (Secrets) and ADR 0083 (Node Initialization):
- **Personal account**: `strateg` - used for initial bootstrap only
- **Automation account**: `automator` - used by Ansible/CI for all operations

## Current Configuration

From topology `projects/home-lab/topology/instances/devices/srv-orangepi5.yaml`:
- Management IP: 10.0.99.20 (VLAN 99)
- Interface: enx00e04c680347 (USB Ethernet adapter)

SSH config (`~/.ssh/config`):
```
# Bootstrap access (personal account)
Host orangepi5-bootstrap
    HostName 10.0.99.20
    User strateg
    IdentityFile ~/.ssh/id_ed25519

# Production access (automation account)
Host orangepi5 srv-orangepi5
    HostName 10.0.99.20
    User automator
    IdentityFile ~/.ssh/id_ed25519_automation
```

Files created:
- Ansible inventory: `projects/home-lab/ansible/inventory/production/local-hosts.yml`
- Secrets: `projects/home-lab/secrets/instances/srv-orangepi5.yaml` (SOPS encrypted)
- Bootstrap playbook: `projects/home-lab/ansible/playbooks/bootstrap-automator.yml`

## Bootstrap: Create automator User

### Step 1: Ensure strateg SSH access

First, add your SSH key to strateg user on orangepi5:

```bash
# Option A: If you know strateg password
ssh-copy-id -i ~/.ssh/id_ed25519.pub strateg@10.0.99.20

# Option B: Via console (HDMI + keyboard)
# Login as strateg, then:
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAde61C6ummeVTLbkbOo9h6zoHF3Hh1BDFj1XxpBg+K1 dprohhorov@gmail.com' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### Step 2: Run bootstrap script

```bash
# With SSH key authentication:
./scripts/bootstrap/orangepi5-automator.sh

# OR with password authentication:
./scripts/bootstrap/orangepi5-automator.sh --ask-pass
```

### Step 3: Verify automator access

```bash
# Test automator connection
ssh orangepi5

# Show Docker containers
ssh orangepi5 'docker ps'

# Test Ansible
cd projects/home-lab/ansible
ansible -i inventory/production srv-orangepi5 -m ping
```

## After Bootstrap

### Run Ansible playbooks

```bash
cd projects/home-lab/ansible

# Network configuration
ansible-playbook -i inventory/production playbooks/network-orangepi5.yml
```

### Docker management

```bash
ssh orangepi5 'docker ps'
ssh orangepi5 'docker compose -f /path/to/compose.yml up -d'
```

## Troubleshooting

### Permission Denied (automator)

Bootstrap not completed. Run:
```bash
./scripts/bootstrap/orangepi5-automator.sh --ask-pass
```

### Network Unreachable

```bash
ping 10.0.99.20

# Check MikroTik VLAN 99 routing
/ip route print where dst-address~"10.0.99"
```

## References

- ADR 0072: Unified Secrets Management with SOPS
- ADR 0083: Unified Node Initialization Contract
- Topology: `projects/home-lab/topology/instances/devices/srv-orangepi5.yaml`
- Install guide: `docs/guides/ORANGEPI5-ARMBIAN-SSD-INSTALL.md`
