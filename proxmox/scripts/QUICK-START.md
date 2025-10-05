# Quick Start Guide - 5 Minutes to Production

## Prerequisites

- ✅ Proxmox VE installed
- ✅ Network configured (vmbr2 = 10.0.30.0/24)
- ✅ HDD mounted at /mnt/hdd
- ✅ SSH access to Proxmox

## Step 1: Upload Scripts (1 min)

```bash
# On your local machine
scp -r proxmox/scripts root@<proxmox-ip>:/root/

# SSH to Proxmox
ssh root@<proxmox-ip>
cd /root/scripts
```

## Step 2: Create Templates (15-30 min, one-time)

```bash
# Create all 9 templates
bash templates/create-all-templates.sh

# Or create individual template
bash templates/create-postgresql-template.sh
```

**What happens:**
- Downloads Community Scripts
- Creates containers on HDD
- Converts to templates
- IDs: 900-908

**Wait time:** 15-30 minutes total

## Step 3: Deploy Services (5-10 min)

```bash
# Deploy all services
bash deploy-all-services.sh

# Or deploy individual service
bash services/deploy-postgresql.sh
```

**What happens:**
- Clones templates to SSD
- Configures network (10.0.30.10-90)
- Starts containers
- Applies service config

**Wait time:** 5-10 minutes total

## Step 4: Verify (1 min)

```bash
# List all containers
pct list

# Check status
pct status 200

# Test PostgreSQL
pct exec 200 -- su - postgres -c 'psql -c "SELECT version();"'

# Test Redis
pct exec 201 -- redis-cli ping
```

## Step 5: Access Services

```bash
# SSH to any service
ssh root@10.0.30.10  # PostgreSQL
Password: Homelab2025!

# Or from Proxmox console
pct enter 200
```

## Service URLs

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Nginx Proxy Manager | http://10.0.30.80:81 | admin@example.com / changeme |
| Grafana | http://10.0.30.60:3000 | admin / admin |
| Home Assistant | http://10.0.30.50:8123 | Setup on first access |
| Nextcloud | http://10.0.30.30 | Setup on first access |
| Gitea | http://10.0.30.40:3000 | Setup on first access |

## Common Tasks

### Deploy Additional Instance

```bash
# Clone PostgreSQL for 2nd database
pct clone 900 210 --hostname postgres-02 --full --storage local-lvm
pct set 210 --net0 name=eth0,bridge=vmbr2,ip=10.0.30.11/24,gw=10.0.30.1
pct start 210
```

### Backup Service

```bash
# Backup PostgreSQL
vzdump 200 --storage local-hdd --mode snapshot
```

### Remove Service

```bash
pct stop 200
pct destroy 200
```

## Troubleshooting

### Template creation failed

```bash
# Check what went wrong
pct list | grep 900

# Retry
pct destroy 900
bash templates/create-postgresql-template.sh
```

### Service won't start

```bash
# Check logs
pct exec 200 -- journalctl -xe

# Restart
pct stop 200
pct start 200
```

### Network not working

```bash
# Check IP
pct exec 200 -- ip a

# Reconfigure
pct set 200 --net0 name=eth0,bridge=vmbr2,ip=10.0.30.10/24,gw=10.0.30.1
pct reboot 200
```

## Next Steps

1. **Configure OPNsense** - Add firewall rules for LAN → INTERNAL
2. **Setup Nginx Proxy Manager** - Reverse proxy for all services
3. **Configure each service** - Follow service-specific docs
4. **Setup backups** - Schedule weekly backups
5. **Monitor resources** - Check CPU/RAM usage

## Complete Automation (Zero interaction)

Create a master script:

```bash
#!/bin/bash
# complete-setup.sh - Full automation

cd /root/scripts

# Create all templates
bash templates/create-all-templates.sh <<EOF
yes
EOF

# Wait for templates
sleep 60

# Deploy all services
bash deploy-all-services.sh <<EOF
yes
EOF

echo "Setup complete!"
pct list
```

Run it:
```bash
bash complete-setup.sh
```

Go get coffee ☕ - everything will be ready in 30-40 minutes!

## Architecture Summary

```
Templates (HDD)          Services (SSD)
  900-908          →        200-208
  (one-time)              (production)

Network: 10.0.30.0/24
Gateway: 10.0.30.1 (OPNsense)
Storage: local-lvm (SSD) + local-hdd (HDD)
```

**Total time from zero to production:** ~40 minutes
- Template creation: 30 min (one-time)
- Service deployment: 10 min (repeatable)
