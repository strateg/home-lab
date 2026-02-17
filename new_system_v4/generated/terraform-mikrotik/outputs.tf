# =============================================================================
# MikroTik Terraform Outputs
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

# -----------------------------------------------------------------------------
# System Information
# -----------------------------------------------------------------------------

output "router_identity" {
  description = "MikroTik router identity"
  value       = routeros_system_identity.router.name
}

# -----------------------------------------------------------------------------
# Network Configuration
# -----------------------------------------------------------------------------

output "networks" {
  description = "Configured networks"
  value = {
    "net-lan" = {
      name    = "LAN"
      cidr    = "192.168.88.0/24"
      gateway = "192.168.88.1"
      vlan    = null
    }
    "net-servers" = {
      name    = "Servers"
      cidr    = "10.0.30.0/24"
      gateway = "10.0.30.1"
      vlan    = 30
    }
    "net-guest" = {
      name    = "Guest WiFi"
      cidr    = "192.168.30.0/24"
      gateway = "192.168.30.1"
      vlan    = 50
    }
    "net-iot" = {
      name    = "IoT Network"
      cidr    = "192.168.40.0/24"
      gateway = "192.168.40.1"
      vlan    = 40
    }
    "net-management" = {
      name    = "Management"
      cidr    = "10.0.99.0/24"
      gateway = "10.0.99.1"
      vlan    = 99
    }
    "net-vpn-home" = {
      name    = "VPN Home"
      cidr    = "10.0.200.0/24"
      gateway = "10.0.200.1"
      vlan    = null
    }
    "net-tailscale" = {
      name    = "Tailscale Mesh"
      cidr    = "100.64.0.0/10"
      gateway = "None"
      vlan    = null
    }
  }
}

# -----------------------------------------------------------------------------
# VLAN Configuration
# -----------------------------------------------------------------------------

output "vlans" {
  description = "Configured VLANs"
  value = {
    "30" = {
      name        = "Servers"
      network_ref = "net-servers"
    }
    "50" = {
      name        = "Guest WiFi"
      network_ref = "net-guest"
    }
    "40" = {
      name        = "IoT Network"
      network_ref = "net-iot"
    }
    "99" = {
      name        = "Management"
      network_ref = "net-management"
    }
  }
}

# -----------------------------------------------------------------------------
# VPN Information
# -----------------------------------------------------------------------------

output "wireguard_interface" {
  description = "WireGuard interface name"
  value       = routeros_interface_wireguard.wg_home.name
}

output "wireguard_public_key" {
  description = "WireGuard server public key (share with peers)"
  value       = routeros_interface_wireguard.wg_home.public_key
  sensitive   = false
}

output "wireguard_endpoint" {
  description = "WireGuard endpoint configuration"
  value = {
    port    = 51820
    network = "10.0.200.0/24"
  }
}

# -----------------------------------------------------------------------------
# Container Status
# -----------------------------------------------------------------------------

output "containers" {
  description = "Deployed containers"
  value = {
    adguard = {
      name     = routeros_container.adguard.hostname
      image    = routeros_container.adguard.remote_image
      interface = routeros_interface_veth.adguard_veth.name
      ip       = routeros_interface_veth.adguard_veth.address
    }
    tailscale = {
      name     = routeros_container.tailscale.hostname
      image    = routeros_container.tailscale.remote_image
      interface = routeros_interface_veth.tailscale_veth.name
      ip       = routeros_interface_veth.tailscale_veth.address
    }
  }
}

# -----------------------------------------------------------------------------
# Management Access
# -----------------------------------------------------------------------------

output "management_urls" {
  description = "Management interface URLs"
  value = {
    webfig    = "https://192.168.88.1/"
    api       = "https://192.168.88.1:8443/"
    adguard   = "http://192.168.88.1:3000/"
    winbox    = "192.168.88.1:8291"
  }
}

# -----------------------------------------------------------------------------
# Infrastructure Summary
# -----------------------------------------------------------------------------

output "infrastructure_summary" {
  description = "MikroTik infrastructure summary"
  value = <<-EOT
    ╔══════════════════════════════════════════════════════════════════════╗
    ║  MikroTik RouterOS Configuration - Topology v4.0.0
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  Router: MikroTik Chateau LTE7 ax
    ║
    ║  Networks:
    ║    - LAN: 192.168.88.0/24
    ║    - Servers: 10.0.30.0/24 (VLAN 30)
    ║    - Guest WiFi: 192.168.30.0/24 (VLAN 50)
    ║    - IoT Network: 192.168.40.0/24 (VLAN 40)
    ║    - Management: 10.0.99.0/24 (VLAN 99)
    ║    - VPN Home: 10.0.200.0/24
    ║    - Tailscale Mesh: 100.64.0.0/10
    ║
    ║  Services:
    ║    - DNS: AdGuard Home (container)
    ║    - VPN: WireGuard + Tailscale
    ║    - LTE Failover: Active
    ║
    ╚══════════════════════════════════════════════════════════════════════╝
  EOT
}