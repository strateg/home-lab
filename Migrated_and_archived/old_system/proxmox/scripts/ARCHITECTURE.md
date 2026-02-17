# LXC Automation Architecture

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: Template Creation                    │
│                         (One-time setup)                          │
└─────────────────────────────────────────────────────────────────┘

Step 1: Run create-all-templates.sh
        ↓
Step 2: Downloads Proxmox Community Scripts
        ↓
Step 3: Creates LXC containers (ID 900-999)
        ↓
Step 4: Stores on HDD (local-hdd)
        ↓
Step 5: Converts to templates

Result: 9 Templates ready for cloning


┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 2: Service Deployment                   │
│                      (Repeatable process)                         │
└─────────────────────────────────────────────────────────────────┘

Step 1: Run deploy-all-services.sh (or individual deploy script)
        ↓
Step 2: Clones template (900-999 → 200-299)
        ↓
Step 3: Stores on SSD (local-lvm) for production
        ↓
Step 4: Configures network (static IP in 10.0.30.0/24)
        ↓
Step 5: Starts container
        ↓
Step 6: Applies service-specific configuration

Result: Production service ready to use
```

## Component Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Proxmox VE Host                               │
│                                                                       │
│  ┌────────────────────────┐        ┌──────────────────────────────┐ │
│  │   Templates (HDD)      │        │   Services (SSD)             │ │
│  │   Storage: local-hdd   │        │   Storage: local-lvm         │ │
│  │   /mnt/hdd             │        │   Performance: Fast          │ │
│  ├────────────────────────┤        ├──────────────────────────────┤ │
│  │                        │        │                              │ │
│  │ 900 PostgreSQL ────────┼───────→│ 200 PostgreSQL  10.0.30.10  │ │
│  │ 901 Redis      ────────┼───────→│ 201 Redis       10.0.30.20  │ │
│  │ 902 Nextcloud  ────────┼───────→│ 202 Nextcloud   10.0.30.30  │ │
│  │ 903 Gitea      ────────┼───────→│ 203 Gitea       10.0.30.40  │ │
│  │ 904 HomeAssist ────────┼───────→│ 204 HomeAssist  10.0.30.50  │ │
│  │ 905 Grafana    ────────┼───────→│ 205 Grafana     10.0.30.60  │ │
│  │ 906 Prometheus ────────┼───────→│ 206 Prometheus  10.0.30.70  │ │
│  │ 907 NPM        ────────┼───────→│ 207 NPM         10.0.30.80  │ │
│  │ 908 Docker     ────────┼───────→│ 208 Docker      10.0.30.90  │ │
│  │                        │        │                              │ │
│  │ Read-only templates    │ Clone  │ Writable containers          │ │
│  │ Slow (HDD)             │ ─────→ │ Fast (SSD)                   │ │
│  └────────────────────────┘        └──────────────────────────────┘ │
│                                                                       │
│                           Network: vmbr2 (10.0.30.0/24)              │
└──────────────────────────────────────────────────────────────────────┘
                                      │
                                      ↓
                            ┌──────────────────┐
                            │  OPNsense Router │
                            │  10.0.30.1       │
                            └──────────────────┘
                                      │
                                      ↓
                              LAN (192.168.20.0/24)
```

## Script Hierarchy

```
proxmox/scripts/
│
├── lib/common-functions.sh           # Core library
│   ├── check_proxmox()               # Environment checks
│   ├── template_exists()             # Template management
│   ├── container_exists()
│   ├── create_template_from_community()  # Template creation
│   ├── clone_template()              # Cloning logic
│   ├── start_container()             # Container lifecycle
│   └── ... (20+ utility functions)
│
├── templates/                        # Template creation
│   ├── create-all-templates.sh       # Master: Create all
│   │   └── Calls create_template_from_community() for each service
│   │
│   └── create-postgresql-template.sh  # Individual template
│       └── Uses lib/common-functions.sh
│
├── services/                         # Service deployment
│   ├── deploy-postgresql.sh          # PostgreSQL deployment
│   │   ├── Sources: lib/common-functions.sh
│   │   ├── Checks: template_exists(900)
│   │   ├── Clones: clone_template(900 → 200)
│   │   └── Configures: PostgreSQL-specific settings
│   │
│   ├── deploy-redis.sh               # Redis deployment
│   └── deploy-docker.sh              # Docker deployment
│
└── deploy-all-services.sh            # Master: Deploy all
    ├── Sources: lib/common-functions.sh
    ├── Iterates: SERVICES array
    ├── Deploys: Each service with defaults
    └── Reports: Success/failure summary
```

## Data Flow

### Template Creation Flow

```
User Input
    ↓
create-all-templates.sh
    ↓
For each service:
    ↓
    ┌──────────────────────────────────────────┐
    │ create_template_from_community()         │
    │                                          │
    │ 1. Download Community Script             │
    │    URL: github.com/.../postgresql.sh     │
    │                                          │
    │ 2. Set environment variables             │
    │    CTID=900                              │
    │    STORAGE=local-hdd                     │
    │    NET=dhcp                              │
    │                                          │
    │ 3. Execute Community Script              │
    │    bash -c "$(wget -qLO - $URL)"         │
    │                                          │
    │ 4. Wait for container creation           │
    │                                          │
    │ 5. Stop container                        │
    │    pct stop 900                          │
    │                                          │
    │ 6. Convert to template                   │
    │    pct template 900                      │
    └──────────────────────────────────────────┘
    ↓
Template stored on HDD
```

### Service Deployment Flow

```
User Input (or defaults)
    ↓
deploy-postgresql.sh
    ↓
    ┌──────────────────────────────────────────┐
    │ Check template_exists(900)               │
    └──────────────────────────────────────────┘
    ↓
    ┌──────────────────────────────────────────┐
    │ clone_template(900 → 200)                │
    │                                          │
    │ pct clone 900 200                        │
    │   --hostname postgresql-db               │
    │   --storage local-lvm                    │
    │   --full                                 │
    └──────────────────────────────────────────┘
    ↓
    ┌──────────────────────────────────────────┐
    │ Configure Network                        │
    │                                          │
    │ pct set 200 --net0                       │
    │   name=eth0,bridge=vmbr2,                │
    │   ip=10.0.30.10/24,gw=10.0.30.1          │
    └──────────────────────────────────────────┘
    ↓
    ┌──────────────────────────────────────────┐
    │ start_container(200)                     │
    │                                          │
    │ pct start 200                            │
    │ wait 30 seconds                          │
    └──────────────────────────────────────────┘
    ↓
    ┌──────────────────────────────────────────┐
    │ Service-specific configuration           │
    │                                          │
    │ exec_in_container(200, "config cmds")    │
    └──────────────────────────────────────────┘
    ↓
Service ready at 10.0.30.10
```

## Network Architecture

```
                    ┌──────────────────────┐
                    │   Physical Host      │
                    │   Dell XPS L701X     │
                    └──────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────────┐           ┌─────────┐          ┌─────────┐
   │ vmbr0  │           │ vmbr1   │          │ vmbr2   │
   │  WAN   │           │  LAN    │          │ INTERNAL│
   └────────┘           └─────────┘          └─────────┘
        │                     │                     │
        │              ┌──────────────┐             │
        │              │  OPNsense VM │             │
        └─────────────→│  Firewall    │←────────────┘
                       └──────────────┘
                              │
                       Routes to LXC
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌─────────┐           ┌─────────┐          ┌─────────┐
   │  LXC    │           │  LXC    │          │  LXC    │
   │ CTID    │           │ CTID    │          │ CTID    │
   │  200    │           │  201    │          │  202    │
   │         │           │         │          │         │
   │10.0.30  │           │10.0.30  │          │10.0.30  │
   │   .10   │           │   .20   │          │   .30   │
   └─────────┘           └─────────┘          └─────────┘
  PostgreSQL              Redis              Nextcloud

  All connected to vmbr2 (Internal Bridge)
  Gateway: 10.0.30.1 (OPNsense)
```

## Storage Architecture

```
Physical Disks:
┌──────────────────────────────────────────────────────────┐
│  /dev/sda (SSD 180GB)         /dev/sdb (HDD 500GB)      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────┐    ┌──────────────────────┐    │
│  │   local-lvm (LVM)   │    │  local-hdd (Dir)     │    │
│  │   ~148 GB           │    │  /mnt/hdd            │    │
│  │                     │    │  500 GB              │    │
│  └─────────────────────┘    └──────────────────────┘    │
│           │                          │                   │
│           ↓                          ↓                   │
│  ┌─────────────────────┐    ┌──────────────────────┐    │
│  │  Production         │    │  Templates           │    │
│  │  Containers         │    │  900-999             │    │
│  │  200-299            │    │                      │    │
│  │                     │    │  Backups             │    │
│  │  - PostgreSQL 200   │    │  ISO Images          │    │
│  │  - Redis 201        │    │  Personal Files      │    │
│  │  - Nextcloud 202    │    │                      │    │
│  │  - ...              │    │                      │    │
│  │                     │    │                      │    │
│  │  Fast I/O           │    │  Bulk Storage        │    │
│  │  Limited space      │    │  Large capacity      │    │
│  └─────────────────────┘    └──────────────────────┘    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Security Model

```
Access Layers:

1. Physical Layer
   └─ Dell XPS L701X (Proxmox host)
      └─ SSH access only

2. Network Layer
   └─ OPNsense Firewall
      ├─ Rules for LAN → INTERNAL
      └─ NAT/routing for service access

3. Container Layer
   └─ LXC Containers (unprivileged)
      ├─ Isolated namespaces
      ├─ Resource limits
      └─ Individual root passwords

4. Application Layer
   └─ Each service has own authentication
      ├─ PostgreSQL users
      ├─ Redis password
      ├─ Nextcloud users
      └─ etc.
```

## Scaling Model

```
Horizontal Scaling (Multiple instances):

Template 900 (PostgreSQL)
    │
    ├──→ Service 200 (Primary DB)    10.0.30.10
    ├──→ Service 210 (Replica 1)     10.0.30.11
    ├──→ Service 211 (Replica 2)     10.0.30.12
    └──→ Service 212 (Test DB)       10.0.30.13


Vertical Scaling (Resource adjustment):

pct set 200 --memory 4096  # Increase RAM
pct set 200 --cores 4      # Increase CPU
pct resize 200 rootfs +10G # Increase disk
```

## Disaster Recovery

```
Recovery Scenarios:

1. Container Failure
   └─ Clone template again
      └─ Restore from backup

2. Template Corruption
   └─ Re-create from Community Scripts
      └─ 15-30 minutes per template

3. Complete System Loss
   └─ Reinstall Proxmox
   └─ Run post-install script
   └─ Create templates (1-2 hours)
   └─ Deploy services (30 minutes)
   └─ Restore from backups
```

## Performance Characteristics

| Metric | Templates (HDD) | Services (SSD) |
|--------|----------------|----------------|
| **Creation time** | 5-15 min/each | 2-5 min (clone) |
| **Storage speed** | ~100 MB/s read | ~500 MB/s read |
| **I/O latency** | ~10ms | ~1ms |
| **Use case** | One-time creation | Daily operations |
| **Cost** | Bulk storage | Premium performance |

**Optimization strategy:**
- Templates on HDD (rarely accessed)
- Services on SSD (frequent I/O)
- Backups on HDD (periodic writes)
