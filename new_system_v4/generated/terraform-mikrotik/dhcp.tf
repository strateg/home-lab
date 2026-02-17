# =============================================================================
# MikroTik DHCP Server Configuration
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

# -----------------------------------------------------------------------------
# DHCP Server: LAN
# -----------------------------------------------------------------------------

resource "routeros_ip_dhcp_server" "dhcp_net_lan" {
  name          = "dhcp-net-lan"
  interface     = "bridge-lan"
  address_pool  = routeros_ip_pool.pool_net_lan.name
  lease_time    = "1d"
  authoritative = "yes"
  comment       = "DHCP server for LAN"

  depends_on = [
    routeros_ip_pool.pool_net_lan,
    routeros_ip_address.net_lan
  ]
}

resource "routeros_ip_dhcp_server_network" "net_net_lan" {
  address    = "192.168.88.0/24"
  gateway    = "192.168.88.1"
  dns_server = ["192.168.88.1"]
  comment    = "LAN DHCP network"
}

# -----------------------------------------------------------------------------
# DHCP Server: Guest WiFi
# -----------------------------------------------------------------------------

resource "routeros_ip_dhcp_server" "dhcp_net_guest" {
  name          = "dhcp-net-guest"
  interface     = "vlan50"
  address_pool  = routeros_ip_pool.pool_net_guest.name
  lease_time    = "1d"
  authoritative = "yes"
  comment       = "DHCP server for Guest WiFi"

  depends_on = [
    routeros_ip_pool.pool_net_guest,
    routeros_ip_address.net_guest
  ]
}

resource "routeros_ip_dhcp_server_network" "net_net_guest" {
  address    = "192.168.30.0/24"
  gateway    = "192.168.30.1"
  dns_server = ["1.1.1.1", "8.8.8.8"]
  comment    = "Guest WiFi DHCP network"
}

# -----------------------------------------------------------------------------
# DHCP Server: IoT Network
# -----------------------------------------------------------------------------

resource "routeros_ip_dhcp_server" "dhcp_net_iot" {
  name          = "dhcp-net-iot"
  interface     = "vlan40"
  address_pool  = routeros_ip_pool.pool_net_iot.name
  lease_time    = "1d"
  authoritative = "yes"
  comment       = "DHCP server for IoT Network"

  depends_on = [
    routeros_ip_pool.pool_net_iot,
    routeros_ip_address.net_iot
  ]
}

resource "routeros_ip_dhcp_server_network" "net_net_iot" {
  address    = "192.168.40.0/24"
  gateway    = "192.168.40.1"
  dns_server = ["192.168.88.1"]
  comment    = "IoT Network DHCP network"
}

# -----------------------------------------------------------------------------
# Static DHCP Leases (Reserved IPs)
# -----------------------------------------------------------------------------

