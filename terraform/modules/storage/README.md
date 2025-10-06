# Storage Module

Manages Proxmox storage pools for home lab infrastructure on Dell XPS L701X with optimized SSD/HDD allocation strategy.

## Architecture

```
Dell XPS L701X Storage:
├── SSD 180 GB (fast)           → local-lvm (LVM-Thin)
│   ├── Production VMs          → OPNsense (32 GB)
│   ├── Database LXC            → PostgreSQL (8 GB), Redis (4 GB)
│   ├── Web Services LXC        → Nextcloud (20 GB), Gitea (8 GB)
│   └── Critical LXC            → Home Assistant, Grafana, Prometheus
│
└── HDD 500 GB (slow)           → local-hdd (Directory)
    ├── VM Templates            → ~50 GB
    ├── LXC Templates           → ~20 GB
    ├── Backups                 → ~200 GB
    ├── ISO Images              → ~30 GB
    └── Reserved                → ~100 GB
```

## Storage Strategy

### SSD 180GB - Production (local-lvm)

**Type:** LVM-Thin (thin provisioning)
**Purpose:** High-performance production workloads
**Content:** VM disk images, LXC root filesystems

**Allocation:**
- OPNsense VM: 32 GB
- PostgreSQL LXC: 8 GB
- Redis LXC: 4 GB
- Nextcloud LXC: 20 GB
- Gitea LXC: 8 GB
- Home Assistant LXC: 8 GB
- Grafana LXC: 8 GB
- Prometheus LXC: 16 GB
- Nginx Proxy LXC: 4 GB
- Docker LXC: 20 GB
- **Total:** ~128 GB
- **Free:** ~52 GB (for growth)

### HDD 500GB - Templates/Backups (local-hdd)

**Type:** Directory storage
**Purpose:** Cold storage, templates, backups
**Content:** Backups, ISO images, LXC templates, snippets

**Allocation:**
- VM Templates: ~50 GB
- LXC Templates: ~20 GB
- Weekly Backups: ~200 GB
- ISO Images: ~30 GB
- Snippets/Scripts: ~5 GB
- **Total:** ~305 GB
- **Free:** ~195 GB (for additional backups)

## Usage

```hcl
module "storage" {
  source = "../../modules/storage"

  # Node configuration
  node_name = var.proxmox_node_name

  # SSD storage (production)
  enable_ssd_storage = true
  ssd_storage_id     = "local-lvm"
  ssd_size_gb        = 180

  # HDD storage (templates/backups)
  enable_hdd_storage = true
  hdd_storage_id     = "local-hdd"
  hdd_mount_point    = "/mnt/hdd"
  hdd_size_gb        = 500

  # Backup retention policy
  enable_backup_pruning = true
  backup_keep_last      = 3
  backup_keep_daily     = 7
  backup_keep_weekly    = 4
  backup_keep_monthly   = 6
  backup_keep_yearly    = 1

  # Storage allocation strategy
  storage_strategy = {
    ssd_for_production = true
    hdd_for_templates  = true
    hdd_for_backups    = true
    ssd_for_databases  = true
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| node_name | Proxmox node name | `string` | n/a | yes |
| enable_ssd_storage | Enable SSD storage | `bool` | `true` | no |
| ssd_storage_id | SSD storage ID | `string` | `"local-lvm"` | no |
| ssd_size_gb | SSD size in GB | `number` | `180` | no |
| enable_hdd_storage | Enable HDD storage | `bool` | `true` | no |
| hdd_storage_id | HDD storage ID | `string` | `"local-hdd"` | no |
| hdd_mount_point | HDD mount point | `string` | `"/mnt/hdd"` | no |
| hdd_size_gb | HDD size in GB | `number` | `500` | no |
| enable_backup_pruning | Enable backup pruning | `bool` | `true` | no |
| backup_keep_last | Keep last N backups | `number` | `3` | no |
| backup_keep_daily | Keep daily backups | `number` | `7` | no |
| backup_keep_weekly | Keep weekly backups | `number` | `4` | no |
| backup_keep_monthly | Keep monthly backups | `number` | `6` | no |
| backup_keep_yearly | Keep yearly backups | `number` | `1` | no |

## Outputs

| Name | Description |
|------|-------------|
| ssd_storage_id | SSD storage datastore ID |
| hdd_storage_id | HDD storage datastore ID |
| storage_summary | Complete storage configuration |
| storage_strategy | Storage allocation strategy |
| backup_retention | Backup retention policy |
| capacity_planning | Storage capacity planning info |

## Prerequisites

### 1. SSD Storage (local-lvm)

Created automatically during Proxmox installation:

```bash
# Verify SSD storage
pvesm status | grep local-lvm
lvs

# Check capacity
pvesm list local-lvm
```

### 2. HDD Storage (local-hdd)

Must be created manually before Terraform:

```bash
# 1. Identify HDD device
lsblk
fdisk -l

# 2. Create partition (if needed)
fdisk /dev/sdb
# n → p → 1 → default → default → w

# 3. Format partition
mkfs.ext4 /dev/sdb1

# 4. Create mount point
mkdir -p /mnt/hdd

# 5. Get UUID
blkid /dev/sdb1

# 6. Add to /etc/fstab
echo "UUID=<uuid> /mnt/hdd ext4 defaults 0 2" >> /etc/fstab

# 7. Mount
mount -a
df -h /mnt/hdd

# 8. Create Proxmox storage structure
mkdir -p /mnt/hdd/{dump,images,template/{iso,cache},snippets}

# 9. Add storage to Proxmox
pvesm add dir local-hdd --path /mnt/hdd --content backup,iso,vztmpl,snippets
```

Or use Ansible role (recommended):

```bash
ansible-playbook -i inventory/production/hosts.yml playbooks/proxmox-setup.yml --tags storage
```

## Storage Operations

### Check Storage Status

```bash
# List all storage
pvesm status

# Check specific storage
pvesm status -storage local-lvm
pvesm status -storage local-hdd

# Check disk usage
df -h /mnt/hdd
lvs
```

### Create Backup

```bash
# Backup VM to HDD
vzdump 100 --storage local-hdd --mode snapshot

# Backup LXC to HDD
vzdump 200 --storage local-hdd --mode snapshot

# Backup all VMs
for vmid in $(qm list | awk 'NR>1 {print $1}'); do
  vzdump $vmid --storage local-hdd --mode snapshot
done

# Backup all LXC
for ctid in $(pct list | awk 'NR>1 {print $1}'); do
  vzdump $ctid --storage local-hdd --mode snapshot
done
```

### Restore Backup

```bash
# List backups
pvesm list local-hdd --content backup

# Restore VM
qmrestore /mnt/hdd/dump/vzdump-qemu-100-*.vma.zst 100 --storage local-lvm

# Restore LXC
pct restore 200 /mnt/hdd/dump/vzdump-lxc-200-*.tar.zst --storage local-lvm
```

### Manage Templates

```bash
# Download LXC template to HDD
pveam update
pveam available
pveam download local-hdd debian-12-standard_12.7-1_amd64.tar.zst

# List templates
pveam list local-hdd

# Upload ISO to HDD
cd /mnt/hdd/template/iso
wget https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso
```

## Backup Retention Policy

Default retention (configured via module):

```
keep_last    = 3   # Keep last 3 backups
keep_daily   = 7   # Keep 1 week of daily backups
keep_weekly  = 4   # Keep 1 month of weekly backups
keep_monthly = 6   # Keep 6 months of monthly backups
keep_yearly  = 1   # Keep 1 year backup
```

Apply retention:

```bash
# Manual pruning
pvepurge --storage local-hdd --type qemu --keep-last 3

# Automatic pruning (via Proxmox scheduled backups)
# Datacenter → Backup → Add
# Storage: local-hdd
# Retention: As configured in module
```

## Performance Tuning

### SSD Optimizations

```bash
# Check SSD TRIM support
fstrim -v /

# Enable periodic TRIM (already enabled in Proxmox)
systemctl status fstrim.timer

# Check I/O scheduler (should be 'mq-deadline' or 'none' for SSD)
cat /sys/block/sda/queue/scheduler

# LVM thin pool monitoring
lvs -o +data_percent,metadata_percent
```

### HDD Optimizations

```bash
# Disable SSD optimizations for HDD
# Mount options in /etc/fstab should include: defaults,noatime

# Check HDD health
smartctl -a /dev/sdb

# Monitor I/O
iostat -x 1 /dev/sdb
```

## Monitoring

### Storage Capacity Alerts

Monitor via Proxmox Web UI or Prometheus:

```bash
# Check storage usage
pvesm status

# Alert if > 80% full
pvesm status | awk '$3 > 0 && ($4/$3)*100 > 80 {print $1, "is", ($4/$3)*100 "% full"}'
```

### Backup Monitoring

```bash
# List recent backups
pvesm list local-hdd --content backup

# Check backup age
find /mnt/hdd/dump -name "*.vma.zst" -mtime +7  # Older than 7 days

# Monitor backup size
du -sh /mnt/hdd/dump/*
```

## Troubleshooting

### HDD Not Mounted

```bash
# Check mount status
mount | grep /mnt/hdd
df -h | grep hdd

# Remount
mount -a

# Check fstab
cat /etc/fstab | grep hdd
```

### Storage Full

```bash
# Check usage
df -h /mnt/hdd
pvesm status -storage local-hdd

# Find large files
du -h /mnt/hdd | sort -rh | head -20

# Clean old backups manually
rm /mnt/hdd/dump/vzdump-*.vma.zst.<old-date>

# Or use pruning
pvepurge --storage local-hdd --type qemu --dry-run
```

### LVM Thin Pool Full

```bash
# Check thin pool usage
lvs -o +data_percent,metadata_percent

# If > 90%, need to extend or remove VMs/LXC
# Cannot extend on Dell XPS (SSD is fixed size)

# Free space by removing old VMs
qm list
qm destroy <vmid>

# Or migrate to HDD storage
qm migrate <vmid> <node> --targetstorage local-hdd
```

## Best Practices

1. **SSD for Performance**
   - Production VMs (OPNsense)
   - Database LXC (PostgreSQL, Redis)
   - Frequently accessed services

2. **HDD for Capacity**
   - Backups (daily/weekly)
   - Templates (VM/LXC)
   - ISO images
   - Infrequently accessed data

3. **Backup Strategy**
   - Daily backups to HDD
   - Keep 7 daily, 4 weekly, 6 monthly
   - Test restore periodically
   - Consider external backup (USB/NAS)

4. **Monitoring**
   - Set alerts at 80% capacity
   - Monitor SSD health (smartctl)
   - Check backup age
   - Review prune logs

5. **Maintenance**
   - Monthly backup cleanup
   - Quarterly restore test
   - Annual storage review
   - Keep 20-30% free space on SSD

## Migration from Current Setup

If you already have VMs/LXC and want to reorganize:

```bash
# 1. Backup everything
for vmid in $(qm list | awk 'NR>1 {print $1}'); do
  vzdump $vmid --storage local-hdd
done

# 2. Create new storage structure via Terraform
terraform apply

# 3. Migrate VMs to appropriate storage
# Production → SSD
qm migrate 100 pve --targetstorage local-lvm

# Templates → HDD (already on HDD)
# No migration needed

# 4. Update VM/LXC configs
# Already done by Terraform modules
```

## References

- [Proxmox Storage](https://pve.proxmox.com/wiki/Storage)
- [LVM Thin Provisioning](https://pve.proxmox.com/wiki/Storage:_LVM_Thin)
- [Proxmox Backup](https://pve.proxmox.com/wiki/Backup_and_Restore)
- [Storage Replication](https://pve.proxmox.com/wiki/Storage_Replication)
