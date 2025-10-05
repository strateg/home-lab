# Proxmox LXC Automation System

Automated template creation and service deployment using Proxmox VE Community Scripts.

## Architecture

```
Templates (HDD)           Services (SSD/HDD)
ID 900-999                ID 200-299

┌─────────────────┐      ┌──────────────────┐
│ 900: PostgreSQL │─────→│ 200: PostgreSQL  │
│ 901: Redis      │─────→│ 201: Redis       │
│ 902: Nextcloud  │─────→│ 202: Nextcloud   │
│ 903: Gitea      │─────→│ 203: Gitea       │
│ 904: HomeAssist │─────→│ 204: HomeAssist  │
│ 905: Grafana    │─────→│ 205: Grafana     │
│ 906: Prometheus │─────→│ 206: Prometheus  │
│ 907: NPM        │─────→│ 207: NPM         │
│ 908: Docker     │─────→│ 208: Docker      │
└─────────────────┘      └──────────────────┘
     Templates                Services
    (on HDD)              (cloned to SSD)
```

## Directory Structure

```
proxmox/scripts/
├── lib/
│   └── common-functions.sh        # Shared library functions
├── templates/
│   ├── create-all-templates.sh    # Create all templates
│   └── create-postgresql-template.sh  # Individual template
├── services/
│   ├── deploy-postgresql.sh       # Deploy PostgreSQL
│   ├── deploy-redis.sh            # Deploy Redis
│   └── deploy-docker.sh           # Deploy Docker
└── deploy-all-services.sh         # Deploy all services
```

## Quick Start

### Option 1: Full Automation (Recommended)

```bash
# 1. Create all templates (one-time, stores on HDD)
cd /home/dmpr/workspaces/projects/home-lab
bash proxmox/scripts/templates/create-all-templates.sh

# 2. Deploy all services (clones to SSD)
bash proxmox/scripts/deploy-all-services.sh
```

### Option 2: Individual Services

```bash
# 1. Create specific template
bash proxmox/scripts/templates/create-postgresql-template.sh

# 2. Deploy specific service
bash proxmox/scripts/services/deploy-postgresql.sh
```

## Template Management

### Create All Templates

```bash
bash proxmox/scripts/templates/create-all-templates.sh
```

**What it does:**
- Downloads Proxmox VE Community Scripts
- Creates LXC containers (ID 900-999)
- Stores on HDD (`local-hdd`)
- Converts to templates
- Ready for cloning

**Templates created:**
| ID | Name | Service |
|----|------|---------|
| 900 | postgresql-template | PostgreSQL 16 |
| 901 | redis-template | Redis Cache |
| 902 | nextcloud-template | Nextcloud |
| 903 | gitea-template | Gitea Git |
| 904 | homeassistant-template | Home Assistant |
| 905 | grafana-template | Grafana |
| 906 | prometheus-template | Prometheus |
| 907 | npm-template | Nginx Proxy Manager |
| 908 | docker-template | Docker Host |

### List Templates

```bash
pct list | grep template
```

## Service Deployment

### Deploy All Services

```bash
bash proxmox/scripts/deploy-all-services.sh
```

**What it does:**
- Clones templates (ID 900-999 → 200-299)
- Stores on SSD (`local-lvm`) for production
- Configures static IPs (10.0.30.10-90)
- Sets hostname
- Starts containers
- Applies service-specific configuration

**Services deployed:**
| CTID | Hostname | IP | Service |
|------|----------|----|---------|
| 200 | postgresql-db | 10.0.30.10 | PostgreSQL |
| 201 | redis-cache | 10.0.30.20 | Redis |
| 202 | nextcloud | 10.0.30.30 | Nextcloud |
| 203 | gitea | 10.0.30.40 | Gitea |
| 204 | homeassistant | 10.0.30.50 | Home Assistant |
| 205 | grafana | 10.0.30.60 | Grafana |
| 206 | prometheus | 10.0.30.70 | Prometheus |
| 207 | nginx-proxy | 10.0.30.80 | Nginx Proxy Manager |
| 208 | docker-host | 10.0.30.90 | Docker |

### Deploy Individual Service

```bash
# PostgreSQL
bash proxmox/scripts/services/deploy-postgresql.sh

# Redis
bash proxmox/scripts/services/deploy-redis.sh

# Docker
bash proxmox/scripts/services/deploy-docker.sh
```

**Interactive prompts:**
- Container ID (default provided)
- Hostname (default provided)
- IP Address (default provided)
- Storage (SSD/HDD)

## Network Configuration

All services deployed to **Internal Network**:

```
Network: 10.0.30.0/24
Gateway: 10.0.30.1 (OPNsense)
DNS: 192.168.10.2 (OPNsense)
Bridge: vmbr2 (Internal)
```

## Storage Strategy

### Templates (HDD - local-hdd)
- **Location:** /mnt/hdd
- **Purpose:** Template storage
- **Reason:** Save SSD space
- **Access:** Read-only after creation

### Services (SSD - local-lvm)
- **Location:** local-lvm
- **Purpose:** Production containers
- **Reason:** Fast I/O
- **Size:** Allocated from 148 GB pool

## Default Credentials

**All containers:**
- Username: `root`
- Password: `Homelab2025!`

⚠️ **Change passwords after deployment!**

## Common Operations

### List Templates

```bash
pct list | grep template
```

### List Containers

```bash
pct list | grep -v template
```

### Container Status

```bash
pct status 200
```

### Start/Stop Container

```bash
pct start 200
pct stop 200
```

### Access Container

```bash
# SSH
ssh root@10.0.30.10

# Console
pct enter 200

# Execute command
pct exec 200 -- ls -la
```

### Clone Additional Service

```bash
# Clone PostgreSQL for another database
pct clone 900 210 --hostname postgres-02 --full --storage local-lvm
pct set 210 --net0 name=eth0,bridge=vmbr2,ip=10.0.30.11/24,gw=10.0.30.1
pct start 210
```

### Remove Service

```bash
pct stop 200
pct destroy 200
```

## Service-Specific Configuration

### PostgreSQL (CTID 200)

```bash
# Access database
pct exec 200 -- su - postgres -c 'psql'

# Create database
pct exec 200 -- su - postgres -c 'createdb myapp'

# Create user
pct exec 200 -- su - postgres -c "psql -c \"CREATE USER myuser WITH PASSWORD 'mypass';\""
```

**Connection string:**
```
postgresql://myuser:mypass@10.0.30.10:5432/myapp
```

### Redis (CTID 201)

```bash
# Test connection
redis-cli -h 10.0.30.10 ping

# Connect
redis-cli -h 10.0.30.10
```

### Docker (CTID 208)

```bash
# Run container in Docker host
pct exec 208 -- docker run -d -p 8080:80 nginx

# Access from host
curl http://10.0.30.90:8080
```

### Nginx Proxy Manager (CTID 207)

**Access Web UI:**
```
http://10.0.30.80:81

Default credentials:
Email: admin@example.com
Password: changeme
```

## Automation Examples

### Deploy Multiple PostgreSQL Instances

```bash
#!/bin/bash
# Deploy 3 PostgreSQL databases

for i in {1..3}; do
    CTID=$((209 + i))
    IP="10.0.30.$((10 + i))"

    pct clone 900 $CTID --hostname postgres-0$i --full --storage local-lvm
    pct set $CTID --net0 name=eth0,bridge=vmbr2,ip=${IP}/24,gw=10.0.30.1
    pct start $CTID

    echo "PostgreSQL instance $i: $IP"
done
```

### Backup All Services

```bash
#!/bin/bash
# Backup all deployed services

for ctid in {200..208}; do
    if pct status $ctid &>/dev/null; then
        vzdump $ctid --storage local-hdd --mode snapshot --compress zstd
    fi
done
```

## Troubleshooting

### Template Creation Failed

```bash
# Check logs
journalctl -xe

# Retry template creation
pct destroy 900
bash proxmox/scripts/templates/create-postgresql-template.sh
```

### Container Won't Start

```bash
# Check status
pct status 200

# View configuration
pct config 200

# Check logs
pct exec 200 -- journalctl -xe
```

### Network Issues

```bash
# Test connectivity
pct exec 200 -- ping 8.8.8.8

# Check network config
pct exec 200 -- ip a

# Reconfigure network
pct set 200 --net0 name=eth0,bridge=vmbr2,ip=10.0.30.10/24,gw=10.0.30.1
pct reboot 200
```

### Out of Disk Space

**SSD Full:**
```bash
# Move non-critical services to HDD
pct stop 202
pct move-disk 202 rootfs local-hdd
pct start 202
```

**HDD Full:**
```bash
# Clean old backups
find /mnt/hdd/dump -name "*.zst" -mtime +30 -delete
```

## Advanced Usage

### Custom Template Creation

```bash
# Create custom template
pct create 920 local:vztmpl/debian-12.tar.zst \
  --hostname custom-template \
  --net0 name=eth0,bridge=vmbr2,ip=dhcp \
  --storage local-hdd \
  --memory 2048 --cores 2 --rootfs local-hdd:8

# Configure container
pct start 920
pct exec 920 -- apt update && apt install -y custom-packages

# Convert to template
pct stop 920
pct template 920
```

### Clone with Cloud-Init

```bash
# Clone with automatic configuration
pct clone 900 220 --hostname app-db --full --storage local-lvm
pct set 220 --net0 name=eth0,bridge=vmbr2,ip=10.0.30.20/24,gw=10.0.30.1
pct set 220 --onboot 1
pct start 220
```

## Monitoring

### Resource Usage

```bash
# All containers
pct list

# Specific container
pct exec 200 -- htop

# Disk usage
pct df 200
```

### Logs

```bash
# System logs
pct exec 200 -- journalctl -f

# Service logs
pct exec 200 -- tail -f /var/log/postgresql/*.log
```

## Best Practices

1. **Create templates once** - Store on HDD
2. **Clone for production** - Deploy to SSD
3. **Use static IPs** - Easier management
4. **Document customizations** - Track changes
5. **Regular backups** - Weekly snapshots
6. **Monitor resources** - Check disk/RAM usage
7. **Update templates** - Rebuild quarterly
8. **Test before deploy** - Clone to HDD first

## Integration with Home Lab

These services integrate with the overall architecture:

```
Internet → OPNsense (Firewall) → Internal Network (10.0.30.0/24)
                                         ↓
                              ┌──────────┴──────────┐
                              │  LXC Services       │
                              │  (Auto-deployed)    │
                              └─────────────────────┘
                                         ↓
                              Access from LAN (192.168.20.0/24)
                              via OPNsense routing
```

## Next Steps

After deployment:

1. **Configure firewall rules** on OPNsense
2. **Set up Nginx Proxy Manager** for reverse proxy
3. **Configure each service** according to needs
4. **Create backups** using Proxmox backup jobs
5. **Monitor services** with Grafana + Prometheus

## Support

**Documentation:**
- [Proxmox VE Community Scripts](https://community-scripts.github.io/ProxmoxVE/)
- [VM Templates Guide](../VM-TEMPLATES-GUIDE.md)
- [Storage Reference](../STORAGE-REFERENCE.md)

**Commands:**
```bash
# Get help for any script
bash script-name.sh --help

# List available functions
source lib/common-functions.sh
declare -F | grep -v "declare -f _"
```
