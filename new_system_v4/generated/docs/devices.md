# Devices Inventory

**Generated from**: topology.yaml v4.0.0
**Date**: 2026-02-17 17:45:30

---

## Physical Devices

### Gamayun

**ID**: `gamayun`

| Property | Value |
|----------|-------|
| **Type** | hypervisor |
| **Role** | compute |
| **Model** | Dell XPS L701X |
| **Location** | home |

#### Specifications

**CPU**: Intel Core i3-M370
- Cores: 2
- Threads: 4
- Speed: 2400 MHz

**Memory**: 8 GB DDR3
- Upgradeable: No

**Storage**:
- disk-ssd-system: 180 GB SSD ()
- disk-hdd-data: 500 GB HDD ()

#### Network Interfaces

- **if-eth-builtin** (enp3s0)
  - MAC: `auto-detect`
  - Speed: 
  - Type: pci-ethernet
- **if-eth-usb** (enxXXXXXXXXXXXX)
  - MAC: `auto-detect`
  - Speed: 
  - Type: usb-ethernet

**Description**: Primary Proxmox VE host - Р“Р°РјР°СЋРЅ (РІРµС‰Р°СЏ РїС‚РёС†Р°)

---

### MikroTik Chateau LTE7 ax

**ID**: `mikrotik-chateau`

| Property | Value |
|----------|-------|
| **Type** | router |
| **Role** | central-gateway |
| **Model** | S53UG+5HaxD2HaxD-TC&R11e-LTE7 |
| **Location** | home |

#### Specifications

**CPU**: Qualcomm IPQ-6010
- Cores: 4
- Threads: 
- Speed: 1800 MHz

**Memory**:  GB DDR
- Upgradeable: No


#### Network Interfaces

- **if-mikrotik-wan** ()
  - MAC: ``
  - Speed: 
  - Type: ethernet
- **if-mikrotik-lan1** ()
  - MAC: ``
  - Speed: 
  - Type: ethernet
- **if-mikrotik-lan2** ()
  - MAC: ``
  - Speed: 
  - Type: ethernet
- **if-mikrotik-lan3** ()
  - MAC: ``
  - Speed: 
  - Type: ethernet
- **if-mikrotik-lan4** ()
  - MAC: ``
  - Speed: 
  - Type: ethernet
- **if-mikrotik-wlan-5g** ()
  - MAC: ``
  - Speed: 
  - Type: wifi-5ghz
- **if-mikrotik-wlan-2g** ()
  - MAC: ``
  - Speed: 
  - Type: wifi-2.4ghz
- **if-mikrotik-lte** ()
  - MAC: ``
  - Speed: 
  - Type: lte

**Description**: Central router with WiFi 6, LTE failover, RouterOS v7 containers

---

### Orange Pi 5

**ID**: `orangepi5`

| Property | Value |
|----------|-------|
| **Type** | sbc |
| **Role** | application-server |
| **Model** | Orange Pi 5 |
| **Location** | home |

#### Specifications

**CPU**: Rockchip RK3588S
- Cores: 8
- Threads: 
- Speed:  MHz

**Memory**:  GB LPDDR4/4X
- Upgradeable: No


#### Network Interfaces

- **if-opi5-eth** ()
  - MAC: ``
  - Speed: 
  - Type: ethernet
- **if-opi5-usb3** ()
  - MAC: ``
  - Speed: 
  - Type: usb
- **if-opi5-usb2** ()
  - MAC: ``
  - Speed: 
  - Type: usb
- **if-opi5-usbc** ()
  - MAC: ``
  - Speed: 
  - Type: usb-c
- **if-opi5-hdmi** ()
  - MAC: ``
  - Speed: 
  - Type: hdmi
- **if-opi5-mipi-dsi** ()
  - MAC: ``
  - Speed: 
  - Type: display
- **if-opi5-mipi-csi** ()
  - MAC: ``
  - Speed: 
  - Type: camera
- **if-opi5-gpio** ()
  - MAC: ``
  - Speed: 
  - Type: expansion
- **if-opi5-audio** ()
  - MAC: ``
  - Speed: 
  - Type: audio
- **if-opi5-debug** ()
  - MAC: ``
  - Speed: 
  - Type: debug

**Description**: Dedicated application server for Nextcloud, Jellyfin, monitoring

---

### GL.iNet Slate AX

**ID**: `slate-ax1800`

| Property | Value |
|----------|-------|
| **Type** | router |
| **Role** | travel-router |
| **Model** | GL-AXT1800 |
| **Location** | portable |

#### Specifications

**CPU**: MediaTek MT7981B
- Cores: 2
- Threads: 
- Speed: 1300 MHz

**Memory**:  GB DDR4
- Upgradeable: No


#### Network Interfaces

- **if-slate-wan** ()
  - MAC: ``
  - Speed: 
  - Type: ethernet
- **if-slate-lan** ()
  - MAC: ``
  - Speed: 
  - Type: ethernet
- **if-slate-wlan-5g** ()
  - MAC: ``
  - Speed: 
  - Type: wifi-5ghz
- **if-slate-wlan-2g** ()
  - MAC: ``
  - Speed: 
  - Type: wifi-2.4ghz

**Description**: Travel router for remote access to home network

---


## Virtual Machines

Total: **0**


## LXC Containers

Total: **2**

### postgresql-db

**ID**: `lxc-postgresql` | **VMID**: 200

| Property | Value |
|----------|-------|
| **Type** | database |
| **Role** | database-server |
| **OS** | debian 12 |
| **Trust Zone** | servers |

**Resources**:
- **CPU**: 2 cores
- **Memory**: 1024 MB
- **Swap**: 1024 MB

**Storage**:
- **Root**: 8 GB

**IP Address**: 10.0.30.10/24

**Tags**: database, production

---

### redis-cache

**ID**: `lxc-redis` | **VMID**: 201

| Property | Value |
|----------|-------|
| **Type** | cache |
| **Role** | cache-server |
| **OS** | debian 12 |
| **Trust Zone** | servers |

**Resources**:
- **CPU**: 1 cores
- **Memory**: 512 MB
- **Swap**: 256 MB

**Storage**:
- **Root**: 4 GB

**IP Address**: 10.0.30.20/24

**Tags**: cache, production

---


## Storage Pools

### local

**ID**: `storage-local`

| Property | Value |
|----------|-------|
| **Pool** |  |
| **Type** | dir |
| **Path** | /var/lib/vz |


**Description**: Local directory storage on SSD

---

### local-lvm

**ID**: `storage-lvm`

| Property | Value |
|----------|-------|
| **Pool** |  |
| **Type** | lvmthin |
| **Path** | N/A |


**Description**: SSD 180GB - Production VMs and LXC thin pool

---

### local-hdd

**ID**: `storage-hdd`

| Property | Value |
|----------|-------|
| **Pool** |  |
| **Type** | dir |
| **Path** | /mnt/hdd |


**Description**: HDD 500GB - Backups, ISOs, Templates

---


---

**DO NOT EDIT MANUALLY** - Regenerate with `python3 scripts/generate-docs.py`