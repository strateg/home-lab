# Network Module Variables
# Proxmox Network Bridges Configuration

# ============================================================
# Node Configuration
# ============================================================

variable "node_name" {
  description = "Proxmox node name"
  type        = string
}

# ============================================================
# Physical Network Interfaces
# ============================================================

variable "wan_interface" {
  description = "WAN interface name (USB-Ethernet, via udev rule)"
  type        = string
  default     = "eth-usb"
}

variable "lan_interface" {
  description = "LAN interface name (Built-in Ethernet, via udev rule)"
  type        = string
  default     = "eth-builtin"
}

variable "wifi_interface" {
  description = "WiFi interface name (optional, for management)"
  type        = string
  default     = "wlan0"
}

# ============================================================
# Network CIDR Blocks
# ============================================================

variable "opnsense_lan_network_cidr" {
  description = "OPNsense LAN network CIDR (vmbr1, to OpenWRT)"
  type        = string
  default     = "192.168.10.254/24"
  # Proxmox will use .254, OPNsense uses .1, OpenWRT uses .2
}

variable "lxc_internal_proxmox_ip_cidr" {
  description = "Proxmox IP on INTERNAL bridge (vmbr2, for LXC)"
  type        = string
  default     = "10.0.30.1/24"
  # LXC containers use 10.0.30.10-90, gateway is OPNsense 10.0.30.254
}

variable "mgmt_proxmox_ip_cidr" {
  description = "Proxmox IP on MGMT bridge (vmbr99, for management)"
  type        = string
  default     = "10.0.99.1/24"
  # OPNsense uses 10.0.99.10 for Web UI access
}

# ============================================================
# Optional Features
# ============================================================

variable "enable_wifi_bridge" {
  description = "Enable WiFi bridge for management/out-of-band access"
  type        = bool
  default     = false
}

variable "wifi_bridge_ip_cidr" {
  description = "WiFi bridge IP and CIDR (if enabled)"
  type        = string
  default     = "192.168.99.1/24"
}

# ============================================================
# VLAN Configuration (optional)
# ============================================================

variable "enable_vlans" {
  description = "Enable VLAN aware bridges"
  type        = bool
  default     = false
}

variable "vlans" {
  description = "VLAN configuration (if enabled)"
  type = map(object({
    id      = number
    name    = string
    network = string
  }))
  default = {
    # guest = {
    #   id      = 30
    #   name    = "Guest WiFi"
    #   network = "192.168.30.0/24"
    # }
    # iot = {
    #   id      = 40
    #   name    = "IoT Devices"
    #   network = "192.168.40.0/24"
    # }
  }
}
