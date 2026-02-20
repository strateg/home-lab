# Proxmox VE Post-Installation Scripts

Post-installation configuration scripts for Proxmox VE 9 on Dell XPS L701X.

## Overview

These scripts automate the post-installation configuration of Proxmox VE after initial bare-metal installation. They should be run in sequence after Proxmox is installed and accessible via SSH.

## Prerequisites

- Proxmox VE 9.x installed on Dell XPS L701X
- SSH access to Proxmox host as root
- Network connectivity (internet access for package installation)
- Second HDD (500GB) installed and detected as /dev/sdb

## Installation Scripts

Run these scripts in order:

### 01-install-terraform.sh

**Purpose**: Install Terraform for infrastructure provisioning

**What it does**:
- Adds HashiCorp GPG key and repository
- Installs Terraform v1.7.0
- Enables tab completion
- Verifies installation

**Usage**:
```bash
cd /root/post-install
./01-install-terraform.sh
```

**Duration**: ~2 minutes

---

### 02-install-ansible.sh

**Purpose**: Install Ansible for configuration management

**What it does**:
- Installs Python3 and pip
- Installs Ansible core (v2.14+)
- Installs Python dependencies (proxmoxer, requests, etc.)
- Installs Ansible collections from requirements.yml
- Installs Ansible roles (geerlingguy.*)

**Usage**:
```bash
./02-install-ansible.sh
```

**Duration**: ~3-5 minutes

---

### 03-configure-storage.sh

**Purpose**: Configure HDD storage pool

**What it does**:
- Detects second HDD (/dev/sdb)
- Creates GPT partition table
- Formats as ext4
- Mounts at /mnt/hdd
- Adds to /etc/fstab for automatic mounting
- Creates directory structure (backup, iso, template, snippets)
- Configures Proxmox storage pool (local-hdd)

**Usage**:
```bash
./03-configure-storage.sh
```

**Duration**: ~2 minutes
**Warning**: Will format /dev/sdb - ensure you have the correct device!

---

### 04-configure-network.sh

**Purpose**: Configure network bridges and interfaces

**What it does**:
- Detects USB and built-in Ethernet interfaces
- Creates UDEV rules for persistent naming (eth-usb, eth-builtin)
- Disables USB autosuspend for stability
- Configures 4 network bridges:
  - vmbr0: WAN (DHCP) - USB Ethernet to ISP
  - vmbr1: LAN (192.168.10.254/24) - Built-in Ethernet
  - vmbr2: INTERNAL (10.0.30.1/24) - LXC containers
  - vmbr99: MGMT (10.0.99.1/24) - Management
- Configures DNS servers (Cloudflare + Google)

**Usage**:
```bash
./04-configure-network.sh
```

**Duration**: ~1 minute
**Note**: Requires reboot for UDEV rules to take effect

---

### 05-init-git-repo.sh

**Purpose**: Initialize Git repository for Infrastructure as Code

**What it does**:
- Installs Git
- Configures Git user (interactive)
- Creates project directory (/root/home-lab)
- Initializes Git repository
- Creates comprehensive .gitignore
- Creates initial commit
- Optionally configures remote repository (GitHub/GitLab/Gitea)

**Usage**:
```bash
./05-init-git-repo.sh
```

**Duration**: ~2 minutes (interactive)

---

## Quick Start

### Option 1: Run all scripts automatically

```bash
cd /root/post-install
for script in 01-*.sh 02-*.sh 03-*.sh 04-*.sh 05-*.sh; do
    echo "Running $script..."
    ./$script
done
```

### Option 2: Run scripts individually

```bash
cd /root/post-install

# Install tools
./01-install-terraform.sh
./02-install-ansible.sh

# Configure system
./03-configure-storage.sh
./04-configure-network.sh

# Setup Git
./05-init-git-repo.sh
```

## Post-Script Actions

After running all scripts:

1. **Reboot system** (required for network configuration)
   ```bash
   reboot
   ```

2. **Verify network bridges**
   ```bash
   ip -br link show type bridge
   brctl show
   ```

3. **Verify storage**
   ```bash
   pvesm status
   df -h /mnt/hdd
   ```

4. **Copy IaC files to Proxmox**
   ```bash
   # From your workstation
   scp -r ~/workspaces/projects/home-lab/* root@10.0.99.1:/root/home-lab/
   ```

5. **Initialize Terraform**
   ```bash
   cd /root/home-lab/terraform
   cp terraform.tfvars.example terraform.tfvars
   vim terraform.tfvars  # Configure your settings
   terraform init
   terraform plan
   ```

6. **Run Ansible playbook**
   ```bash
   cd /root/home-lab/ansible
   ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml
   ```

## Troubleshooting

### Script fails: "Permission denied"

Make scripts executable:
```bash
chmod +x *.sh
```

### Network configuration doesn't apply

Reboot the system:
```bash
reboot
```

Or restart networking:
```bash
systemctl restart networking
```

### HDD not detected

Check available disks:
```bash
lsblk -o NAME,SIZE,TYPE,MODEL
fdisk -l
```

Update HDD_DEVICE in 03-configure-storage.sh if needed.

### Terraform/Ansible not found after installation

Reload shell environment:
```bash
source ~/.bashrc
hash -r
```

## Network Topology After Configuration

```
ISP Router
    │
    └─── [eth-usb] ──► vmbr0 (WAN, DHCP)
                            │
                            └─── OPNsense WAN interface

GL.iNet Slate AX (192.168.10.1)
    │
    └─── [eth-builtin] ──► vmbr1 (LAN, 192.168.10.254/24)
                                │
                                └─── OPNsense LAN interface

LXC Containers ──► vmbr2 (INTERNAL, 10.0.30.1/24)
    │
    ├─── PostgreSQL (10.0.30.10)
    ├─── Redis (10.0.30.20)
    ├─── Nextcloud (10.0.30.30)
    └─── Jellyfin (10.0.30.40)

Management ──► vmbr99 (MGMT, 10.0.99.1/24)
    │
    ├─── Proxmox Web UI (10.0.99.1:8006)
    └─── OPNsense Web UI (10.0.99.10)
```

## Storage Layout After Configuration

```
SSD 180GB (local-lvm)
├─── Root partition: 50 GB
├─── Swap: 2 GB
└─── LVM thin pool: ~128 GB
     └─── VMs/LXC production data

HDD 500GB (local-hdd, /mnt/hdd)
├─── backup/     - VM/LXC backups
├─── iso/        - ISO images
├─── template/   - VM templates
├─── snippets/   - Cloud-init snippets
└─── dump/       - Configuration dumps
```

## Hardware Specifications

**Dell XPS L701X**:
- CPU: Intel Core i3-M370 (2 cores, 2.4 GHz)
- RAM: 8 GB DDR3
- Storage:
  - SSD 180 GB (SATA) - System + VMs
  - HDD 500 GB (SATA) - Backups + Templates
- Network:
  - USB Ethernet (1 Gb/s) - WAN
  - Built-in Ethernet (1 Gb/s) - LAN
  - WiFi (not used)

## Next Steps

After post-installation:

1. ✅ Reboot system
2. ✅ Verify network and storage
3. ⏭️ Apply Terraform configuration
4. ⏭️ Run Ansible playbooks
5. ⏭️ Create VMs and LXC containers
6. ⏭️ Configure services

## Support

For issues or questions:
- Check Proxmox documentation: https://pve.proxmox.com/wiki/
- Review logs: `journalctl -xe`
- Check service status: `systemctl status <service>`

## License

MIT
