# Proxmox Auto-Install USB Creation Guide

Complete guide to creating bootable USB drives for automated Proxmox VE 9 installation.

## Overview

Two modes are available:

| Mode | Script | Reinstall Prevention | Use Case |
|------|--------|---------------------|----------|
| **UEFI** (Recommended) | `create-uefi-autoinstall-proxmox-usb.sh` | ✅ Yes | Modern systems with UEFI boot |
| **Legacy BIOS** | `create-legacy-autoinstall-proxmox-usb.sh` | ❌ No | Older systems without UEFI |

## UEFI Mode (Recommended)

### Features

- ✅ **Full reinstall prevention** - USB won't reinstall if system already installed
- ✅ Automatic boot from hard drive after installation
- ✅ No need to remove USB after installation
- ✅ Modern boot standard
- ✅ UUID-based installation tracking

### Usage

```bash
sudo ./create-uefi-autoinstall-proxmox-usb.sh <ISO_FILE> answer.toml <USB_DEVICE>

# Example
sudo ./create-uefi-autoinstall-proxmox-usb.sh ~/Downloads/proxmox-ve_9.0-1.iso answer.toml /dev/sdc
```

### Boot Instructions

1. Insert USB into Dell XPS L701X
2. Press **F12** during boot
3. Select **UEFI: USB Device** (not just "USB Device")
4. System installs automatically (~10-15 minutes)
5. System reboots to hard drive (even with USB inserted)

### What Happens Internally

The script uses the official Proxmox method:

```bash
# 1. Validate configuration
proxmox-auto-install-assistant validate-answer answer.toml

# 2. Embed answer.toml into ISO
proxmox-auto-install-assistant prepare-iso \
  --fetch-from iso \
  --answer-file answer.toml \
  --on-first-boot first-boot.sh \
  original.iso

# 3. Write prepared ISO to USB
dd if=prepared.iso of=/dev/sdX

# 4. Add UUID-based reinstall prevention
# - Generate installation UUID
# - Modify GRUB to check for existing installation
# - Add first-boot script to mark system as installed
```

See [Reinstall Prevention Guide](reinstall-prevention.md) for detailed explanation.

## Legacy BIOS Mode (Fallback)

### Limitations

⚠️ **Important Limitations**:
- **NO reinstall prevention** - Will always try to reinstall when booted from USB
- **Must remove USB manually** after installation
- ISO filesystem is read-only (cannot modify GRUB)
- Only use if UEFI boot fails

### Why No Reinstall Prevention?

- Hybrid ISO uses ISO9660 filesystem (read-only)
- Cannot modify GRUB configuration on read-only filesystem
- UEFI has writable FAT32 partition, Legacy BIOS does not

### Usage

```bash
sudo ./create-legacy-autoinstall-proxmox-usb.sh <ISO_FILE> answer.toml <USB_DEVICE>

# Example
sudo ./create-legacy-autoinstall-proxmox-usb.sh ~/Downloads/proxmox-ve_9.0-1.iso answer.toml /dev/sdc
```

### Boot Instructions

1. Insert USB into Dell XPS L701X
2. Press **F12** during boot
3. Select **Removable Devices** or **USB HDD** (not UEFI)
4. System installs automatically (~10-15 minutes)
5. System powers off after installation
6. **⚠️ REMOVE USB BEFORE POWERING ON!**
7. Power on to boot from hard drive

### If You Forget to Remove USB

- Dell will boot from USB again
- Blue GRUB menu appears offering to reinstall
- Press **Ctrl+C** or **F12** and select hard drive manually

## Prerequisites

### Required Tools

```bash
# Check if installed
which proxmox-auto-install-assistant
which dd lsblk parted

# For Legacy BIOS only
which extlinux syslinux
```

### Installing proxmox-auto-install-assistant

**On Debian/Ubuntu**:

```bash
# Add Proxmox repository
wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg \
  -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg

echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" | \
  sudo tee /etc/apt/sources.list.d/pve-install-repo.list

# Install
sudo apt update
sudo apt install proxmox-auto-install-assistant
```

**On other distributions**:
- Download from [Proxmox Downloads](https://www.proxmox.com/en/downloads)
- Build from source (see Proxmox documentation)

## Configuration: answer.toml

The `answer.toml` file contains all installation parameters:

```toml
[global]
keyboard = "en-us"
country = "us"
timezone = "UTC"
root_password = "$6$..." # SHA-512 hash
mailto = "admin@home.local"
fqdn = "gamayun.home.local"
reboot_mode = "power-off"

[disk-setup]
filesystem = "ext4"
disk_list = ["sda"]  # SSD only, HDD preserved
lvm.swapsize = 2
lvm.maxroot = 50
lvm.minfree = 10
lvm.maxvz = 0

[network]
source = "from-dhcp"

[first-boot]  # Required for UEFI mode with --on-first-boot
source = "from-iso"
ordering = "fully-up"
```

See the included `answer.toml` for full configuration.

## Finding Your USB Device

```bash
# List block devices
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL

# Example output
NAME        SIZE TYPE MOUNTPOINT MODEL
sda       180.4G disk            INTEL SSDSC2BF180A4H
├─sda1      512M part /boot/efi
├─sda2        2G part [SWAP]
└─sda3    177.9G part /
sdc       114.6G disk            SanDisk 3.2Gen1  ← This is your USB
├─sdc1        1G part
└─sdc2    113.6G part
```

**Important**: Use the device name (e.g., `/dev/sdc`), not partition names (`/dev/sdc1`).

## Verification

After USB creation:

```bash
# Check partitions
lsblk /dev/sdc

# For UEFI mode, verify UUID protection
sudo mount /dev/sdc2 /mnt
cat /mnt/EFI/BOOT/grub.cfg | grep usb_uuid
# Should show: set usb_uuid="TIMEZONE_YYYY_MM_DD_HH_MM"
sudo umount /mnt
```

## Troubleshooting

### Error: "proxmox-auto-install-assistant: command not found"

**Solution**: Install the tool (see Prerequisites section above)

### Error: "Permission denied"

**Solution**: Run with `sudo`:
```bash
sudo ./create-uefi-autoinstall-proxmox-usb.sh ...
```

### Error: "No such file or directory (os error 2)"

**Cause**: Missing `[first-boot]` section in `answer.toml` (UEFI mode)

**Solution**: Ensure `answer.toml` contains:
```toml
[first-boot]
source = "from-iso"
ordering = "fully-up"
```

### Error: Device is busy

**Solution**: Unmount all partitions:
```bash
sudo umount /dev/sdc* 2>/dev/null
sudo ./create-uefi-autoinstall-proxmox-usb.sh ...
```

### USB boots but shows interactive installer (not automatic)

**Possible causes**:
1. Wrong boot mode (booted UEFI when USB is Legacy, or vice versa)
2. `answer.toml` not embedded correctly
3. ISO not prepared with `proxmox-auto-install-assistant`

**Solution**: Recreate USB following this guide exactly

### Dell boots from USB even after installation (UEFI mode)

**This is a bug** - Reinstall prevention should work in UEFI mode.

**Debug**:
```bash
# Check if first-boot script ran
ssh root@proxmox-ip
cat /etc/proxmox-install-id
cat /boot/efi/proxmox-installed

# Check GRUB wrapper on USB
sudo mount /dev/sdc2 /mnt
cat /mnt/EFI/BOOT/grub.cfg
sudo umount /mnt
```

**Report issue** with output from above commands.

## Advanced Options

### Skip UUID Protection (UEFI mode)

⚠️ **Warning**: USB will always reinstall!

```bash
SKIP_UUID_PROTECTION=1 sudo ./create-uefi-autoinstall-proxmox-usb.sh ...
```

Use cases:
- Testing installation multiple times
- Creating installation media for multiple systems

### Auto-confirm (skip prompts)

```bash
AUTO_CONFIRM=1 sudo ./create-uefi-autoinstall-proxmox-usb.sh ...
```

## Related Documentation

- **[Quick Start Guide](quick-start.md)** - Fast-track to installation
- **[Reinstall Prevention](reinstall-prevention.md)** - How UUID protection works (UEFI only)
- **[Main README](../../README.md)** - Project overview
- **[answer.toml](../../answer.toml)** - Configuration file reference

## Support

For issues:
1. Check [Troubleshooting](#troubleshooting) section above
2. Review script output for error messages
3. Verify all prerequisites are installed
4. Check [Proxmox Auto-Install Documentation](https://pve.proxmox.com/wiki/Automated_Installation)
