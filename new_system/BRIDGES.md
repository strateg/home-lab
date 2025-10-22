# Network Bridges Setup Guide

## Overview

Network bridges in Proxmox VE can now be **automatically created via Terraform** using `bpg/proxmox` provider v0.85+!

This document provides:
1. **Automated setup** using Terraform (recommended)
2. **Manual setup** alternatives (Web UI, CLI, Ansible)

---

## ✨ NEW: Automated Setup via Terraform (Recommended)

### What Changed?

**Provider v0.85.0+ supports `proxmox_virtual_environment_network_linux_bridge` resource!**

- ✅ **Fully automated** bridge creation from `topology.yaml`
- ✅ **Declarative** infrastructure-as-code
- ✅ **Idempotent** - safe to run multiple times
- ✅ **Integrated** with VM/LXC deployment

### Prerequisites

1. **Update Terraform provider** (already done in generated config):
   ```hcl
   proxmox = {
     source  = "bpg/proxmox"
     version = "~> 0.85.0"  # Was: 0.50.0
   }
   ```

2. **Verify physical interface names** in `topology/physical.yaml`:
   ```bash
   # SSH to Proxmox host
   ssh root@<proxmox-ip>

   # Find USB Ethernet adapter
   ip link show | grep -i enx
   # Example output: enx00e04c6800f9

   # Find built-in Ethernet
   ip link show | grep -E 'enp|eth0'
   # Example output: enp3s0
   ```

3. **Update `topology/physical.yaml`** with actual interface names:
   ```yaml
   - id: if-eth-usb
     physical_name: "enx00e04c6800f9"  # ← Replace with your USB Ethernet name

   - id: if-eth-builtin
     physical_name: "enp3s0"  # ← Replace with your built-in Ethernet name
   ```

4. **Regenerate Terraform**:
   ```bash
   cd new_system
   python3 scripts/generate-terraform.py
   ```

### Deploy Bridges with Terraform

```bash
cd generated/terraform

# 1. Upgrade provider to v0.85+
terraform init -upgrade

# 2. Review what will be created
terraform plan

# Expected output:
# + proxmox_virtual_environment_network_linux_bridge.bridge_vmbr0
# + proxmox_virtual_environment_network_linux_bridge.bridge_vmbr1
# + proxmox_virtual_environment_network_linux_bridge.bridge_vmbr2
# + proxmox_virtual_environment_network_linux_bridge.bridge_vmbr99

# 3. Create bridges
terraform apply

# 4. Verify
terraform output bridges
```

### Verify Bridge Creation

```bash
# SSH to Proxmox
ssh root@<proxmox-ip>

# Check bridges
brctl show
# Should show: vmbr0, vmbr1, vmbr2, vmbr99

# Check IPs
ip addr show | grep vmbr
# vmbr0: DHCP (from ISP)
# vmbr1: 192.168.10.254/24
# vmbr2: 10.0.30.1/24
# vmbr99: 10.0.99.1/24
```

### What Gets Created

From `generated/terraform/bridges.tf`:

```hcl
resource "proxmox_virtual_environment_network_linux_bridge" "bridge_vmbr0" {
  node_name = var.proxmox_node
  name      = "vmbr0"
  comment   = "WAN Bridge - to ISP Router (USB-Ethernet)"
  ports     = ["enx00e04c6800f9"]  # Your USB Ethernet
  # DHCP - no static address
  autostart = true
}

resource "proxmox_virtual_environment_network_linux_bridge" "bridge_vmbr1" {
  node_name = var.proxmox_node
  name      = "vmbr1"
  comment   = "LAN Bridge - to GL.iNet Slate AX"
  ports     = ["enp3s0"]  # Your built-in Ethernet
  address   = "192.168.10.254/24"
  autostart = true
}

# ... vmbr2 and vmbr99 (internal bridges, no physical ports)
```

### Troubleshooting Terraform Bridges

**Issue: "Cannot find interface enxXXXX"**
```bash
# Solution: Update physical_name in topology/physical.yaml
ssh root@<proxmox-ip> "ip link show"
# Copy actual interface name to topology/physical.yaml
```

**Issue: "Bridge already exists"**
```bash
# Solution: Import existing bridge into Terraform state
terraform import proxmox_virtual_environment_network_linux_bridge.bridge_vmbr0 <node>:vmbr0
terraform import proxmox_virtual_environment_network_linux_bridge.bridge_vmbr1 <node>:vmbr1
terraform import proxmox_virtual_environment_network_linux_bridge.bridge_vmbr2 <node>:vmbr2
terraform import proxmox_virtual_environment_network_linux_bridge.bridge_vmbr99 <node>:vmbr99
```

**Issue: "DHCP not working on vmbr0"**
```bash
# Some provider versions may require manual DHCP setup
# Edit /etc/network/interfaces on Proxmox host:
auto vmbr0
iface vmbr0 inet dhcp
    bridge-ports enxXXXXXXXXXXXX
```

---

## Manual Setup (Fallback)

## Required Bridges

Based on `topology.yaml`, the following bridges must be created:

### 1. vmbr0 - WAN Bridge
```
Name:          vmbr0
Comment:       WAN Bridge - to ISP Router (USB-Ethernet)
Bridge ports:  if-eth-usb (USB Ethernet adapter)
IPv4/CIDR:     DHCP
Autostart:     Yes
VLAN aware:    No
```

**Purpose:** Connects OPNsense WAN interface to ISP router via USB Ethernet adapter.

---

### 2. vmbr1 - LAN Bridge
```
Name:          vmbr1
Comment:       LAN Bridge - to GL.iNet Slate AX (Built-in Ethernet)
Bridge ports:  if-eth-builtin (Built-in Ethernet)
IPv4/CIDR:     192.168.10.254/24
Gateway:       (leave empty)
Autostart:     Yes
VLAN aware:    No
```

**Purpose:** Connects OPNsense LAN interface to GL.iNet Slate AX router for user access.

---

### 3. vmbr2 - INTERNAL Bridge
```
Name:          vmbr2
Comment:       INTERNAL Bridge - LXC Containers
Bridge ports:  (none - internal only)
IPv4/CIDR:     10.0.30.1/24
Gateway:       (leave empty)
Autostart:     Yes
VLAN aware:    No
```

**Purpose:** Internal network for LXC containers. No physical ports - virtual only.

---

### 4. vmbr99 - MGMT Bridge
```
Name:          vmbr99
Comment:       MGMT Bridge - Management Network
Bridge ports:  (none - internal only)
IPv4/CIDR:     10.0.99.1/24
Gateway:       (leave empty)
Autostart:     Yes
VLAN aware:    No
```

**Purpose:** Management network for Proxmox and OPNsense web interfaces.

---

## Setup Method 1: Proxmox Web UI (Recommended)

### Step-by-step:

1. **Access Proxmox Web UI**
   ```
   https://your-proxmox-ip:8006
   ```

2. **Navigate to Network Configuration**
   - Click on your node (e.g., "gamayun") in the left panel
   - Click "System" → "Network"

3. **Create vmbr0 (WAN)**
   - Click "Create" → "Linux Bridge"
   - Name: `vmbr0`
   - Bridge ports: `enxXXXXXXXXXXXX` (your USB Ethernet, find with `ip link`)
   - IPv4/CIDR: Leave empty (will get DHCP)
   - Comment: `WAN Bridge - to ISP Router (USB-Ethernet)`
   - Autostart: ✓ Checked
   - VLAN aware: ☐ Unchecked
   - Click "Create"

4. **Create vmbr1 (LAN)**
   - Click "Create" → "Linux Bridge"
   - Name: `vmbr1`
   - Bridge ports: `enp3s0` (your built-in Ethernet, check with `ip link`)
   - IPv4/CIDR: `192.168.10.254/24`
   - Comment: `LAN Bridge - to GL.iNet Slate AX (Built-in Ethernet)`
   - Autostart: ✓ Checked
   - VLAN aware: ☐ Unchecked
   - Click "Create"

5. **Create vmbr2 (INTERNAL)**
   - Click "Create" → "Linux Bridge"
   - Name: `vmbr2`
   - Bridge ports: (leave empty)
   - IPv4/CIDR: `10.0.30.1/24`
   - Comment: `INTERNAL Bridge - LXC Containers`
   - Autostart: ✓ Checked
   - VLAN aware: ☐ Unchecked
   - Click "Create"

6. **Create vmbr99 (MGMT)**
   - Click "Create" → "Linux Bridge"
   - Name: `vmbr99`
   - Bridge ports: (leave empty)
   - IPv4/CIDR: `10.0.99.1/24`
   - Comment: `MGMT Bridge - Management Network`
   - Autostart: ✓ Checked
   - VLAN aware: ☐ Unchecked
   - Click "Create"

7. **Apply Configuration**
   - Click "Apply Configuration" button at the top
   - **WARNING:** This will restart networking. SSH connections will drop.
   - Or reboot: `reboot` (safer option)

---

## Setup Method 2: CLI via /etc/network/interfaces

### Step-by-step:

1. **SSH into Proxmox host**
   ```bash
   ssh root@your-proxmox-ip
   ```

2. **Identify physical interfaces**
   ```bash
   ip link show
   ```

   Look for:
   - Built-in Ethernet (usually `enp3s0` or similar)
   - USB Ethernet (usually `enxXXXXXXXXXXXX`)

3. **Backup current configuration**
   ```bash
   cp /etc/network/interfaces /etc/network/interfaces.backup
   ```

4. **Edit network configuration**
   ```bash
   nano /etc/network/interfaces
   ```

5. **Add bridge configurations** (append to file):

```bash
# WAN Bridge - to ISP Router (USB-Ethernet)
auto vmbr0
iface vmbr0 inet dhcp
        bridge-ports enxXXXXXXXXXXXX  # Replace with your USB Ethernet
        bridge-stp off
        bridge-fd 0
        # WAN Bridge - to ISP Router (USB-Ethernet)

# LAN Bridge - to GL.iNet Slate AX (Built-in Ethernet)
auto vmbr1
iface vmbr1 inet static
        address 192.168.10.254/24
        bridge-ports enp3s0  # Replace with your built-in Ethernet
        bridge-stp off
        bridge-fd 0
        # LAN Bridge - to GL.iNet Slate AX (Built-in Ethernet)

# INTERNAL Bridge - LXC Containers
auto vmbr2
iface vmbr2 inet static
        address 10.0.30.1/24
        bridge-ports none
        bridge-stp off
        bridge-fd 0
        # INTERNAL Bridge - LXC Containers

# MGMT Bridge - Management Network
auto vmbr99
iface vmbr99 inet static
        address 10.0.99.1/24
        bridge-ports none
        bridge-stp off
        bridge-fd 0
        # MGMT Bridge - Management Network
```

6. **Validate syntax** (optional but recommended):
   ```bash
   cat /etc/network/interfaces
   ```

7. **Apply configuration**:

   **Option A: Reload networking** (may break SSH):
   ```bash
   systemctl restart networking
   ```

   **Option B: Reboot** (safer):
   ```bash
   reboot
   ```

---

## Setup Method 3: CLI Commands (pvesh)

### Alternative using Proxmox CLI:

```bash
# Create vmbr0 (WAN)
pvesh create /nodes/$(hostname)/network -type bridge \
  -iface vmbr0 \
  -bridge_ports enxXXXXXXXXXXXX \
  -comments 'WAN Bridge - to ISP Router (USB-Ethernet)' \
  -autostart 1

# Create vmbr1 (LAN)
pvesh create /nodes/$(hostname)/network -type bridge \
  -iface vmbr1 \
  -bridge_ports enp3s0 \
  -address 192.168.10.254 \
  -netmask 255.255.255.0 \
  -comments 'LAN Bridge - to GL.iNet Slate AX (Built-in Ethernet)' \
  -autostart 1

# Create vmbr2 (INTERNAL)
pvesh create /nodes/$(hostname)/network -type bridge \
  -iface vmbr2 \
  -address 10.0.30.1 \
  -netmask 255.255.255.0 \
  -comments 'INTERNAL Bridge - LXC Containers' \
  -autostart 1

# Create vmbr99 (MGMT)
pvesh create /nodes/$(hostname)/network -type bridge \
  -iface vmbr99 \
  -address 10.0.99.1 \
  -netmask 255.255.255.0 \
  -comments 'MGMT Bridge - Management Network' \
  -autostart 1

# Apply configuration
ifreload -a
# Or reboot for safety
reboot
```

---

## Verification

### Check bridge status:

```bash
# List all bridges
brctl show

# Check IP addresses
ip addr show

# Verify bridge vmbr0
ip link show vmbr0

# Verify bridge vmbr1
ip link show vmbr1

# Verify bridge vmbr2
ip link show vmbr2

# Verify bridge vmbr99
ip link show vmbr99

# Check connectivity (should get DHCP on vmbr0)
ping -I vmbr0 8.8.8.8

# Check Proxmox network status
pvesh get /nodes/$(hostname)/network
```

### Expected output for `brctl show`:

```
bridge name     bridge id               STP enabled     interfaces
vmbr0           8000.XXXXXXXXXXXX       no              enxXXXXXXXXXXXX
vmbr1           8000.XXXXXXXXXXXX       no              enp3s0
vmbr2           8000.XXXXXXXXXXXX       no
vmbr99          8000.XXXXXXXXXXXX       no
```

### Expected output for `ip addr show`:

```
...
X: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP
    inet 192.168.1.XXX/24 scope global dynamic vmbr0  # DHCP from ISP
...
X: vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP
    inet 192.168.10.254/24 scope global vmbr1
...
X: vmbr2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP
    inet 10.0.30.1/24 scope global vmbr2
...
X: vmbr99: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP
    inet 10.0.99.1/24 scope global vmbr99
...
```

---

## Troubleshooting

### Bridge not appearing
```bash
# Reload networking
systemctl restart networking

# Or reboot
reboot
```

### Cannot access Proxmox Web UI after changes
1. Connect monitor/keyboard directly to server
2. Check `/etc/network/interfaces` for syntax errors
3. Restore from backup: `cp /etc/network/interfaces.backup /etc/network/interfaces`
4. Restart: `systemctl restart networking`

### USB Ethernet not detected
```bash
# List all network interfaces
ip link show

# Check USB devices
lsusb

# Check kernel messages
dmesg | grep -i eth

# May need to replug USB Ethernet adapter
```

### Bridge has no IP
```bash
# Check if interface is up
ip link set vmbr1 up

# Manually assign IP (temporary)
ip addr add 192.168.10.254/24 dev vmbr1

# Check /etc/network/interfaces for typos
```

---

## Ansible Automation (Future)

For automated bridge creation, consider using Ansible:

```yaml
# Example playbook (not tested)
- name: Configure Proxmox network bridges
  hosts: proxmox
  tasks:
    - name: Create vmbr0 (WAN)
      ansible.builtin.template:
        src: templates/interfaces.j2
        dest: /etc/network/interfaces
      notify: restart networking

    - name: Apply network configuration
      ansible.builtin.command: ifreload -a
```

This is safer than Terraform for network changes as you can test with `--check` mode.

---

## Integration with Terraform

Once bridges are created, Terraform will reference them in VM/LXC configurations:

```hcl
# Example from vms.tf
network_device {
  bridge = "vmbr0"  # References manually-created bridge
  model  = "virtio"
}
```

Terraform **does not create** the bridges, only **uses** them.

---

## Physical Interface Identification

To find your interface names:

```bash
# List all interfaces with link status
ip -br link show

# Show detailed interface information
ip link show

# Alternative: use lshw
lshw -class network -short

# Show only Ethernet interfaces
ls /sys/class/net/

# Check which is built-in vs USB:
ethtool enp3s0  # Usually built-in
ethtool enxXXXXXXXXXXXX  # Usually USB (name based on MAC)
```

---

## Post-Setup Checklist

- [ ] All 4 bridges created (vmbr0, vmbr1, vmbr2, vmbr99)
- [ ] vmbr0 has DHCP IP from ISP router
- [ ] vmbr1 has static IP 192.168.10.254/24
- [ ] vmbr2 has static IP 10.0.30.1/24
- [ ] vmbr99 has static IP 10.0.99.1/24
- [ ] Proxmox Web UI accessible (on management IP)
- [ ] Physical ports correctly assigned (USB Ethernet to vmbr0, Built-in to vmbr1)
- [ ] `brctl show` displays all bridges
- [ ] Ready to run Terraform (bridges exist for VM/LXC attachment)

---

## Next Steps

After bridges are configured:

1. **Verify bridge configuration:**
   ```bash
   brctl show
   ip addr show
   ```

2. **Proceed with Terraform:**
   ```bash
   cd generated/terraform
   terraform init
   terraform plan
   terraform apply
   ```

3. **Terraform will use the bridges** to attach VMs/LXC network interfaces.

---

## References

- [Proxmox VE Network Configuration](https://pve.proxmox.com/wiki/Network_Configuration)
- [Linux Bridge Documentation](https://wiki.linuxfoundation.org/networking/bridge)
- [bpg/proxmox Provider Documentation](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)

---

## Maintenance

### Adding a new bridge

1. Edit `topology.yaml` (add to `logical_topology.bridges`)
2. Create bridge manually using one of the methods above
3. Regenerate Terraform: `python3 scripts/generate-terraform.py`
4. Apply Terraform changes

### Modifying bridge IP

1. Edit `topology.yaml`
2. Update bridge IP manually:
   - Via Web UI: System → Network → Edit bridge
   - Via CLI: Edit `/etc/network/interfaces` and `ifreload -a`
3. Regenerate Terraform (for documentation updates)

### Deleting a bridge

```bash
# Remove bridge (will disconnect VMs/LXC using it!)
ip link set vmbr2 down
brctl delbr vmbr2

# Permanent: remove from /etc/network/interfaces
nano /etc/network/interfaces
# Delete bridge section and reboot
```

---

**Last Updated:** 2025-10-22
**Topology Version:** 2.2.0
**Terraform Provider:** bpg/proxmox v0.50.0
