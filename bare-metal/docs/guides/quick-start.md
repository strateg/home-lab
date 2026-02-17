# Quick Start - Proxmox Auto-Install USB

Get Proxmox VE 9 installed in under 15 minutes with automated USB installation.

## TL;DR

```bash
# 1. Install tools (one time)
sudo apt update && sudo apt install proxmox-auto-install-assistant

# 2. Create UEFI USB (recommended - has reinstall prevention)
cd new_system/bare-metal
sudo ./create-uefi-autoinstall-proxmox-usb.sh ~/Downloads/proxmox-ve_9.0-1.iso answer.toml /dev/sdc

# 3. Boot from USB (F12 → Select "UEFI: USB Device")
# 4. Wait for automatic installation (~10-15 minutes)
# 5. System reboots to hard drive automatically!
```

## Step-by-Step

### 1. Install Required Tools

**Debian/Ubuntu**:
```bash
# Add Proxmox repository
wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg \
  -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg

echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" | \
  sudo tee /etc/apt/sources.list.d/pve-install-repo.list

# Install
sudo apt update
sudo apt install proxmox-auto-install-assistant

# Verify
proxmox-auto-install-assistant --version
```

### 2. Download Proxmox ISO

```bash
cd ~/Downloads
wget https://enterprise.proxmox.com/iso/proxmox-ve_9.0-1.iso
```

### 3. Find Your USB Device

```bash
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL
# Look for your USB device (e.g., /dev/sdc with 115G SanDisk)
```

### 4. Create Bootable USB

**UEFI Mode** (Recommended - has reinstall prevention):
```bash
cd ~/path/to/home-lab/new_system/bare-metal
sudo ./create-uefi-autoinstall-proxmox-usb.sh ~/Downloads/proxmox-ve_9.0-1.iso answer.toml /dev/sdc
```

**Legacy BIOS Mode** (Fallback - NO reinstall prevention):
```bash
sudo ./create-legacy-autoinstall-proxmox-usb.sh ~/Downloads/proxmox-ve_9.0-1.iso answer.toml /dev/sdc
```

> ⚠️ Replace `/dev/sdc` with your actual USB device!

### 5. Boot and Install

1. Insert USB into Dell XPS L701X
2. Power on and press **F12**
3. Select boot device:
   - **UEFI mode**: Choose "UEFI: USB Device" or "UEFI: SanDisk"
   - **Legacy mode**: Choose "Removable Devices" or "USB HDD"
4. Installation starts automatically
5. Wait 10-15 minutes
6. System reboots:
   - **UEFI**: Boots from hard drive automatically (even with USB inserted)
   - **Legacy**: System powers off - **REMOVE USB** before powering on!

### 6. Access Proxmox Web UI

After installation:
```bash
# Find IP (check router DHCP leases or use nmap)
nmap -sP 192.168.1.0/24 | grep -i proxmox

# Access web UI
https://<proxmox-ip>:8006
# Username: root
# Password: (from answer.toml - default: Homelab2025!)
```

## Customization (Optional)

### Change Root Password

```bash
# Generate password hash
openssl passwd -6 "YourStrongPassword"

# Edit answer.toml
nano answer.toml
# Update: root_password = "$6$generated_hash..."
```

### Change Hostname

```bash
nano answer.toml
# Update: fqdn = "your-hostname.home.local"
```

### Configure Static IP (instead of DHCP)

```bash
nano answer.toml
# Change:
# [network]
# source = "from-answer"
# cidr = "192.168.1.100/24"
# gateway = "192.168.1.1"
# dns = "1.1.1.1"
```

## What's Next?

After installation, run post-install scripts:

```bash
ssh root@<proxmox-ip>

# Run configuration scripts
cd /root/post-install
./01-install-terraform.sh
./02-install-ansible.sh
./03-configure-storage.sh
./04-configure-network.sh
./05-init-git-repo.sh

reboot
```

After reboot, Proxmox will be accessible at management IP: `https://10.0.99.1:8006`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| USB boots but asks questions (not automatic) | Wrong boot mode - use UEFI for UEFI USB, Legacy for Legacy USB |
| Permission denied error | Run script with `sudo` |
| Device busy error | Unmount USB: `sudo umount /dev/sdc*` |
| proxmox-auto-install-assistant not found | Install it (see Step 1) |

## More Information

- **[USB Creation Guide](usb-creation.md)** - Detailed instructions and troubleshooting
- **[Reinstall Prevention](reinstall-prevention.md)** - How UUID protection works
- **[Main README](../../README.md)** - Full project documentation

## Boot Mode Comparison

| Feature | UEFI (Recommended) | Legacy BIOS |
|---------|-------------------|-------------|
| Reinstall Prevention | ✅ Yes | ❌ No |
| USB Removal Required | ❌ No | ✅ Yes |
| Modern Systems | ✅ Yes | ⚠️ Old hardware only |
| Script | `create-uefi-autoinstall-proxmox-usb.sh` | `create-legacy-autoinstall-proxmox-usb.sh` |

**Recommendation**: Always use UEFI mode unless your hardware doesn't support it.
