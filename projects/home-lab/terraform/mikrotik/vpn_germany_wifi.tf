# VPN Germany WiFi configuration
# This file is manually maintained until projection supports WiFi extraction
# Matches router config: wifi-vpn-germany with VLAN 55 datapath

# WiFi Datapath for VLAN 55 tagging
resource "routeros_interface_wifi_datapath" "dp_vpn_germany" {
  name    = "dp-vpn-germany"
  bridge  = "bridge"
  vlan_id = 55
  comment = "VPN Germany VLAN 55 - managed by topology"

  lifecycle {
    create_before_destroy = false
  }
}

# WiFi Security profile for VPN Germany
resource "routeros_interface_wifi_security" "sec_vpn_germany" {
  name                 = "sec-vpn-germany"
  authentication_types = ["wpa2-psk"]
  passphrase           = var.wifi_vpn_germany_passphrase
  wps                  = "disable"
  comment              = "VPN Germany security - managed by topology"

  lifecycle {
    create_before_destroy = false
  }
}

# WiFi Configuration (SSID) for VPN Germany
resource "routeros_interface_wifi_configuration" "cfg_vpn_germany" {
  name     = "cfg-vpn-germany"
  ssid     = "VPN-Germany"
  mode     = "ap"
  security = routeros_interface_wifi_security.sec_vpn_germany.name
  datapath = routeros_interface_wifi_datapath.dp_vpn_germany.name
  comment  = "VPN Germany WiFi - managed by topology"

  lifecycle {
    create_before_destroy = false
  }
}

# Bridge VLAN entry for VLAN 55 (tagged on bridge for VLAN interface)
resource "routeros_interface_bridge_vlan" "vlan_55" {
  bridge   = "bridge"
  vlan_ids = ["55"]
  tagged   = ["bridge"]
  comment  = "VLAN 55 VPN Germany - managed by topology"

  lifecycle {
    create_before_destroy = false
  }
}
