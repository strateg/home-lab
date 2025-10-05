# Proxmox VE 9 - Automated Installation USB

## ✅ The Correct Method (Proxmox 8+)

Starting with Proxmox VE 8, automated installation is **built directly into the installer ISO**. No extra packages or tools needed!

### How It Works

1. Write Proxmox ISO to USB with `dd` (preserves hybrid boot structure)
2. Add `auto-installer.yaml` to `/proxmox/` folder on the FAT32 partition
3. Boot from USB and press **`a`** to start automated installation

That's it! No ISO rebuilding, no manual GRUB editing, no special tools.

---

## Quick Start

### Prerequisites

- USB drive (8GB+ recommended)
- Proxmox VE 9 ISO file
- Ubuntu/Debian machine to create the USB

### Create the USB

```bash
# Run the script
sudo ./create-proxmox-usb.sh /dev/sdX path/to/proxmox.iso
```

Replace:
- `/dev/sdX` with your USB device (e.g., `/dev/sdb`)
- `path/to/proxmox.iso` with path to your Proxmox ISO

### Boot and Install

1. **Connect external monitor** to Mini DisplayPort (for Dell XPS L701X)
2. **Insert USB** and boot from it (F12 → select `UEFI: USB...`)
3. **Press `a`** at the installer menu to start automated installation
4. **Wait ~10-15 minutes** for installation to complete
5. **System reboots** automatically when done

---

## Configuration File

The script uses `auto-installer.yaml` for configuration:

```yaml
install:
  target_disk: /dev/sda          # SSD for Proxmox
  filesystem: ext4
  country: EE
  timezone: Europe/Tallinn
  keyboard: us
  root_password: "Homelab2025!"
  management_interface: auto      # Auto-detect network interface
  hostname: proxmox
  domain: home.lan
  ipconfig:
    mode: dhcp                    # Use DHCP for initial setup
  disk_options:
    swapsize: 8                   # 8GB swap (1x RAM)
    maxroot: 30                   # 30GB root partition
    minfree: 8                    # 8GB free space
    maxvz: 0                      # Rest for VM storage
```

### Customize for Your Setup

Edit `auto-installer.yaml` before running the script:

**For static IP:**
```yaml
ipconfig:
  ip: 192.168.1.100/24
  gw: 192.168.1.1
  dns: 8.8.8.8
```

**For different location:**
```yaml
country: RU
timezone: Europe/Moscow
```

**For different disk:**
```yaml
target_disk: /dev/nvme0n1  # For NVMe SSD
```

---

## Dell XPS L701X Specific Notes

### External Display Support

The script automatically adds graphics parameters to GRUB:
```
video=vesafb:ywrap,mtrr vga=791 nomodeset
```

This enables the Mini DisplayPort output during installation.

### Network Adapters

The laptop has two network interfaces:
- **Built-in Ethernet** - Used during installation
- **USB-Ethernet adapter** - Configure post-installation

The installer will auto-detect and use the first available interface.

### Disk Layout

- **SSD 250GB** (`/dev/sda`) - Proxmox system
  - 30GB root
  - 8GB swap
  - ~200GB VM storage
- **HDD 500GB** (`/dev/sdb`) - Add to Proxmox storage post-install

---

## After Installation

### Find IP Address

Check your router's DHCP leases or use:
```bash
nmap -sn 192.168.1.0/24 | grep -B 2 Proxmox
```

### First Login

```bash
ssh root@<ip-address>
# Password: Homelab2025!
```

### Web Interface

Open browser:
```
https://<ip-address>:8006
```

Login:
- Username: `root`
- Password: `Homelab2025!`

### Run Post-Install Script

```bash
# Script is copied to USB at /proxmox/proxmox-post-install.sh
# You can access it from the Proxmox system
bash /proxmox/proxmox-post-install.sh
```

Or upload it:
```bash
scp proxmox-post-install.sh root@<ip-address>:/root/
ssh root@<ip-address>
bash /root/proxmox-post-install.sh
```

---

## Troubleshooting

### Auto-Install Doesn't Start

**Problem**: Installer waits for input instead of starting automatically

**Solution**: You must press **`a`** at the installer menu to trigger automated installation

**Alternative**: Add boot parameter to auto-start:
- Edit GRUB manually (not needed for first install)
- Or use the script's GRUB modification feature

### External Display Stays Black

**Problem**: Can't see installer on external monitor

**Solution**: Graphics parameters should be automatically added by the script

**Verify**:
```bash
# Check GRUB has graphics parameters
sudo mount /dev/sdX2 /mnt
grep "video=vesafb" /mnt/boot/grub/grub.cfg
sudo umount /mnt
```

### USB Doesn't Boot

**Problem**: System doesn't boot from USB

**Solutions**:
- Make sure to select **`UEFI: USB...`** (NOT "USB Storage Device")
- Disable Secure Boot in BIOS if enabled
- Try different USB port

### Installation Fails

**Problem**: Installation stops with error

**Common causes**:
- Wrong disk specified in `auto-installer.yaml` (check with `lsblk`)
- Network not connected (installer needs network)
- Corrupted ISO file (verify checksum)

### YAML Syntax Error

**Problem**: "Could not parse auto-installer.yaml"

**Solution**: Validate YAML syntax:
```bash
# Check for tabs (YAML requires spaces)
cat -A auto-installer.yaml

# Fix indentation (use 2 spaces, not tabs)
```

---

## Technical Details

### What the Script Does

1. **Writes ISO with `dd`**
   - Preserves hybrid boot structure (MBR + GPT + EFI)
   - Creates bootable USB exactly like balenaEtcher
   - No ISO rebuilding that could break boot

2. **Mounts FAT32 EFI partition**
   - This partition is writable (unlike ISO9660)
   - Located at partition 2 (usually `/dev/sdX2`)

3. **Adds configuration files**
   - `/proxmox/auto-installer.yaml` - Installation config
   - `/proxmox/proxmox-post-install.sh` - Optional post-install script

4. **Modifies GRUB**
   - Adds graphics parameters to all boot entries
   - Enables external display support
   - Doesn't break boot chain

5. **Verifies and unmounts**
   - Ensures all changes are written
   - Safe removal

### Why This Works

✅ Uses Proxmox's **built-in auto-installer** (no extra tools)
✅ Only modifies **writable partition** (no ISO rebuilding)
✅ Preserves **hybrid boot structure** (dd write)
✅ Simple and **officially supported** method

### Why Previous Attempts Failed

❌ **ISO rebuild with xorriso** - Broke hybrid boot structure
❌ **Manual GRUB replacement** - Broke boot chain
❌ **Modifying read-only partition** - ISO9660 is read-only
❌ **Non-existent tools** - `proxmox-auto-install-assistant` not in public repos

---

## Files in This Repository

- **`create-proxmox-usb.sh`** - Main USB creation script ⭐
- **`auto-installer.yaml`** - Installation configuration
- **`proxmox-post-install.sh`** - Post-installation script
- **`README-AUTOINSTALL.md`** - This file

### Legacy Files (Reference Only)

These scripts were attempts to solve the problem but don't work correctly:
- `create-proxmox-usb-official.sh` - Used non-existent tool
- `create-proxmox-usb-complete.sh` - Broke GRUB boot chain
- `create-proxmox-usb-simple.sh` - Auto-install didn't trigger
- `prepare-proxmox-usb-*.sh` - Various failed approaches

See `SOLUTION-COMPARISON.md` for detailed analysis.

---

## Summary

```bash
# 1. Create USB
sudo ./create-proxmox-usb.sh /dev/sdX proxmox.iso

# 2. Boot from USB (F12 → UEFI: USB)

# 3. Press 'a' at installer menu

# 4. Wait 10-15 minutes

# 5. Login and configure
ssh root@<ip-address>
```

**This is the correct, working method for Proxmox 8+.** 🎉
