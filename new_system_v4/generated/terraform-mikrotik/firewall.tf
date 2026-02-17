# =============================================================================
# MikroTik Firewall Configuration
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

# -----------------------------------------------------------------------------
# Address Lists
# -----------------------------------------------------------------------------

resource "routeros_ip_firewall_addr_list" "lan_networks" {
  list    = "LAN"
  address = "192.168.88.0/24"
  comment = "Main LAN network"
}

resource "routeros_ip_firewall_addr_list" "servers_network" {
  list    = "SERVERS"
  address = "10.0.30.0/24"
  comment = "Servers network"
}

resource "routeros_ip_firewall_addr_list" "management_network" {
  list    = "MANAGEMENT"
  address = "10.0.99.0/24"
  comment = "Management network"
}

resource "routeros_ip_firewall_addr_list" "vpn_network" {
  list    = "VPN"
  address = "10.0.200.0/24"
  comment = "WireGuard VPN network"
}

resource "routeros_ip_firewall_addr_list" "guest_network" {
  list    = "GUEST"
  address = "192.168.30.0/24"
  comment = "Guest WiFi network"
}

resource "routeros_ip_firewall_addr_list" "iot_network" {
  list    = "IOT"
  address = "192.168.40.0/24"
  comment = "IoT network"
}

# -----------------------------------------------------------------------------
# Firewall Filter Rules - Input Chain
# -----------------------------------------------------------------------------

resource "routeros_ip_firewall_filter" "input_established" {
  chain            = "input"
  action           = "accept"
  connection_state = "established,related"
  comment          = "Accept established/related connections"
}

resource "routeros_ip_firewall_filter" "input_icmp" {
  chain    = "input"
  action   = "accept"
  protocol = "icmp"
  comment  = "Accept ICMP (ping)"
}

resource "routeros_ip_firewall_filter" "input_ssh_lan" {
  chain        = "input"
  action       = "accept"
  protocol     = "tcp"
  dst_port     = "22"
  src_address_list = "LAN"
  comment      = "Accept SSH from LAN"
}

resource "routeros_ip_firewall_filter" "input_winbox" {
  chain        = "input"
  action       = "accept"
  protocol     = "tcp"
  dst_port     = "8291"
  src_address_list = "LAN"
  comment      = "Accept Winbox from LAN"
}

resource "routeros_ip_firewall_filter" "input_api" {
  chain        = "input"
  action       = "accept"
  protocol     = "tcp"
  dst_port     = "8443"
  src_address_list = "MANAGEMENT"
  comment      = "Accept REST API from management network"
}

resource "routeros_ip_firewall_filter" "input_dns" {
  chain    = "input"
  action   = "accept"
  protocol = "udp"
  dst_port = "53"
  comment  = "Accept DNS queries"
}

resource "routeros_ip_firewall_filter" "input_dhcp" {
  chain    = "input"
  action   = "accept"
  protocol = "udp"
  dst_port = "67"
  comment  = "Accept DHCP requests"
}

resource "routeros_ip_firewall_filter" "input_wireguard" {
  chain        = "input"
  action       = "accept"
  protocol     = "udp"
  dst_port     = "51820"
  in_interface = "ether1"
  comment      = "Accept WireGuard from WAN"
}

resource "routeros_ip_firewall_filter" "input_drop_wan" {
  chain        = "input"
  action       = "drop"
  in_interface = "ether1"
  comment      = "Drop all other input from WAN"
  log          = true
  log_prefix   = "DROP_INPUT_WAN:"
}

# -----------------------------------------------------------------------------
# Firewall Filter Rules - Forward Chain
# -----------------------------------------------------------------------------

resource "routeros_ip_firewall_filter" "forward_established" {
  chain            = "forward"
  action           = "accept"
  connection_state = "established,related"
  comment          = "Accept established/related forward"
}

resource "routeros_ip_firewall_filter" "forward_invalid" {
  chain            = "forward"
  action           = "drop"
  connection_state = "invalid"
  comment          = "Drop invalid connections"
}

resource "routeros_ip_firewall_filter" "fw_default_deny" {
  chain  = "forward"
  action = "drop"
  comment = "Default Deny: Drop all traffic by default, allow explicitly"
}

resource "routeros_ip_firewall_filter" "fw_established_related" {
  chain  = "forward"
  action = "accept"
  comment = "Allow Established/Related: Allow established and related connections"
}

resource "routeros_ip_firewall_filter" "fw_servers_internet" {
  chain  = "forward"
  action = "accept"
  src_address_list = "SERVERS"
  dst_address_list = "UNTRUSTED"
  comment = "Servers to Internet: Servers can access internet"
}

resource "routeros_ip_firewall_filter" "fw_user_servers" {
  chain  = "forward"
  action = "accept"
  src_address_list = "USER"
  dst_address_list = "SERVERS"
  protocol = "tcp"
  dst_port = "80,443,5432,6379,8096,3000,9090"
  comment = "User to Server Services: User devices can access server services"
}

resource "routeros_ip_firewall_filter" "fw_guest_isolated" {
  chain  = "forward"
  action = "drop"
  src_address_list = "GUEST"
  comment = "Guest Isolation: Guest network cannot access any internal networks"
}

resource "routeros_ip_firewall_filter" "fw_iot_isolated" {
  chain  = "forward"
  action = "drop"
  src_address_list = "IOT"
  comment = "IoT Isolation: IoT cannot access other networks (except internet)"
}

resource "routeros_ip_firewall_filter" "fw_iot_internet" {
  chain  = "forward"
  action = "accept"
  src_address_list = "IOT"
  dst_address_list = "UNTRUSTED"
  comment = "IoT to Internet: IoT can access internet"
}

resource "routeros_ip_firewall_filter" "fw_management_admin" {
  chain  = "forward"
  action = "accept"
  src_address = "192.168.88.0/24"
  dst_address_list = "MANAGEMENT"
  protocol = "tcp"
  dst_port = "8006,443,22,80"
  comment = "Management Access Control: Allow admin access from LAN to management interfaces"
}

resource "routeros_ip_firewall_filter" "fw_vpn_full_access" {
  chain  = "forward"
  action = "accept"
  src_address = "10.0.200.0/24"
  comment = "VPN Full Access: VPN clients have full network access"
}

resource "routeros_ip_firewall_filter" "fw_tailscale_access" {
  chain  = "forward"
  action = "accept"
  src_address = "100.64.0.0/10"
  comment = "Tailscale Access: Tailscale mesh clients can access LAN and servers"
}

# Default drop for forward
resource "routeros_ip_firewall_filter" "forward_drop_default" {
  chain   = "forward"
  action  = "drop"
  comment = "Default drop all forward"
  log     = true
  log_prefix = "DROP_FORWARD:"
}

# -----------------------------------------------------------------------------
# NAT Rules
# -----------------------------------------------------------------------------

resource "routeros_ip_firewall_nat" "masquerade_wan" {
  chain        = "srcnat"
  action       = "masquerade"
  out_interface = "ether1"
  comment      = "Masquerade outgoing traffic on WAN"
}

resource "routeros_ip_firewall_nat" "masquerade_lte" {
  chain        = "srcnat"
  action       = "masquerade"
  out_interface = "lte1"
  comment      = "Masquerade outgoing traffic on LTE failover"
}

# DNS redirect to AdGuard container
resource "routeros_ip_firewall_nat" "dns_redirect" {
  chain       = "dstnat"
  action      = "dst-nat"
  protocol    = "udp"
  dst_port    = "53"
  to_addresses = "192.168.88.1"
  to_ports    = "53"
  comment     = "Redirect DNS to AdGuard"
}