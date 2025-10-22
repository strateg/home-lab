# Network Module Outputs
# Information about created network bridges

# ============================================================
# Bridge Names
# ============================================================

output "vmbr0_name" {
  description = "WAN bridge name"
  value       = proxmox_virtual_environment_network_linux_bridge.vmbr0.name
}

output "vmbr1_name" {
  description = "LAN bridge name"
  value       = proxmox_virtual_environment_network_linux_bridge.vmbr1.name
}

output "vmbr2_name" {
  description = "INTERNAL bridge name"
  value       = proxmox_virtual_environment_network_linux_bridge.vmbr2.name
}

output "vmbr99_name" {
  description = "MGMT bridge name"
  value       = proxmox_virtual_environment_network_linux_bridge.vmbr99.name
}

# ============================================================
# Bridge IDs (for reference in VM/LXC configs)
# ============================================================

output "wan_bridge" {
  description = "WAN bridge identifier (for VM/LXC network config)"
  value       = "vmbr0"
}

output "lan_bridge" {
  description = "LAN bridge identifier (for VM/LXC network config)"
  value       = "vmbr1"
}

output "internal_bridge" {
  description = "INTERNAL bridge identifier (for LXC network config)"
  value       = "vmbr2"
}

output "mgmt_bridge" {
  description = "MGMT bridge identifier (for VM/LXC network config)"
  value       = "vmbr99"
}

# ============================================================
# Network Configuration Summary
# ============================================================

output "network_summary" {
  description = "Network bridges configuration summary"
  value = {
    wan_bridge = {
      name      = proxmox_virtual_environment_network_linux_bridge.vmbr0.name
      interface = var.wan_interface
      purpose   = "WAN - to ISP Router"
    }
    lan_bridge = {
      name      = proxmox_virtual_environment_network_linux_bridge.vmbr1.name
      interface = var.lan_interface
      ip        = var.opnsense_lan_network_cidr
      purpose   = "LAN - to OpenWRT"
    }
    internal_bridge = {
      name    = proxmox_virtual_environment_network_linux_bridge.vmbr2.name
      ip      = var.lxc_internal_proxmox_ip_cidr
      purpose = "INTERNAL - LXC Containers"
    }
    mgmt_bridge = {
      name    = proxmox_virtual_environment_network_linux_bridge.vmbr99.name
      ip      = var.mgmt_proxmox_ip_cidr
      purpose = "MGMT - Management network"
    }
  }
}

# ============================================================
# Physical Interfaces Mapping
# ============================================================

output "interface_mapping" {
  description = "Physical interface to bridge mapping"
  value = {
    wan_interface  = var.wan_interface
    lan_interface  = var.lan_interface
    wifi_interface = var.wifi_interface
  }
}
