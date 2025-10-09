# Ansible Role: Proxmox

Configures Proxmox VE 9 for home lab infrastructure on Dell XPS L701X.

## Description

This role performs post-installation configuration of Proxmox VE 9, optimized for Dell XPS L701X laptop with 8GB RAM and SSD+HDD storage.

## Requirements

- Proxmox VE 9.x installed
- Debian 12 (Bookworm) base system
- Ansible 2.14 or higher
- Root SSH access to Proxmox host

## Role Variables

### Repository Configuration

```yaml
proxmox_use_no_subscription_repo: true
proxmox_use_enterprise_repo: false
proxmox_use_ceph_repo: false
```

### Network Configuration

```yaml
proxmox_wan_interface: eth-usb
proxmox_lan_interface: eth-builtin

proxmox_bridges:
  - name: vmbr0
    address: ""  # DHCP
  - name: vmbr1
    address: "192.168.10.254/24"
  - name: vmbr2
    address: "10.0.30.1/24"
  - name: vmbr99
    address: "10.0.99.1/24"
```

### Storage Configuration

```yaml
proxmox_hdd_storage:
  name: local-hdd
  path: /mnt/hdd
  enabled: true
```

### Optimization

```yaml
proxmox_ksm_enabled: true
proxmox_swappiness: 10
proxmox_cpu_governor: ondemand
```

## Dependencies

None

## Example Playbook

```yaml
---
- name: Configure Proxmox VE
  hosts: proxmox
  become: yes
  roles:
    - role: proxmox
      vars:
        proxmox_use_no_subscription_repo: true
        proxmox_hdd_storage:
          enabled: true
          path: /mnt/hdd
```

## Tags

- `repositories` - Configure Proxmox repositories
- `packages` - Install additional packages
- `networking` - Configure network bridges
- `storage` - Configure storage pools
- `optimization` - Apply system optimizations
- `security` - Security hardening
- `monitoring` - Setup monitoring
- `backup` - Configure backups

## Usage

### Full configuration

```bash
ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
```

### Specific tasks

```bash
# Only configure repositories
ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml --tags repositories

# Only configure networking
ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml --tags networking

# Skip monitoring
ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml --skip-tags monitoring
```

## What This Role Configures

1. **Repositories**
   - Disables enterprise repository
   - Enables no-subscription repository
   - Updates package cache

2. **Packages**
   - Installs essential tools (vim, git, htop, etc.)
   - Installs monitoring tools (smartmontools, lm-sensors)
   - Installs system utilities

3. **Network**
   - Configures 4 network bridges (vmbr0-vmbr99)
   - Sets up udev rules for interface naming
   - Configures DNS servers

4. **Storage**
   - Mounts HDD at /mnt/hdd
   - Creates Proxmox storage pool (local-hdd)
   - Configures backup directory

5. **Optimization**
   - Enables KSM for RAM deduplication
   - Configures swap settings
   - Sets CPU governor
   - Disables USB autosuspend (for USB-Ethernet stability)

6. **Security**
   - Configures SSH
   - Sets up firewall
   - Installs fail2ban

7. **Monitoring**
   - Installs Prometheus Node Exporter
   - Enables SMART monitoring
   - Configures system logging

8. **Backup**
   - Creates backup directory structure
   - Configures backup retention policy

## Hardware-Specific Optimizations

### Dell XPS L701X

- **USB-Ethernet Stability**: Disables USB autosuspend
- **Laptop Mode**: Optimizes for laptop hardware
- **RAM Constraints**: Enables KSM for 8GB RAM
- **Dual Storage**: Optimizes SSD and HDD usage

## Post-Configuration

After running this role:

1. Access Proxmox Web UI: https://10.0.99.1:8006
2. Apply Terraform configuration to create VMs/LXC
3. Use Ansible to configure VMs/LXC

## Troubleshooting

### Repository issues

```bash
# Check repositories
cat /etc/apt/sources.list.d/pve-*.list

# Update manually
apt update
```

### Network issues

```bash
# Check bridges
brctl show
ip link show type bridge

# Restart networking
systemctl restart networking
```

### Storage issues

```bash
# Check HDD mount
df -h /mnt/hdd
mount | grep hdd

# Remount HDD
mount -a

# Check Proxmox storage
pvesm status
```

## License

MIT

## Author

Home Lab Administrator
