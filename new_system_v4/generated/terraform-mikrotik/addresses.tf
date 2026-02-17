# =============================================================================
# MikroTik IP Address Configuration
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

# -----------------------------------------------------------------------------
# Bridge/VLAN IP Addresses
# -----------------------------------------------------------------------------

resource "routeros_ip_address" "net_lan" {
  address   = "192.168.88.1/24"
  interface = "bridge-lan"
  comment   = "LAN gateway"
}

resource "routeros_ip_address" "net_servers" {
  address   = "10.0.30.1/24"
  interface = "vlan30"
  comment   = "Servers gateway"

  depends_on = [routeros_interface_vlan.vlan30]
}

resource "routeros_ip_address" "net_guest" {
  address   = "192.168.30.1/24"
  interface = "vlan50"
  comment   = "Guest WiFi gateway"

  depends_on = [routeros_interface_vlan.vlan50]
}

resource "routeros_ip_address" "net_iot" {
  address   = "192.168.40.1/24"
  interface = "vlan40"
  comment   = "IoT Network gateway"

  depends_on = [routeros_interface_vlan.vlan40]
}

resource "routeros_ip_address" "net_management" {
  address   = "10.0.99.1/24"
  interface = "vlan99"
  comment   = "Management gateway"

  depends_on = [routeros_interface_vlan.vlan99]
}

resource "routeros_ip_address" "net_vpn_home" {
  address   = "10.0.200.1/24"
  interface = "bridge-lan"
  comment   = "VPN Home gateway"
}

# -----------------------------------------------------------------------------
# IP Pool Configuration (for DHCP)
# -----------------------------------------------------------------------------

resource "routeros_ip_pool" "pool_net_lan" {
  name    = "pool-net-lan"
  ranges  = ["192.168.88.100-192.168.88.200"]
  comment = "DHCP pool for LAN"
}

resource "routeros_ip_pool" "pool_net_guest" {
  name    = "pool-net-guest"
  ranges  = ["192.168.30.100-192.168.30.200"]
  comment = "DHCP pool for Guest WiFi"
}

resource "routeros_ip_pool" "pool_net_iot" {
  name    = "pool-net-iot"
  ranges  = ["192.168.40.100-192.168.40.200"]
  comment = "DHCP pool for IoT Network"
}

