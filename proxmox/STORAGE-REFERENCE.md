# Proxmox Storage Reference

## Storage Overview

```
Dell XPS L701X Home Lab
├── SSD 180GB → local-lvm (Fast, limited space)
└── HDD 500GB → local-hdd (Slower, bulk storage)
```

## Storage Configuration

### local-lvm (SSD - System Storage)

| Parameter | Value |
|-----------|-------|
| **Type** | LVM-Thin |
| **Device** | /dev/sda |
| **Size** | ~148 GB |
| **Speed** | ⚡ Fast (SSD) |
| **Purpose** | Production VMs & critical LXC |

**Content Types:**
- ✅ `images` - VM disks
- ✅ `rootdir` - LXC containers

**Use for:**
- OPNsense VM (firewall - needs performance)
- PostgreSQL LXC (database - I/O intensive)
- Redis LXC (cache - needs speed)
- Docker host LXC (production apps)
- Any production service

**Do NOT use for:**
- Large file storage
- Backups
- ISO images
- Test/dev VMs
- Personal files

---

### local-hdd (HDD - Bulk Storage)

| Parameter | Value |
|-----------|-------|
| **Type** | Directory |
| **Device** | /dev/sdb1 |
| **Mount** | /mnt/hdd |
| **Size** | 500 GB |
| **Speed** | 💾 Slower (HDD) |
| **Purpose** | Backups, templates, bulk data |

**Content Types:**
- ✅ `backup` - VM/LXC backups
- ✅ `iso` - ISO images
- ✅ `vztmpl` - LXC templates
- ✅ `rootdir` - LXC container disks
- ✅ `images` - **VM disks & templates** ⭐
- ✅ `snippets` - Hook scripts

**Use for:**
- **VM Templates** (for cloning!)
- VM/LXC backups
- ISO images
- LXC templates
- Non-critical LXC containers:
  - Nextcloud (large files)
  - Gitea (repositories)
  - Home Assistant
  - Grafana
  - Prometheus (metrics)
- Personal files:
  - Photos
  - Archives
  - Documents

**Directory Structure:**
```
/mnt/hdd/
├── backups/    - Automated VM/LXC backups
├── images/     - VM disk images & templates ⭐
├── iso/        - Operating system ISOs
├── templates/  - LXC templates (.tar.gz)
├── snippets/   - Hook scripts and configs
├── photos/     - Personal photos
└── archives/   - Long-term storage
```

## Content Type Matrix

| Content Type | local-lvm (SSD) | local-hdd (HDD) | Purpose |
|--------------|-----------------|-----------------|---------|
| **backup** | ❌ | ✅ | VM/LXC backups |
| **iso** | ❌ | ✅ | ISO images |
| **vztmpl** | ❌ | ✅ | LXC templates |
| **rootdir** | ✅ | ✅ | LXC container disks |
| **images** | ✅ | ✅ | VM disk images |
| **snippets** | ❌ | ✅ | Hook scripts |

## Usage Recommendations

### Create VM

```bash
# Production VM → SSD
qm create 100 --name opnsense --storage local-lvm

# Testing VM → HDD
qm create 200 --name test-vm --storage local-hdd

# Template → HDD (then clone to SSD)
qm create 100 --name ubuntu-template --storage local-hdd
```

### Create LXC

```bash
# Critical service → SSD
pct create 200 local:vztmpl/debian-12.tar.zst \
  --hostname postgresql \
  --rootfs local-lvm:8

# Non-critical service → HDD
pct create 300 local:vztmpl/debian-12.tar.zst \
  --hostname nextcloud \
  --rootfs local-hdd:20
```

### Backup

```bash
# Always backup to HDD
vzdump 100 --storage local-hdd --mode snapshot

# Or configure in Web UI:
# Datacenter → Backup → Add
# Storage: local-hdd
```

### Templates

```bash
# Create template on HDD
qm create 100 --storage local-hdd
# ... configure ...
qm template 100

# Clone to SSD for production
qm clone 100 201 --full --storage local-lvm

# Clone to HDD for testing
qm clone 100 202 --full --storage local-hdd
```

## Storage Commands

### Check Status

```bash
# Show all storage
pvesm status

# Show content of storage
pvesm list local-lvm
pvesm list local-hdd

# Show disk usage
df -h /mnt/hdd
lvs
```

### Move VM Disk

```bash
# Move VM 100 disk 0 from SSD to HDD
qm move-disk 100 scsi0 local-hdd

# Move from HDD to SSD
qm move-disk 200 scsi0 local-lvm
```

### Clean Up

```bash
# Remove old backups (30+ days)
find /mnt/hdd/dump -name "*.zst" -mtime +30 -delete

# Remove unused VM disks (orphaned)
# Web UI: Storage → local-hdd → Content
# Select unused → Remove

# Check for orphaned disks
qm rescan --vmid all
```

## Capacity Planning

### SSD (148 GB)

| Service | Size | Total |
|---------|------|-------|
| OPNsense VM | 32 GB | 32 GB |
| PostgreSQL LXC | 8 GB | 40 GB |
| Redis LXC | 4 GB | 44 GB |
| NPM LXC | 8 GB | 52 GB |
| Docker LXC | 16 GB | 68 GB |
| **Reserve** | **80 GB** | **148 GB** |

### HDD (500 GB)

| Category | Estimated | Notes |
|----------|-----------|-------|
| Templates | 50 GB | 5-10 templates |
| Backups | 100 GB | Automated weekly |
| ISO images | 30 GB | OS installers |
| LXC containers | 100 GB | Nextcloud, Gitea, etc. |
| Personal files | 200 GB | Photos, archives |
| **Reserve** | **20 GB** | |
| **Total** | **500 GB** | |

## Best Practices

### ✅ Do

1. **Store templates on HDD**
   - Saves SSD space
   - Clone to SSD for production

2. **Use SSD for production**
   - Better performance
   - Lower latency

3. **Backup everything to HDD**
   - Automated backups
   - Safe storage

4. **Monitor usage**
   ```bash
   pvesm status
   df -h /mnt/hdd
   ```

5. **Clean old backups**
   - Keep only recent
   - Archive important ones

### ❌ Don't

1. **Don't fill SSD completely**
   - Keep 20+ GB free
   - LVM needs free space

2. **Don't store backups on SSD**
   - Waste of fast storage
   - Risk of data loss

3. **Don't run heavy I/O on HDD**
   - Databases on SSD
   - Caches on SSD

4. **Don't ignore monitoring**
   - Check usage weekly
   - Clean up proactively

## Troubleshooting

### "Storage full"

**SSD full:**
```bash
# Move non-critical VMs to HDD
qm move-disk <vmid> scsi0 local-hdd

# Remove old snapshots
qm delsnapshot <vmid> <snapshot-name>
```

**HDD full:**
```bash
# Remove old backups
find /mnt/hdd/dump -mtime +30 -delete

# Clean personal files
rm -rf /mnt/hdd/archives/old/*
```

### "Cannot create VM"

**Check available space:**
```bash
pvesm status
```

**Choose different storage:**
- Create on HDD instead
- Free up SSD space

### "Backup failed"

**Check HDD space:**
```bash
df -h /mnt/hdd
```

**Clean old backups:**
```bash
cd /mnt/hdd/dump
ls -lh
rm vzdump-qemu-*.zst
```

## Configuration Files

### /etc/pve/storage.cfg

```conf
dir: local-hdd
    path /mnt/hdd
    content backup,iso,vztmpl,rootdir,images,snippets
    maxfiles 3
    prune-backups keep-all=1,keep-daily=7,keep-weekly=4

lvmthin: local-lvm
    thinpool data
    vgname pve
    content images,rootdir
```

### /etc/fstab (HDD mount)

```conf
UUID=xxxx-xxxx-xxxx /mnt/hdd ext4 defaults,nofail 0 2
```

## Summary

| Feature | SSD (local-lvm) | HDD (local-hdd) |
|---------|-----------------|-----------------|
| **Size** | 148 GB | 500 GB |
| **Speed** | ⚡ Fast | 💾 Slow |
| **Best for** | Production VMs | Templates, backups |
| **VM disks** | ✅ | ✅ |
| **LXC disks** | ✅ | ✅ |
| **Templates** | ❌ | ✅ ⭐ |
| **Backups** | ❌ | ✅ |
| **ISO** | ❌ | ✅ |
| **Personal files** | ❌ | ✅ |

**Rule of thumb:**
- Production → SSD
- Everything else → HDD
- Templates → HDD, clone to SSD
