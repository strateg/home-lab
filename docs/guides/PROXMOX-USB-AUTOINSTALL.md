# Proxmox USB Auto-Install from Topology

**Status**: ✅ STABLE
**Last Updated**: 2025-10-22
**Applies to**: Proxmox VE 9, Dell XPS L701X (Legacy BIOS/MBR)

---

## Overview

This guide explains how to create a bootable USB drive for **unattended Proxmox VE 9 installation** that automatically configures the system using data from `topology.yaml`.

The installation process:
1. Reads Proxmox node configuration from `topology.yaml`
2. Generates `answer.toml` with correct hostname, disk layout, network settings
3. Creates hybrid ISO with embedded answer file
4. Writes ISO to USB drive (Legacy BIOS/MBR compatible)
5. Installs Proxmox automatically (10-15 minutes, no interaction needed)

---

## Prerequisites

### System Requirements

- **Proxmox ISO**: Download from [proxmox.com](https://www.proxmox.com/en/downloads)
- **USB Drive**: 8GB+ (will be **completely erased**)
- **Target Hardware**: Dell XPS L701X or compatible Legacy BIOS system
- **Host OS**: Linux (tested on Ubuntu/Debian)

### Software Requirements

Install required packages on your **development machine** (not target):

```bash
sudo apt update
sudo apt install \
    syslinux \
    extlinux \
    parted \
    dosfstools \
    proxmox-auto-install-assistant \
    python3
```

### Topology Requirements

Your `topology.yaml` must define:
- **Proxmox hypervisor node** in `physical_topology.devices`
- **Disk configuration** with at least one disk (SSD recommended)
- **DNS zone** for domain (e.g., `home.local`)
- **Management network** (optional, uses DHCP if not defined)

---

## Quick Start

### 1. Validate Topology

Before generating USB, validate your topology:

```bash
cd /path/to/home-lab/new_system

# Validate topology for Proxmox requirements
python3 topology-tools/generate-proxmox-answer.py --validate
```

**Expected output:**
```
✓ Topology loaded successfully
  - Version: 2.2.0
  - Proxmox node: gamayun.home.local

✓ Topology validation passed
```

If validation fails, fix errors in `topology.yaml` before proceeding.

### 2. Generate Answer File (Optional)

The USB creation script auto-generates `answer.toml`, but you can preview it:

```bash
# Generate answer.toml from topology
python3 topology-tools/generate-proxmox-answer.py topology.yaml manual-scripts/bare-metal/answer.toml

# Review generated file
cat manual-scripts/bare-metal/answer.toml
```

### 3. Create Bootable USB

**⚠️ WARNING: This will ERASE all data on the USB drive!**

```bash
cd /path/to/home-lab/new_system/bare-metal

# Identify USB device (e.g., /dev/sdc)
lsblk

# Create bootable USB (auto-generates answer.toml from topology)
sudo ./create-legacy-autoinstall-proxmox-usb.sh \
    ~/Downloads/proxmox-ve_9.0-1.iso \
    answer.toml \
    /dev/sdc
```

**Script workflow:**
1. ✓ Validates USB device
2. ✓ Generates `answer.toml` from `topology.yaml` (overwrites existing)
3. ✓ Validates `answer.toml` format
4. ✓ Asks for root password (or uses default: `proxmox`)
5. ✓ Creates hybrid ISO with embedded answer file
6. ✓ Writes ISO to USB with Legacy BIOS boot support

### 4. Install Proxmox

1. **Insert USB** into Dell XPS L701X
2. **Power on** and press **F12** for boot menu
3. Select **"Removable Devices"** or **"USB HDD"**
4. **Proxmox installer starts automatically** (no interaction needed)
5. Installation completes in **10-15 minutes**
6. **System powers off** after installation

### 5. First Boot

**⚠️ IMPORTANT: Remove USB before powering on!**

Legacy BIOS doesn't support reinstall prevention. If USB is still connected, it will reinstall Proxmox.

1. **Remove USB drive**
2. **Power on** to boot into Proxmox
3. **Access Web UI**: `https://<proxmox-ip>:8006`
   - Username: `root`
   - Password: (set during USB creation, default: `proxmox`)

---

## Configuration Details

### Generated from Topology

The following settings are automatically extracted from `topology.yaml`:

| Setting | Topology Source | Example |
|---------|-----------------|---------|
| **Hostname** | `physical_topology.devices[].id` + DNS domain | `gamayun.home.local` |
| **System Disk** | `L1_foundation.devices[].specs.storage_slots[].media` (SSD preferred) | `sda` |
| **Network** | `logical_topology.networks` (management network) | DHCP (default) |
| **Domain** | `logical_topology.dns.zones[].domain` | `home.local` |

### Disk Layout

Generated from topology, example for Dell XPS L701X (180GB SSD):

```toml
[disk-setup]
filesystem = "ext4"
disk_list = ["sda"]

# LVM configuration
lvm.swapsize = 2    # 2 GB swap
lvm.maxroot = 50    # 50 GB root filesystem
lvm.minfree = 10    # 10 GB reserve
lvm.maxvz = 0       # ~128 GB for VMs/LXC
```

### Network Configuration

**Default: DHCP** (recommended for auto-install)

Static IP from topology can be used with `--static` flag:

```bash
python3 topology-tools/generate-proxmox-answer.py topology.yaml answer.toml --static
```

This uses management network IP allocation from `topology.yaml`.

### Password Management

**Default password**: `proxmox` (SHA-512 hash embedded in `answer.toml`)

**To set custom password during USB creation:**
- Script prompts for password interactively
- Password is hashed with SHA-512
- Hash is updated in `answer.toml` before ISO creation

**To change password in answer.toml manually:**

```bash
# Generate new password hash
openssl passwd -6 "YourStrongPassword"

# Edit answer.toml and replace root_password value
vim manual-scripts/bare-metal/answer.toml
```

---

## Troubleshooting

### Validation Errors

**Error: "No Proxmox hypervisor found in topology"**

Check that `topology.yaml` has a device with `type: hypervisor`:

```yaml
physical_topology:
  devices:
    - id: gamayun
      type: hypervisor  # Required!
      role: compute
      # ...
```

**Error: "Proxmox node has no disks defined"**

Add disk configuration to node specs:

```yaml
specs:
  disks:
    - id: disk-ssd-system
      device: "/dev/sda"
      size_gb: 180
      type: "ssd"
```

### USB Boot Issues

**USB not detected in BIOS**

- Ensure USB is inserted before powering on
- Try different USB ports (USB 2.0 ports often work better)
- Check BIOS boot order (USB should be first)

**Installer doesn't start automatically**

- Check that `answer.toml` was embedded correctly
- Verify `proxmox-auto-install-assistant` validation passed
- Try Legacy BIOS mode (not UEFI) for Dell XPS L701X

### Installation Issues

**Password doesn't work after installation**

Legacy BIOS auto-install may have issues with password. If you can't login:

1. Boot from USB again
2. At GRUB menu, press `c` for command line
3. Type: `linux (hd0,gpt3)/vmlinuz root=/dev/sda3 init=/bin/bash`
4. Type: `boot`
5. At prompt: `mount -o remount,rw /`
6. Reset password: `passwd root`
7. Reboot: `sync && reboot -f`

**Network not configured**

Auto-install uses DHCP by default. Configure static IP after installation:

```bash
# SSH to Proxmox
ssh root@<proxmox-ip>

# Run post-install network configuration
cd /root/post-install
./04-configure-network.sh
```

---

## Advanced Usage

### Custom Password Hash

Generate `answer.toml` with specific password:

```bash
# Generate password hash
PASSWORD_HASH=$(openssl passwd -6 "MySecurePassword")

# Generate answer.toml with custom password
python3 topology-tools/generate-proxmox-answer.py \
    topology.yaml \
    answer.toml \
    --password "$PASSWORD_HASH"
```

### Static IP Configuration

Use management network IP from topology:

```bash
python3 topology-tools/generate-proxmox-answer.py \
    topology.yaml \
    answer.toml \
    --static
```

**Note**: Static IP requires management network with IP allocation for Proxmox node in `topology.yaml`.

### Non-Interactive USB Creation

Skip password prompt (uses default password):

```bash
AUTO_CONFIRM=1 sudo ./create-legacy-autoinstall-proxmox-usb.sh \
    proxmox-ve_9.0-1.iso \
    answer.toml \
    /dev/sdc
```

### Manual answer.toml

If you don't want auto-generation from topology:

```bash
# Create answer.toml manually
vim manual-scripts/bare-metal/answer.toml

# Create USB without topology integration
# (move topology.yaml temporarily or edit script)
sudo ./create-legacy-autoinstall-proxmox-usb.sh \
    proxmox-ve_9.0-1.iso \
    answer.toml \
    /dev/sdc
```

---

## Workflow Integration

### Part of Infrastructure-as-Data

This USB creation process is part of the complete infrastructure workflow:

```
topology.yaml  →  generate-proxmox-answer.py  →  answer.toml
                                                        ↓
    create-legacy-autoinstall-proxmox-usb.sh  ←  Proxmox ISO
                        ↓
                  Bootable USB
                        ↓
              Auto-Install Proxmox (10-15 min)
                        ↓
              Post-Install Scripts (/root/post-install/)
                        ↓
              Terraform Apply (generate bridges, VMs, LXC)
                        ↓
              Ansible Configure (services, network)
```

### Next Steps After Installation

After successful Proxmox installation:

1. **SSH to Proxmox**: `ssh root@<proxmox-ip>`

2. **Run post-install scripts**:
   ```bash
   cd /root/post-install
   ./01-install-terraform.sh
   ./02-install-ansible.sh
   ./03-configure-storage.sh
   ./04-configure-network.sh
   ./05-init-git-repo.sh
   ```

3. **Copy repository**:
   ```bash
   scp -r ~/home-lab root@<proxmox-ip>:/root/
   ```

4. **Generate and apply infrastructure**:
   ```bash
   ssh root@<proxmox-ip>
   cd /root/home-lab/new_system

   # Generate Terraform
   python3 topology-tools/generate-terraform.py
   cd generated/terraform
   terraform init
   terraform apply

   # Generate Ansible inventory
   cd /root/home-lab/new_system
   python3 topology-tools/generate-ansible-inventory.py
   cd ansible
   ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml
   ```

---

## Files Reference

| File | Purpose | Generated? |
|------|---------|------------|
| `topology.yaml` | Infrastructure source of truth | Manual |
| `topology-tools/generate-proxmox-answer.py` | Answer file generator | Manual |
| `manual-scripts/bare-metal/answer.toml` | Proxmox auto-install config | Generated |
| `manual-scripts/bare-metal/create-legacy-autoinstall-proxmox-usb.sh` | USB creation script | Manual |
| `/tmp/prepared-proxmox-*.iso` | Hybrid ISO with answer | Generated |

---

## Security Notes

### Password Security

- **Default password (`proxmox`) is INSECURE** for production
- **Always change password** during USB creation or in `answer.toml`
- **Never commit** `answer.toml` with real passwords to Git
- Use `.gitignore` to exclude `answer.toml` if it contains secrets

### answer.toml Handling

```bash
# Check if answer.toml is gitignored
git check-ignore -v manual-scripts/bare-metal/answer.toml

# If not ignored, add to .gitignore
echo "manual-scripts/bare-metal/answer.toml" >> .gitignore
```

**Note**: Sample `answer.toml` with default password can be committed for reference, but production files should be gitignored.

---

## References

- **Proxmox Auto-Install Documentation**: https://pve.proxmox.com/wiki/Automated_Installation
- **proxmox-auto-install-assistant**: https://pve.proxmox.com/wiki/Automated_Installation#assistant
- **SYSLINUX**: https://wiki.syslinux.org/
- **Topology Structure**: [TOPOLOGY-MODULAR.md](../architecture/TOPOLOGY-MODULAR.md)
- **Infrastructure Workflow**: [GENERATED-QUICK-GUIDE.md](GENERATED-QUICK-GUIDE.md)

---

**Last Updated**: 2025-10-22
**Topology Version**: 2.2.0
**Proxmox Version**: 9.0-1
