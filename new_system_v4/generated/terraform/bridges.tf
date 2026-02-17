# ============================================================
# Network Bridges Configuration
# Generated from topology.yaml v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with scripts/generate-terraform.py
# ============================================================

# vmbr0 - LAN Bridge - to MikroTik (Built-in Ethernet)
# Ports: enp3s0

resource "proxmox_virtual_environment_network_linux_bridge" "bridge_vmbr0" {
  node_name = var.proxmox_node

  name    = "vmbr0"
  comment = "LAN Bridge - to MikroTik (Built-in Ethernet)"

  ports = ["enp3s0"]

  address = "192.168.88.2/24"

  gateway = "192.168.88.1"

  vlan_aware = true

  autostart = true

  # Lifecycle management
  lifecycle {
    ignore_changes = [
      # Ignore changes to these attributes as they may be managed outside Terraform
      # or change dynamically (e.g., DHCP-assigned IP)
    ]
  }
}

# vmbr2 - Servers Bridge - LXC Containers (VLAN 30)
# Ports: none (internal only)

resource "proxmox_virtual_environment_network_linux_bridge" "bridge_vmbr2" {
  node_name = var.proxmox_node

  name    = "vmbr2"
  comment = "Servers Bridge - LXC Containers (VLAN 30)"


  address = "10.0.30.2/24"

  gateway = "10.0.30.1"

  vlan_aware = false

  autostart = true

  # Lifecycle management
  lifecycle {
    ignore_changes = [
      # Ignore changes to these attributes as they may be managed outside Terraform
      # or change dynamically (e.g., DHCP-assigned IP)
    ]
  }
}

# vmbr99 - Management Bridge (VLAN 99)
# Ports: none (internal only)

resource "proxmox_virtual_environment_network_linux_bridge" "bridge_vmbr99" {
  node_name = var.proxmox_node

  name    = "vmbr99"
  comment = "Management Bridge (VLAN 99)"


  address = "10.0.99.2/24"

  gateway = "10.0.99.1"

  vlan_aware = false

  autostart = true

  # Lifecycle management
  lifecycle {
    ignore_changes = [
      # Ignore changes to these attributes as they may be managed outside Terraform
      # or change dynamically (e.g., DHCP-assigned IP)
    ]
  }
}


# ============================================================
# Outputs
# ============================================================

output "bridges" {
  description = "Network bridges configuration"
  value = {
    bridge_vmbr0 = {
      name        = proxmox_virtual_environment_network_linux_bridge.bridge_vmbr0.name
      bridge_name = "vmbr0"
      address     = "192.168.88.2/24"
      ports       = ["enp3s0"]
    }
    bridge_vmbr2 = {
      name        = proxmox_virtual_environment_network_linux_bridge.bridge_vmbr2.name
      bridge_name = "vmbr2"
      address     = "10.0.30.2/24"
      ports       = []
    }
    bridge_vmbr99 = {
      name        = proxmox_virtual_environment_network_linux_bridge.bridge_vmbr99.name
      bridge_name = "vmbr99"
      address     = "10.0.99.2/24"
      ports       = []
    }
  }
}