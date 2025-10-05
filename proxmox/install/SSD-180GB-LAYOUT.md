# SSD 180GB - Disk Layout Calculation

## Configuration for Dell XPS L701X with 180GB SSD

### LVM Parameters (answer.toml)

```toml
lvm.swapsize = 8    # 8 GB  (1x RAM)
lvm.maxroot = 20    # 20 GB (Proxmox OS)
lvm.minfree = 4     # 4 GB  (snapshots reserve)
lvm.maxvz = 0       # Use all remaining space
```

### Partition Layout

| Partition | Size | Purpose | Type |
|-----------|------|---------|------|
| **EFI** | ~512 MB | Boot partition | FAT32 |
| **LVM** | ~179.5 GB | Proxmox volumes | LVM |
| └─ **Swap** | 8 GB | Virtual memory | Swap |
| └─ **Root** | 20 GB | Proxmox OS + packages | ext4 |
| └─ **Minfree** | 4 GB | Reserved (snapshots) | - |
| └─ **Data** | **~148 GB** | VMs & LXC | LVM-thin |

### Calculation

```
Total SSD:        180 GB
- EFI:           -0.5 GB
───────────────────────
LVM available:   179.5 GB

LVM breakdown:
- Swap:            8 GB
- Root:           20 GB
- Minfree:         4 GB
───────────────────────
Reserved:         32 GB

Available for VMs: 179.5 - 32 = ~148 GB
```

## Storage Distribution

### local-lvm (SSD - Fast)

**Total: ~148 GB available**

Recommended allocation:
- **OPNsense VM**: 32 GB
  - CPU: 2 cores
  - RAM: 2 GB
  - Disk: 32 GB (on SSD for performance)

- **Critical LXC**: ~30-50 GB total
  - PostgreSQL: 8 GB
  - Redis: 4 GB
  - Nginx Proxy Manager: 8 GB
  - Docker Host: 16 GB

- **Reserve**: ~60-80 GB
  - For additional VMs
  - Temporary containers
  - Snapshots (requires extra space)

### local-hdd (HDD - Bulk storage)

**Total: 500 GB**

Usage:
- VM/LXC backups (automated)
- ISO images
- LXC templates
- Non-critical containers:
  - Nextcloud (large files)
  - Gitea (repositories)
  - Home Assistant
  - Grafana
  - Prometheus (metrics data)
- Personal data:
  - Photos
  - Archives
  - Documents

## Comparison: 180GB vs 250GB SSD

| Metric | 180 GB SSD | 250 GB SSD | Difference |
|--------|------------|------------|------------|
| **Total** | 180 GB | 250 GB | -70 GB |
| **Swap** | 8 GB | 8 GB | same |
| **Root** | 20 GB | 30 GB | -10 GB |
| **Minfree** | 4 GB | 8 GB | -4 GB |
| **VM Space** | **~148 GB** | **~204 GB** | **-56 GB** |

### Impact Assessment

✅ **Still sufficient for Home Lab!**

**Why it's OK:**
- OPNsense VM only needs 32 GB
- Critical services on SSD: ~50 GB
- Remaining ~66 GB for flexibility
- **HDD handles bulk storage** (Nextcloud, media, backups)

**Optimization tips:**
- Store large LXC on HDD
- Move ISO files to HDD
- Use HDD for Nextcloud data
- Keep only active VMs on SSD

## Example Layout

### Option 1: Minimal (Safe)
```
SSD (148 GB):
├── OPNsense VM       32 GB  ████████
├── PostgreSQL LXC     8 GB  ██
├── Redis LXC          4 GB  █
├── NPM LXC            8 GB  ██
├── Docker LXC        16 GB  ████
└── Reserve           80 GB  ████████████████████

HDD (500 GB):
├── Backups          100 GB
├── Nextcloud LXC     50 GB
├── Gitea LXC         20 GB
├── Home Assistant    10 GB
├── Grafana           10 GB
├── Prometheus        30 GB
├── Photos/Archives  200 GB
└── ISO/Templates     80 GB
```

### Option 2: Aggressive (Max VMs on SSD)
```
SSD (148 GB):
├── OPNsense VM       32 GB
├── Database VMs      40 GB
├── Web Services      40 GB
├── Test VMs          20 GB
└── Reserve           16 GB  (minimal but workable)

HDD (500 GB):
├── All LXC containers
├── All backups
├── Personal data
```

## Monitoring Free Space

### Check SSD usage:
```bash
pvesm status | grep local-lvm
lvs
```

### Check HDD usage:
```bash
df -h /mnt/hdd
```

### Warning thresholds:
- **SSD < 20 GB free**: Move some containers to HDD
- **SSD < 10 GB free**: Critical! Clean up immediately
- **HDD < 50 GB free**: Clean old backups

## Conclusion

**180 GB SSD is sufficient for this Home Lab setup!**

Key points:
✅ Proxmox fits comfortably (20 GB root)
✅ OPNsense VM fits (32 GB)
✅ Space for 4-6 LXC containers on SSD
✅ HDD handles bulk storage (500 GB)
✅ Total usable: 148 GB (SSD) + 500 GB (HDD) = 648 GB

**Trade-off vs 250GB:**
- Less space for VMs on fast SSD (-56 GB)
- More important to use HDD wisely
- Still plenty for a home lab environment

**Recommendation:**
Use the configuration as-is. It's well-balanced for your hardware!
