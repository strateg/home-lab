# Proxmox VE Bare-Metal Installation

Automated bare-metal installation for Proxmox VE 9 on Dell XPS L701X using auto-install USB.

## Overview

This directory contains everything needed to create a bootable USB drive that will automatically install and configure Proxmox VE 9 on Dell XPS L701X laptop.

**Key Features**:
- Unattended installation (no user interaction required)
- Automatic disk partitioning (ext4, LVM-thin)
- Network configuration via DHCP
- Repository setup (no-subscription)
- Post-install scripts for complete system configuration

## Files

```
bare-metal/
├── README.md              # This file
├── answer.toml            # Proxmox auto-install configuration
├── create-usb.sh          # USB creator script
└── post-install/          # Post-installation scripts
    ├── README.md          # Post-install guide
    ├── 01-install-terraform.sh
    ├── 02-install-ansible.sh
    ├── 03-configure-storage.sh
    ├── 04-configure-network.sh
    └── 05-init-git-repo.sh
```

## Prerequisites

### Hardware Requirements

**Dell XPS L701X**:
- CPU: Intel Core i3-M370 (2 cores, 2.4 GHz)
- RAM: 8 GB DDR3
- Storage:
  - SSD 180 GB (SATA) - for Proxmox system and VMs
  - HDD 500 GB (SATA) - for backups and templates
- Network:
  - USB Ethernet adapter (1 Gb/s)
  - Built-in Ethernet (1 Gb/s)

### Software Requirements

- USB drive (minimum 2 GB)
- Proxmox VE 9 ISO file
- Linux system with:
  - Root access (sudo)
  - `dd`, `lsblk`, `mkpasswd` tools

## Quick Start

### Step 1: Prepare Bootable USB

```bash
cd bare-metal/

# Download Proxmox VE 9 ISO (if not already downloaded)
wget https://enterprise.proxmox.com/iso/proxmox-ve_9.0-1.iso

# Create bootable USB (replace /dev/sdX with your USB device)
sudo ./create-usb.sh /dev/sdX proxmox-ve_9.0-1.iso
```

**Important**:
- Replace `/dev/sdX` with your actual USB device (e.g., `/dev/sdb`)
- All data on USB drive will be ERASED
- Script will prompt for root password (for Proxmox)

### Step 2: Install Proxmox

1. Insert USB drive into Dell XPS L701X
2. Power on laptop
3. Press **F12** for boot menu
4. Select USB drive (UEFI mode)
5. Installation starts automatically (~10-15 minutes)
6. Remove USB and reboot when complete

### Step 3: Post-Installation Configuration

```bash
# SSH to Proxmox (it will have DHCP IP initially)
ssh root@<proxmox-ip>

# Copy post-install scripts to Proxmox
# (if not already on USB)
scp -r post-install/ root@<proxmox-ip>:/root/

# SSH to Proxmox
ssh root@<proxmox-ip>

# Run post-install scripts
cd /root/post-install
./01-install-terraform.sh
./02-install-ansible.sh
./03-configure-storage.sh
./04-configure-network.sh
./05-init-git-repo.sh

# Reboot to apply network configuration
reboot
```

### Step 4: Access Proxmox Web UI

After reboot, access Proxmox at management IP:
```
https://10.0.99.1:8006
Username: root
Password: (the one you set during USB creation)
```

## Detailed Installation Guide

### Phase 1: USB Creation

The `create-usb.sh` script performs these steps:

1. **Validates USB device**
   - Checks if device exists
   - Verifies minimum size (2 GB)
   - Unmounts if mounted

2. **Validates ISO file**
   - Checks if file exists
   - Verifies it's a valid ISO image

3. **Prepares answer.toml**
   - Prompts for root password
   - Generates SHA-512 password hash
   - Updates answer.toml

4. **Creates bootable USB**
   - Writes ISO to USB with `dd`
   - Syncs data to ensure write completion

5. **Adds auto-install config**
   - Mounts USB partition
   - Copies answer.toml to USB
   - Copies post-install scripts (optional)

**Usage**:
```bash
sudo ./create-usb.sh <USB_DEVICE> <ISO_FILE>

# Examples:
sudo ./create-usb.sh /dev/sdb proxmox-ve_9.0-1.iso
sudo ./create-usb.sh /dev/sdc ~/Downloads/proxmox-ve_9.0-1.iso
```

**Options**:
- `-h, --help`: Show help message

### Phase 2: Proxmox Installation

The auto-install process configures:

**Disk Layout** (ext4 on SSD 180GB):
```
/dev/sda1    512 MB    EFI System Partition
/dev/sda2    50 GB     Root filesystem (ext4)
/dev/sda3    2 GB      Swap
/dev/sda4    ~128 GB   LVM-thin pool (for VMs/LXC)
```

**Network Configuration**:
- DHCP enabled (temporary)
- Hostname: `pve.home.local`
- Interface: auto-detected

**Repository Configuration**:
- Enterprise repository: disabled
- No-subscription repository: enabled
- Package cache: updated

**First-boot Commands**:
- Disable enterprise repository
- Enable no-subscription repository
- Update package cache
- Install essential tools (vim, git, curl, wget, htop, tmux)
- Create /root/post-install directory

### Phase 3: Post-Installation

See [post-install/README.md](post-install/README.md) for detailed information.

**Scripts**:
1. **01-install-terraform.sh**: Install Terraform v1.7.0
2. **02-install-ansible.sh**: Install Ansible v2.14+
3. **03-configure-storage.sh**: Configure HDD storage pool
4. **04-configure-network.sh**: Configure network bridges
5. **05-init-git-repo.sh**: Initialize Git repository

## Configuration Details

### answer.toml

Auto-install configuration file with:
- Keyboard layout: US
- Timezone: UTC
- Root password: SHA-512 hash
- Disk: ext4 filesystem, 50GB root, 2GB swap
- Network: DHCP enabled
- First-boot: Repository configuration

**Security Note**:
- Default password hash in answer.toml: `Homelab2025!`
- Change before using in production
- Generate new hash: `mkpasswd -m sha-512 "YourPassword"`

### Disk Partitioning Strategy

**SSD 180GB** (`/dev/sda`):
- 50 GB: Root filesystem (Proxmox OS, system services)
- 2 GB: Swap (for RAM overflow)
- ~128 GB: LVM-thin pool (production VMs and LXC containers)

**HDD 500GB** (`/dev/sdb`):
- Entire disk: Backup, ISO images, VM templates
- Mounted at: `/mnt/hdd`
- Proxmox storage ID: `local-hdd`

### Network Topology

After post-installation, network will be configured as:

```
┌─────────────────────────────────────────────────────────┐
│                     ISP Router                          │
│                   (DHCP Server)                         │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────▼───────────┐
          │  USB Ethernet (eth-usb)│
          └────────────┬───────────┘
                       │
          ┌────────────▼───────────┐
          │   vmbr0 (WAN, DHCP)    │
          └────────────┬───────────┘
                       │
          ┌────────────▼───────────────────────┐
          │    OPNsense Firewall VM            │
          │    WAN: vmbr0 (DHCP)               │
          │    LAN: vmbr1 (192.168.10.254/24)  │
          └────────────┬───────────────────────┘
                       │
          ┌────────────▼────────────────────────┐
          │ Built-in Ethernet (eth-builtin)    │
          └────────────┬────────────────────────┘
                       │
          ┌────────────▼────────────────────────┐
          │  GL.iNet Slate AX Router            │
          │  (192.168.10.1 - Travel/Home)       │
          └─────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│             LXC Containers Network                       │
│         vmbr2 (INTERNAL, 10.0.30.1/24)                   │
│  ┌───────────────┬────────────┬─────────────┐           │
│  │ PostgreSQL    │ Redis      │ Nextcloud   │           │
│  │ (10.0.30.10)  │(10.0.30.20)│(10.0.30.30) │           │
│  └───────────────┴────────────┴─────────────┘           │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│           Management Network                             │
│        vmbr99 (MGMT, 10.0.99.1/24)                       │
│  ┌───────────────┬──────────────────────┐               │
│  │ Proxmox VE    │ OPNsense Web UI      │               │
│  │ (10.0.99.1)   │ (10.0.99.10)         │               │
│  └───────────────┴──────────────────────┘               │
└──────────────────────────────────────────────────────────┘
```

## Troubleshooting

### USB Creation Issues

**Error: Device not found**
```bash
# List available devices
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT

# Use correct device (e.g., /dev/sdb, not /dev/sdb1)
```

**Error: Permission denied**
```bash
# Run with sudo
sudo ./create-usb.sh /dev/sdb proxmox-ve_9.0-1.iso
```

**Error: ISO file not valid**
```bash
# Verify ISO file
file proxmox-ve_9.0-1.iso
# Should output: "ISO 9660 CD-ROM filesystem data"

# Download again if corrupted
```

### Installation Issues

**Boot menu doesn't show USB**
- Ensure USB is inserted
- Try different USB port
- Ensure UEFI mode is enabled in BIOS

**Installation hangs**
- Remove and reinsert USB
- Verify ISO file integrity
- Check hardware compatibility

**Installation fails: Disk errors**
- Check SSD health: `smartctl -a /dev/sda`
- Verify disk is detected in BIOS
- Try different SATA port/cable

### Post-Installation Issues

**Cannot SSH to Proxmox**
```bash
# Find Proxmox IP
# Check your router's DHCP leases
# Or connect monitor and keyboard to see IP

# If SSH key issues
ssh -o StrictHostKeyChecking=no root@<ip>
```

**Scripts fail to run**
```bash
# Make scripts executable
chmod +x /root/post-install/*.sh

# Run with bash explicitly
bash /root/post-install/01-install-terraform.sh
```

**Network configuration fails**
```bash
# Check interface names
ip link show

# Update MAC addresses in 04-configure-network.sh
# Rerun script
```

## Security Considerations

### Password Security

- Change default password in answer.toml before creating USB
- Use strong passwords (20+ characters, mixed case, numbers, symbols)
- Store passwords securely (password manager)

### Network Security

- Management network (vmbr99) is isolated
- Firewall (OPNsense) protects internal networks
- SSH access restricted to management network

### Storage Security

- Encrypt sensitive data on VMs/LXC
- Regular backups to HDD
- Keep backups encrypted
- Test restore procedures

## Next Steps

After completing bare-metal installation:

1. ✅ Proxmox VE installed and accessible
2. ✅ Storage configured (SSD + HDD)
3. ✅ Network bridges created
4. ✅ Git repository initialized

**Continue with**:
5. ⏭️ Copy IaC files to Proxmox
6. ⏭️ Configure Terraform (terraform.tfvars)
7. ⏭️ Apply Terraform configuration
8. ⏭️ Run Ansible playbooks
9. ⏭️ Create VMs and LXC containers

See [../README.md](../README.md) for complete project documentation.

## Resources

- [Proxmox VE Documentation](https://pve.proxmox.com/wiki/Main_Page)
- [Proxmox VE Auto-Install Guide](https://pve.proxmox.com/wiki/Automated_Installation)
- [Terraform Proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [Ansible Proxmox Module](https://docs.ansible.com/ansible/latest/collections/community/general/proxmox_module.html)

## License

MIT
