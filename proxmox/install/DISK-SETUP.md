# Disk Setup for Proxmox Installation

## Overview

This automated installation is configured for **dual-disk setup**:

```
Dell XPS L701X:
├── SSD 180GB (/dev/sda)  → System disk [WILL BE ERASED]
└── HDD 500GB (/dev/sdb)  → Data disk [PRESERVED]
```

## What Happens During Installation

### Phase 1: Automated Installation (via answer.toml)

**SSD (`/dev/sda`) - COMPLETE ERASURE**
- ⚠️ All data will be destroyed
- Proxmox system installed
- LVM configured:
  - Swap: 8 GB (1x RAM)
  - Root: 20 GB (Proxmox OS)
  - Minfree: 4 GB (snapshots reserve)
  - Data (VMs/LXC): ~148 GB

**HDD (`/dev/sdb`) - UNTOUCHED**
- ✅ Completely ignored by installer
- ✅ All data remains safe
- ✅ Backups, photos, archives preserved

### Phase 2: Post-Installation (proxmox-post-install.sh)

**HDD Configuration - SMART DETECTION or FORCED INIT**

Run the script with appropriate flag:

```bash
# NEW system - automatically initialize HDD
bash proxmox-post-install.sh --init-hdd

# EXISTING system - preserve data (default)
bash proxmox-post-install.sh
```

**Default mode (preserve data):**

1. **Check if HDD has existing filesystem:**
   ```bash
   ✓ Existing filesystem detected: ext4
   ✓ Preserving existing data (no formatting)
   ```
   → Mounts WITHOUT formatting

2. **If no filesystem found:**
   ```bash
   ⚠ No filesystem detected
   Create new filesystem? (yes/no)
   ```
   → Asks before formatting

**Init mode (`--init-hdd` flag):**

1. **No partition:**
   ```bash
   Creating partition and formatting (auto mode)...
   ✓ Partition created
   ✓ ext4 filesystem created
   ```
   → Automatic setup

2. **Partition exists but no filesystem:**
   ```bash
   Creating ext4 filesystem (auto mode)...
   ✓ Formatted automatically
   ```
   → No questions asked

3. **Existing data detected:**
   ```bash
   ⚠ Existing filesystem detected: ext4
   ⚠ --init-hdd flag set, but data exists!
   ERASE all data and reformat? (yes/no)
   ```
   → Safety prompt (prevents accidental data loss)

**Both modes then:**

3. **Mount and Configure:**
   - Create mount point: `/mnt/hdd`
   - Use UUID-based mounting (reliable)
   - Add to `/etc/fstab` with `nofail` option
   - Add to Proxmox as `local-hdd` storage
   - Create directories:
     - `backups/` - VM/LXC backups
     - `photos/` - Personal photos
     - `archives/` - Long-term storage
     - `iso/` - ISO images
     - `templates/` - LXC templates

## Configuration Files

### answer.toml
```toml
[disk-setup]
disk_list = ["sda"]  # ← Only SSD! HDD omitted
```

### /etc/fstab (after post-install)
```bash
# UUID-based mounting (reliable)
UUID=xxxx-xxxx-xxxx /mnt/hdd ext4 defaults,nofail 0 2
```

## Storage Layout After Installation

### SSD (`local-lvm`)
```
/dev/sda (180 GB)
├── EFI partition (512 MB)
├── Swap (8 GB)
└── LVM
    ├── pve-root (20 GB) - Proxmox OS
    └── pve-data (~148 GB) - VMs, critical LXC
```

**Usage:**
- OPNsense VM
- Critical services (high performance)

### HDD (`local-hdd`)
```
/dev/sdb1 → /mnt/hdd
├── backups/    - Automated backups
├── photos/     - Personal data
├── archives/   - Long-term storage
├── iso/        - Operating system ISOs
└── templates/  - LXC templates
```

**Usage:**
- VM/LXC backups
- ISO storage
- Personal files
- Non-critical LXC containers

## Verification After Installation

### 1. Check HDD Mount
```bash
df -h /mnt/hdd
```

Expected output:
```
Filesystem      Size  Used Avail Use% Mounted on
/dev/sdb1       458G  XXG  XXG   XX% /mnt/hdd
```

### 2. Check Existing Data
```bash
ls -lh /mnt/hdd/
```

Your files should be intact!

### 3. Check Proxmox Storage
```bash
pvesm status
```

Expected:
```
Name         Type     Status  Total    Used  Available
local-lvm    lvmthin  active  148 GB   ...   ...
local-hdd    dir      active  458 GB   ...   ...
```

## Important Notes

### ⚠️ Before Installation
1. **Backup critical data** from SSD (it will be erased!)
2. **Verify HDD contents** (should be preserved, but safety first)
3. **Check disk names** with `lsblk` (may differ: sda/sdb/nvme0n1)

### ✅ Data Safety
- HDD is never formatted if filesystem exists
- UUID-based mounting prevents wrong disk mounting
- `nofail` option in fstab - system boots even if HDD fails
- Post-install script asks before ANY destructive operation

### 🔧 Customization

**Different disk names?**

Edit in `answer.toml`:
```toml
disk_list = ["nvme0n1"]  # For NVMe SSD
```

Edit in `proxmox-post-install.sh`:
```bash
HDD_DEVICE="/dev/sdc"  # If HDD is on different device
```

**Single disk setup?**

Just ignore HDD warnings - everything still works!

## Troubleshooting

### "HDD not detected"
- Normal if HDD not connected
- Normal if single-disk setup
- Re-run `proxmox-post-install.sh` after connecting HDD

### "Failed to mount HDD"
- Check `dmesg` for disk errors
- Verify filesystem: `blkid /dev/sdb1`
- Manual mount: `mount /dev/sdb1 /mnt/hdd`

### "Partition exists but no filesystem"
- HDD has partition table but not formatted
- Script will ask to format
- Say 'yes' only if it's a new disk!

## Summary

| Disk | Size | Installation | Post-Install | Data |
|------|------|-------------|--------------|------|
| **SSD** | 180GB | ❌ ERASED | ✅ System | Lost |
| **HDD** | 500GB | ✅ IGNORED | ✅ Mounted | **SAFE** |

**Your data on HDD is safe!** 🎉
