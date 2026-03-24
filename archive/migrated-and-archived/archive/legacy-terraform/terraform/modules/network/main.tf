# Terraform Network Module
# Proxmox Network Bridges (vmbr0, vmbr1, vmbr2, vmbr99)
# Dell XPS L701X: USB-Ethernet (WAN) + Built-in Ethernet (LAN)

# ============================================================
# Network Bridges
# ============================================================

# vmbr0 - WAN Bridge (to ISP Router)
resource "proxmox_virtual_environment_network_linux_bridge" "vmbr0" {
  node_name = var.node_name
  name      = "vmbr0"
  comment   = "WAN Bridge - to ISP Router (USB-Ethernet)"

  # USB-Ethernet adapter (via udev rule: eth-usb)
  ports = [var.wan_interface]

  # No IP address on bridge (DHCP from ISP)
  # OPNsense will handle WAN IP via DHCP
  autostart = true
}

# vmbr1 - LAN Bridge (to OpenWRT)
resource "proxmox_virtual_environment_network_linux_bridge" "vmbr1" {
  node_name = var.node_name
  name      = "vmbr1"
  comment   = "LAN Bridge - to OpenWRT (Built-in Ethernet)"

  # Built-in Ethernet adapter (via udev rule: eth-builtin)
  ports = [var.lan_interface]

  # Static IP for Proxmox on LAN bridge
  # This allows Proxmox to communicate with OPNsense and OpenWRT
  address = "${var.opnsense_lan_network_cidr}"
  # Example: "192.168.10.254/24"

  autostart = true

  # VLAN aware (опционально, если нужны VLANs)
  vlan_aware = false
}

# vmbr2 - INTERNAL Bridge (LXC Containers)
resource "proxmox_virtual_environment_network_linux_bridge" "vmbr2" {
  node_name = var.node_name
  name      = "vmbr2"
  comment   = "INTERNAL Bridge - LXC Containers (no physical port)"

  # No physical ports (software bridge only)
  # LXC containers connect here, gateway via OPNsense (10.0.30.254)

  # Static IP for Proxmox on INTERNAL bridge
  # Allows Proxmox to access LXC containers directly
  address = "${var.lxc_internal_proxmox_ip_cidr}"
  # Example: "10.0.30.1/24"

  autostart = true
}

# vmbr99 - MGMT Bridge (Management)
resource "proxmox_virtual_environment_network_linux_bridge" "vmbr99" {
  node_name = var.node_name
  name      = "vmbr99"
  comment   = "MGMT Bridge - Management network (no physical port)"

  # No physical ports (software bridge only)
  # For accessing Proxmox Web UI and OPNsense management interface

  # Static IP for Proxmox on MGMT bridge
  address = "${var.mgmt_proxmox_ip_cidr}"
  # Example: "10.0.99.1/24"

  autostart = true
}

# ============================================================
# Optional: WiFi Bridge (for management/out-of-band access)
# ============================================================

# Uncomment if you want to use WiFi for management
# resource "proxmox_virtual_environment_network_linux_bridge" "vmbr_wifi" {
#   count     = var.enable_wifi_bridge ? 1 : 0
#   node_name = var.node_name
#   name      = "vmbr-wifi"
#   comment   = "WiFi Bridge - Management/Out-of-band access"
#
#   ports = [var.wifi_interface]
#   address = var.wifi_bridge_ip_cidr
#   autostart = true
# }

# ============================================================
# Network Routes (если нужна дополнительная маршрутизация)
# ============================================================

# Example: Static route to LXC network via OPNsense
# This ensures Proxmox can route to LXC containers through OPNsense
# Usually configured via /etc/network/interfaces, but can be managed here

# Note: Proxmox network configuration is typically done via /etc/network/interfaces
# This Terraform module creates bridges, but additional routing may require
# post-configuration scripts or Ansible
