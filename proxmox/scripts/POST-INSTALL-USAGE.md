# proxmox-post-install.sh - Usage Guide

## Quick Reference

```bash
# Show help
bash proxmox-post-install.sh --help

# NEW system - initialize HDD automatically
bash proxmox-post-install.sh --init-hdd

# EXISTING system - preserve HDD data (default)
bash proxmox-post-install.sh
bash proxmox-post-install.sh --preserve-hdd
```

## Command Line Options

| Option | Purpose | Use Case |
|--------|---------|----------|
| `--init-hdd` | Force HDD initialization | **NEW** system setup |
| `--preserve-hdd` | Preserve existing data | **EXISTING** system (default) |
| `--help`, `-h` | Show help message | Documentation |

## When to Use Each Option

### 🆕 `--init-hdd` - New System Setup

**Use when:**
- ✅ Fresh Proxmox installation
- ✅ HDD is brand new (no data)
- ✅ HDD needs to be formatted
- ✅ You want automatic setup without prompts

**What it does:**
1. **No partition** → Creates partition + formats automatically
2. **Partition exists, no FS** → Formats automatically
3. **Data exists** → Asks for confirmation (safety!)

**Example workflow:**
```bash
# Fresh install of Proxmox
ssh root@192.168.1.100

# Upload and run script
scp proxmox-post-install.sh root@192.168.1.100:/root/
ssh root@192.168.1.100
bash proxmox-post-install.sh --init-hdd

# Script output:
# ✓ Partition created
# ✓ Formatted as ext4
# ✓ Mounted at /mnt/hdd
# ✓ Added to Proxmox as local-hdd
```

---

### 💾 Default (no flag) - Preserve Data

**Use when:**
- ✅ Reinstalling Proxmox (HDD has data to keep)
- ✅ HDD already formatted and has files
- ✅ You want to be cautious
- ✅ Migrating from another system

**What it does:**
1. **Filesystem exists** → Mounts WITHOUT formatting ✅
2. **No filesystem** → Asks before formatting
3. **No partition** → Asks before creating

**Example workflow:**
```bash
# Reinstalling Proxmox, HDD has backups/photos
ssh root@192.168.1.100

bash proxmox-post-install.sh
# or explicitly:
bash proxmox-post-install.sh --preserve-hdd

# Script output:
# ✓ Existing filesystem detected: ext4
# ✓ Preserving existing data (no formatting)
# ✓ Mounted at /mnt/hdd
#
# Existing data found on HDD:
#   backups/   45G
#   photos/    120G
#   archives/  200G
```

## Behavior Matrix

| HDD State | `--init-hdd` | Default (preserve) |
|-----------|--------------|-------------------|
| **No partition** | Auto create + format | Ask user |
| **Partition, no FS** | Auto format | Ask user |
| **Has filesystem** | Ask to erase (safety!) | Mount without formatting ✅ |

## Safety Features

### Protection Against Data Loss

1. **Default is safe**: Without flags, script NEVER formats existing data
2. **Double confirmation**: Even with `--init-hdd`, asks before erasing existing data
3. **UUID mounting**: Uses UUID instead of /dev/sdb1 (more reliable)
4. **nofail option**: System boots even if HDD fails/missing

### What Gets Asked

**With `--init-hdd` + existing data:**
```
⚠ Existing filesystem detected: ext4
⚠ --init-hdd flag set, but data exists!
ERASE all data and reformat? (yes/no):
```
→ Type `no` to preserve data

**Default mode + no filesystem:**
```
⚠ No filesystem detected
Create new filesystem? (yes/no):
```
→ Safe to type `yes` if it's new disk

## Complete Installation Workflow

### Scenario 1: Brand New System

```bash
# 1. Boot from USB, install Proxmox (wipes SSD only)
#    HDD is untouched during installation

# 2. SSH into new system
ssh root@192.168.1.100

# 3. Copy script
scp proxmox/scripts/proxmox-post-install.sh root@192.168.1.100:/root/

# 4. Run with --init-hdd
ssh root@192.168.1.100
bash proxmox-post-install.sh --init-hdd

# 5. Script configures everything:
#    ✓ Repositories
#    ✓ Network interfaces (eth-builtin, eth-usb)
#    ✓ Network bridges (vmbr0-2, vmbr99)
#    ✓ HDD formatted and mounted
#    ✓ Optimizations (KSM, USB power, laptop lid)

# 6. Reboot
systemctl reboot

# 7. Verify
pvesm status
# local-lvm   148 GB
# local-hdd   458 GB  ← Ready to use!
```

### Scenario 2: Reinstall (Preserve HDD)

```bash
# 1. Boot from USB, install Proxmox
#    ⚠️ SSD erased, HDD untouched

# 2. SSH into system
ssh root@192.168.1.100

# 3. Run WITHOUT --init-hdd
bash proxmox-post-install.sh

# 4. Script detects existing data:
#    ✓ Found ext4 filesystem
#    ✓ Preserving existing data
#    ✓ Mounted /mnt/hdd
#
# Existing data:
#   backups/   45G   ← Still there!
#   photos/    120G  ← Safe!

# 5. Verify data intact
ls -lh /mnt/hdd/
# backups/
# photos/
# archives/
```

## Troubleshooting

### "Command not found: proxmox-post-install.sh"

Make script executable:
```bash
chmod +x proxmox-post-install.sh
```

### "HDD not detected"

Check disk name:
```bash
lsblk
```

If HDD is not `/dev/sdb`, edit script:
```bash
nano proxmox-post-install.sh
# Change: HDD_DEVICE="/dev/sdb"
# To:     HDD_DEVICE="/dev/sdc"  (or whatever lsblk shows)
```

### Script asks questions even with `--init-hdd`

This is INTENTIONAL if data exists! It's a safety feature.

If HDD has data and you want to erase:
1. Script asks: "ERASE all data and reformat? (yes/no)"
2. Type: `yes`

Or manually wipe HDD first:
```bash
wipefs -a /dev/sdb
```

### Want to re-run script

Safe to re-run! Script is idempotent:
- Won't recreate existing partitions
- Won't reformat existing filesystems (unless forced)
- Won't duplicate fstab entries

```bash
# Re-run to fix partial config
bash proxmox-post-install.sh
```

## Advanced Usage

### Force complete HDD wipe

```bash
# 1. Wipe all signatures
wipefs -a /dev/sdb

# 2. Run script
bash proxmox-post-install.sh --init-hdd

# HDD will be completely clean and reformatted
```

### Use different filesystem

Edit script before running:
```bash
nano proxmox-post-install.sh

# Find: mkfs.ext4
# Replace with: mkfs.xfs
# or: mkfs.btrfs
```

### Skip HDD entirely

Just say "no" when prompted, or:
```bash
# Edit script, comment out HDD section
# Or just ignore the warnings
```

## Summary

| You want to... | Use this command |
|----------------|------------------|
| **Setup new system** | `bash proxmox-post-install.sh --init-hdd` |
| **Reinstall, keep HDD data** | `bash proxmox-post-install.sh` |
| **See all options** | `bash proxmox-post-install.sh --help` |

**Default behavior is SAFE**: preserves existing data! 🛡️
