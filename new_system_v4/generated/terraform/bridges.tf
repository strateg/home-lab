# ============================================================
# Network Bridges Configuration
# Generated from topology.yaml v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with scripts/generate-terraform.py
# ============================================================

# vmbr0 - LAN trunk bridge to MikroTik (VLAN-aware)
# Ports: enp3s0

resource "proxmox_virtual_environment_network_linux_bridge" "bridge_vmbr0" {
  node_name = var.proxmox_node

  name    = "vmbr0"
  comment = "LAN trunk bridge to MikroTik (VLAN-aware)"

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
  }
}