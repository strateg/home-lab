# Services Inventory

**Generated from**: topology.yaml v4.0.0
**Date**: 2026-02-17 17:45:30

---

## Running Services

Total services: **15**

### MikroTik WebFig

**ID**: `svc-mikrotik-ui`

| Property | Value |
|----------|-------|
| **Type** | web-ui |
| **Protocol** | https |
| **Port** |  |
| **Host** | mikrotik-chateau (Device) |
| **Network** | net-management |
| **Trust Zone** | management |

**Description**: MikroTik RouterOS WebFig management (HTTPS)




---

### AdGuard Home

**ID**: `svc-adguard`

| Property | Value |
|----------|-------|
| **Type** | dns |
| **Protocol** | http |
| **Port** |  |
| **Host** | mikrotik-chateau (Device) |
| **Network** | net-lan |
| **Trust Zone** | user |

**Description**: DNS filtering and ad blocking (container on MikroTik)




---

### WireGuard VPN

**ID**: `svc-wireguard`

| Property | Value |
|----------|-------|
| **Type** | vpn |
| **Protocol** | udp |
| **Port** | 51820 |
| **Host** | mikrotik-chateau (Device) |
| **Network** | net-vpn-home |
| **Trust Zone** | user |

**Description**: WireGuard VPN server (native RouterOS)




---

### Tailscale

**ID**: `svc-tailscale`

| Property | Value |
|----------|-------|
| **Type** | vpn |
| **Protocol** |  |
| **Port** |  |
| **Host** | mikrotik-chateau (Device) |
| **Network** | net-tailscale |
| **Trust Zone** | user |

**Description**: Tailscale mesh VPN (container on MikroTik)




---

### Nextcloud

**ID**: `svc-nextcloud`

| Property | Value |
|----------|-------|
| **Type** | web-application |
| **Protocol** | https |
| **Port** |  |
| **Host** | orangepi5 (Device) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Nextcloud file sharing and collaboration

**Dependencies**:
- svc-postgresql (required)
- svc-redis (required)



---

### Jellyfin

**ID**: `svc-jellyfin`

| Property | Value |
|----------|-------|
| **Type** | media-server |
| **Protocol** | http |
| **Port** | 8096 |
| **Host** | orangepi5 (Device) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Jellyfin media server with hardware transcoding




---

### AdGuard Home Secondary

**ID**: `svc-adguard-secondary`

| Property | Value |
|----------|-------|
| **Type** | dns |
| **Protocol** | http |
| **Port** |  |
| **Host** | orangepi5 (Device) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Secondary DNS for redundancy (synced with primary)




---

### Prometheus

**ID**: `svc-prometheus`

| Property | Value |
|----------|-------|
| **Type** | monitoring |
| **Protocol** | http |
| **Port** | 9090 |
| **Host** | orangepi5 (Device) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Prometheus metrics collection




---

### Alertmanager

**ID**: `svc-alertmanager`

| Property | Value |
|----------|-------|
| **Type** | alerting |
| **Protocol** | http |
| **Port** | 9093 |
| **Host** | orangepi5 (Device) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Alert routing and notifications

**Dependencies**:
- svc-prometheus (required)



---

### Loki

**ID**: `svc-loki`

| Property | Value |
|----------|-------|
| **Type** | logging |
| **Protocol** | http |
| **Port** | 3100 |
| **Host** | orangepi5 (Device) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Centralized log aggregation




---

### Grafana

**ID**: `svc-grafana`

| Property | Value |
|----------|-------|
| **Type** | visualization |
| **Protocol** | http |
| **Port** | 3000 |
| **Host** | orangepi5 (Device) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Grafana dashboards and visualization

**Dependencies**:
- svc-prometheus (required)



---

### Home Assistant

**ID**: `svc-homeassistant`

| Property | Value |
|----------|-------|
| **Type** | home-automation |
| **Protocol** | http |
| **Port** | 8123 |
| **Host** | orangepi5 (Device) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Home Assistant smart home automation




---

### Proxmox Web UI

**ID**: `svc-proxmox-ui`

| Property | Value |
|----------|-------|
| **Type** | web-ui |
| **Protocol** | https |
| **Port** | 8006 |
| **Host** | gamayun (Device) |
| **Network** | net-management |
| **Trust Zone** | management |

**Description**: Proxmox VE management interface




---

### PostgreSQL Database

**ID**: `svc-postgresql`

| Property | Value |
|----------|-------|
| **Type** | database |
| **Protocol** | tcp |
| **Port** | 5432 |
| **Host** | postgresql-db (LXC) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: PostgreSQL database server




---

### Redis Cache

**ID**: `svc-redis`

| Property | Value |
|----------|-------|
| **Type** | cache |
| **Protocol** | tcp |
| **Port** | 6379 |
| **Host** | redis-cache (LXC) |
| **Network** | net-servers |
| **Trust Zone** | servers |

**Description**: Redis cache server




---


## Services by Type

### Web-Ui

- **MikroTik WebFig** (mikrotik-chateau) - /https
- **Proxmox Web UI** (gamayun) - 8006/https

### Dns

- **AdGuard Home** (mikrotik-chateau) - /http
- **AdGuard Home Secondary** (orangepi5) - /http

### Vpn

- **WireGuard VPN** (mikrotik-chateau) - 51820/udp
- **Tailscale** (mikrotik-chateau) - /

### Web-Application

- **Nextcloud** (orangepi5) - /https

### Media-Server

- **Jellyfin** (orangepi5) - 8096/http

### Monitoring

- **Prometheus** (orangepi5) - 9090/http

### Alerting

- **Alertmanager** (orangepi5) - 9093/http

### Logging

- **Loki** (orangepi5) - 3100/http

### Visualization

- **Grafana** (orangepi5) - 3000/http

### Home-Automation

- **Home Assistant** (orangepi5) - 8123/http

### Database

- **PostgreSQL Database** (postgresql-db) - 5432/tcp

### Cache

- **Redis Cache** (redis-cache) - 6379/tcp


---

## Services by Host

### mikrotik-chateau

- **MikroTik WebFig** (web-ui) - /https
- **AdGuard Home** (dns) - /http
- **WireGuard VPN** (vpn) - 51820/udp
- **Tailscale** (vpn) - /

### orangepi5

- **Nextcloud** (web-application) - /https
- **Jellyfin** (media-server) - 8096/http
- **AdGuard Home Secondary** (dns) - /http
- **Prometheus** (monitoring) - 9090/http
- **Alertmanager** (alerting) - 9093/http
- **Loki** (logging) - 3100/http
- **Grafana** (visualization) - 3000/http
- **Home Assistant** (home-automation) - 8123/http

### gamayun

- **Proxmox Web UI** (web-ui) - 8006/https

### postgresql-db

- **PostgreSQL Database** (database) - 5432/tcp

### redis-cache

- **Redis Cache** (cache) - 6379/tcp


---

**DO NOT EDIT MANUALLY** - Regenerate with `python3 scripts/generate-docs.py`