# =============================================================================
# MikroTik Interface Configuration
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

# -----------------------------------------------------------------------------
# Bridge Configuration
# -----------------------------------------------------------------------------

resource "routeros_interface_bridge" "lan" {
  name           = "bridge-lan"
  comment        = "Main LAN Bridge"
  vlan_filtering = true
  pvid           = 1
  frame_types    = "admit-all"
  igmp_snooping  = true
  protocol_mode  = "rstp"
}

# -----------------------------------------------------------------------------
# Bridge Ports (LAN ports to bridge)
# -----------------------------------------------------------------------------

resource "routeros_interface_bridge_port" "lan1" {
  bridge    = routeros_interface_bridge.lan.name
  interface = "if-mikrotik-lan1"
  pvid      = 1
  comment   = "LAN port 1 - Proxmox"

  depends_on = [routeros_interface_bridge.lan]
}

resource "routeros_interface_bridge_port" "lan2" {
  bridge    = routeros_interface_bridge.lan.name
  interface = "if-mikrotik-lan2"
  pvid      = 1
  comment   = "LAN port 2 - Orange Pi 5"

  depends_on = [routeros_interface_bridge.lan]
}

resource "routeros_interface_bridge_port" "lan3" {
  bridge    = routeros_interface_bridge.lan.name
  interface = "if-mikrotik-lan3"
  pvid      = 1
  comment   = "LAN port 3 - reserved"

  depends_on = [routeros_interface_bridge.lan]
}

resource "routeros_interface_bridge_port" "lan4" {
  bridge    = routeros_interface_bridge.lan.name
  interface = "if-mikrotik-lan4"
  pvid      = 1
  comment   = "LAN port 4 - reserved"

  depends_on = [routeros_interface_bridge.lan]
}

# -----------------------------------------------------------------------------
# VLAN Interfaces
# -----------------------------------------------------------------------------

resource "routeros_interface_vlan" "vlan30" {
  name      = "vlan30"
  vlan_id   = 30
  interface = routeros_interface_bridge.lan.name
  comment   = "Servers (net-servers)"

  depends_on = [routeros_interface_bridge.lan]
}

resource "routeros_interface_vlan" "vlan50" {
  name      = "vlan50"
  vlan_id   = 50
  interface = routeros_interface_bridge.lan.name
  comment   = "Guest WiFi (net-guest)"

  depends_on = [routeros_interface_bridge.lan]
}

resource "routeros_interface_vlan" "vlan40" {
  name      = "vlan40"
  vlan_id   = 40
  interface = routeros_interface_bridge.lan.name
  comment   = "IoT Network (net-iot)"

  depends_on = [routeros_interface_bridge.lan]
}

resource "routeros_interface_vlan" "vlan99" {
  name      = "vlan99"
  vlan_id   = 99
  interface = routeros_interface_bridge.lan.name
  comment   = "Management (net-management)"

  depends_on = [routeros_interface_bridge.lan]
}

# -----------------------------------------------------------------------------
# Bridge VLAN Filtering
# -----------------------------------------------------------------------------

resource "routeros_interface_bridge_vlan" "vlan30" {
  bridge   = routeros_interface_bridge.lan.name
  vlan_ids = [30]
  tagged   = [routeros_interface_bridge.lan.name]
  comment  = "Servers"

  depends_on = [routeros_interface_vlan.vlan30]
}

resource "routeros_interface_bridge_vlan" "vlan50" {
  bridge   = routeros_interface_bridge.lan.name
  vlan_ids = [50]
  tagged   = [routeros_interface_bridge.lan.name]
  comment  = "Guest WiFi"

  depends_on = [routeros_interface_vlan.vlan50]
}

resource "routeros_interface_bridge_vlan" "vlan40" {
  bridge   = routeros_interface_bridge.lan.name
  vlan_ids = [40]
  tagged   = [routeros_interface_bridge.lan.name]
  comment  = "IoT Network"

  depends_on = [routeros_interface_vlan.vlan40]
}

resource "routeros_interface_bridge_vlan" "vlan99" {
  bridge   = routeros_interface_bridge.lan.name
  vlan_ids = [99]
  tagged   = [routeros_interface_bridge.lan.name]
  comment  = "Management"

  depends_on = [routeros_interface_vlan.vlan99]
}

# -----------------------------------------------------------------------------
# WiFi Interfaces (if managed by Terraform)
# -----------------------------------------------------------------------------
# Note: WiFi configuration via Terraform is complex and may require
# manual setup. See bootstrap/mikrotik/README.md for WiFi setup guide.

# WiFi 5GHz - wlan1
# WiFi 2.4GHz - wlan2
# Guest VLAN assignment is handled in CAPsMAN or WiFi configuration

# -----------------------------------------------------------------------------
# WAN Interface (ether1 - 2.5GbE)
# -----------------------------------------------------------------------------
# WAN interface is configured via DHCP client, not managed here
# LTE interface (lte1) is configured separately for failover