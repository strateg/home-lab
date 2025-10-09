# Network Configuration Guide

## Overview

Automated network configuration for Proxmox VE on Dell XPS L701X home lab.

The system creates **4 network bridges** with persistent interface naming:

```
┌─────────────────────────────────────────────────────────────┐
│                    Dell XPS L701X Proxmox                   │
│                                                             │
│  ┌──────────────┐              ┌──────────────┐            │
│  │  USB-Ethernet│─────────────→│    vmbr0     │            │
│  │   (eth-wan)  │              │   WAN Bridge │────→ ISP   │
│  └──────────────┘              └──────────────┘            │
│                                                             │
│  ┌──────────────┐              ┌──────────────┐            │
│  │   Built-in   │─────────────→│    vmbr1     │            │
│  │  (eth-lan)   │              │   LAN Bridge │────→ OpenWRT│
│  └──────────────┘              └──────────────┘            │
│                                                             │
│                                 ┌──────────────┐            │
│                                 │    vmbr2     │            │
│                                 │10.0.30.0/24  │────→ LXC   │
│                                 └──────────────┘            │
│                                                             │
│                                 ┌──────────────┐            │
│                                 │    vmbr99    │            │
│                                 │10.0.99.0/24  │────→ Mgmt  │
│                                 └──────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

## Network Bridges

| Bridge | Purpose | IP Range | Connected To |
|--------|---------|----------|-------------|
| **vmbr0** | WAN | DHCP from ISP | ISP Router via USB-Ethernet |
| **vmbr1** | LAN | Managed by OpenWRT | OpenWRT WAN via Built-in Ethernet |
| **vmbr2** | Internal | 10.0.30.0/24 | LXC containers (PostgreSQL, Redis, etc.) |
| **vmbr99** | Management | 10.0.99.0/24 | Emergency access to VMs/containers |

## Persistent Interface Names

UDEV rules provide consistent naming across reboots:

- **eth-wan** → USB-Ethernet adapter (to ISP)
- **eth-lan** → Built-in Ethernet (to OpenWRT)

## Quick Start

### Option 1: Automated Configuration (Recommended)

```bash
# Full automation - no prompts
bash configure-network.sh --auto

# Or integrate with post-install
bash proxmox-post-install.sh --init-hdd --auto-network
```

### Option 2: Interactive Configuration

```bash
# Interactive mode - choose interfaces manually
bash configure-network.sh

# Or via post-install
bash proxmox-post-install.sh
```

### Option 3: Manual Configuration

```bash
# Show current configuration
bash configure-network.sh --show

# Generate network diagram
bash configure-network.sh --diagram

# Test connectivity
bash configure-network.sh --test
```

## What Gets Configured

### 1. UDEV Rules (`/etc/udev/rules.d/70-persistent-net.rules`)

```bash
# Built-in Ethernet
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="xx:xx:xx:xx:xx:xx", NAME="eth-lan"

# USB-Ethernet
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="yy:yy:yy:yy:yy:yy", NAME="eth-wan"
```

### 2. Network Interfaces (`/etc/network/interfaces`)

```bash
# Loopback
auto lo
iface lo inet loopback

# Physical interfaces
auto eth-wan
iface eth-wan inet manual

auto eth-lan
iface eth-lan inet manual

# vmbr0 - WAN Bridge
auto vmbr0
iface vmbr0 inet manual
    bridge-ports eth-wan
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094

# vmbr1 - LAN Bridge
auto vmbr1
iface vmbr1 inet manual
    bridge-ports eth-lan
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094

# vmbr2 - Internal Bridge
auto vmbr2
iface vmbr2 inet static
    address 10.0.30.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0

# vmbr99 - Management Bridge
auto vmbr99
iface vmbr99 inet static
    address 10.0.99.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0
```

## Network Flow

### WAN Traffic (Internet Access)

```
Internet ←→ ISP Router ←→ USB-Ethernet ←→ vmbr0 ←→ OPNsense WAN
```

### LAN Traffic (Home Network)

```
OPNsense LAN ←→ vmbr1 ←→ Built-in Ethernet ←→ OpenWRT WAN
                                                    ↓
                                              OpenWRT LAN
                                                    ↓
                                             Home Devices
```

### Internal Traffic (LXC Containers)

```
Proxmox Host (10.0.30.1) ←→ vmbr2 ←→ LXC Containers (10.0.30.10-90)
```

### Management Traffic (Emergency Access)

```
Proxmox Host (10.0.99.1) ←→ vmbr99 ←→ VMs/Containers (10.0.99.x)
```

## Troubleshooting

### Network Not Working After Reboot

```bash
# Check interface names
ip link show

# Check udev rules applied
cat /etc/udev/rules.d/70-persistent-net.rules

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

# Restart networking
systemctl restart networking
```

### Interface Detection Failed

```bash
# Show all interfaces
ip link show

# Check PCI devices (built-in)
lspci | grep -i ethernet

# Check USB devices (USB-Ethernet)
lsusb | grep -i ethernet

# Manual configuration
bash configure-network.sh --interactive
```

### Restore Previous Configuration

```bash
# List available backups
ls -la /root/network-backups/

# Restore from backup
bash configure-network.sh --restore
```

### USB-Ethernet Not Detected

This is normal if the adapter is not connected. Options:

1. **Connect USB-Ethernet and re-run**:
   ```bash
   bash configure-network.sh --auto
   ```

2. **Skip for now, configure later**:
   ```bash
   # Network will be configured without WAN bridge
   # You can add vmbr0 manually later
   ```

## Advanced Usage

### Generate Network Diagram

```bash
bash configure-network.sh --diagram
```

Output shows full network topology with bridges, interfaces, and IP ranges.

### Test Network Connectivity

```bash
bash configure-network.sh --test
```

Tests:
- Interface status (up/down)
- Bridge configuration
- IP addressing
- Gateway reachability
- DNS resolution

### Backup Current Configuration

Automatic backups are created in `/root/network-backups/` before any changes:

```bash
/root/network-backups/
└── backup-20250106-143052/
    ├── interfaces
    └── 70-persistent-net.rules
```

### Custom Configuration

Edit the configuration manually:

```bash
# Edit interfaces
nano /etc/network/interfaces

# Edit udev rules
nano /etc/udev/rules.d/70-persistent-net.rules

# Apply changes
systemctl restart networking
```

## Integration with OPNsense

Once network is configured, create OPNsense VM:

```bash
# Download OPNsense ISO
cd /var/lib/vz/template/iso
wget https://mirror.ams1.nl.leaseweb.net/opnsense/releases/24.7/OPNsense-24.7-dvd-amd64.iso.bz2
bunzip2 OPNsense-24.7-dvd-amd64.iso.bz2

# Create VM
qm create 100 --name opnsense --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0 --net1 virtio,bridge=vmbr1 --cdrom local:iso/OPNsense-24.7-dvd-amd64.iso --scsihw virtio-scsi-pci --bootdisk scsi0 --ostype other

# Add disk
qm set 100 --scsi0 local-lvm:32

# Start VM
qm start 100
```

OPNsense network configuration:
- **WAN (vtnet0)** → vmbr0 → ISP (DHCP)
- **LAN (vtnet1)** → vmbr1 → OpenWRT (192.168.20.1/24)

## Files

| File | Purpose |
|------|---------|
| `lib/network-functions.sh` | Core network detection and configuration library |
| `configure-network.sh` | Standalone network configuration script |
| `proxmox-post-install.sh` | Post-install automation (includes network setup) |
| `/etc/network/interfaces` | Network interfaces configuration |
| `/etc/udev/rules.d/70-persistent-net.rules` | Persistent interface naming |

## Architecture Reference

See full home lab architecture in:
- `/docs/NETWORK-ARCHITECTURE.md`
- `proxmox/scripts/ARCHITECTURE.md`

## Support

If automatic detection fails:

1. Run `ip link show` and identify interfaces manually
2. Use `--interactive` mode for manual selection
3. Check system logs: `journalctl -xe | grep -i network`
4. Verify hardware: `lspci` and `lsusb`
