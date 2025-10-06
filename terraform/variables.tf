# Terraform Variables
# Home Lab Infrastructure
# Dell XPS L701X - 8GB RAM, SSD 180GB + HDD 500GB

# ============================================================
# Proxmox Connection
# ============================================================

variable "proxmox_api_url" {
  description = "Proxmox API URL"
  type        = string
  default     = "https://10.0.99.1:8006/api2/json"
}

variable "proxmox_api_token_id" {
  description = "Proxmox API Token ID (format: user@pam!token_id=secret)"
  type        = string
  sensitive   = true
  # Set via terraform.tfvars or TF_VAR_proxmox_api_token_id
}

variable "proxmox_tls_insecure" {
  description = "Skip TLS verification (self-signed certificates)"
  type        = bool
  default     = true
}

variable "proxmox_ssh_user" {
  description = "SSH user for Proxmox host"
  type        = string
  default     = "root"
}

variable "proxmox_node_name" {
  description = "Proxmox node name"
  type        = string
  default     = "pve"
}

# ============================================================
# Hardware Configuration (Dell XPS L701X)
# ============================================================

variable "hardware_cpu_cores" {
  description = "Total CPU cores available (Core i3-M370 = 2 cores + HT = 4 threads)"
  type        = number
  default     = 2
}

variable "hardware_ram_mb" {
  description = "Total RAM in MB (8 GB DDR3)"
  type        = number
  default     = 8192
}

variable "hardware_ssd_size_gb" {
  description = "SSD size in GB (production VMs)"
  type        = number
  default     = 180
}

variable "hardware_hdd_size_gb" {
  description = "HDD size in GB (templates, backups)"
  type        = number
  default     = 500
}

# ============================================================
# Network Interfaces
# ============================================================

variable "wan_interface" {
  description = "WAN interface name (USB-Ethernet)"
  type        = string
  default     = "eth-usb"  # via udev rule
}

variable "lan_interface" {
  description = "LAN interface name (built-in Ethernet)"
  type        = string
  default     = "eth-builtin"  # via udev rule
}

variable "wifi_interface" {
  description = "WiFi interface name (management, optional)"
  type        = string
  default     = "wlan0"
}

# ============================================================
# Network Configuration
# ============================================================

# ISP Network
variable "isp_network" {
  description = "ISP Router network"
  type        = string
  default     = "192.168.1.0/24"
}

variable "isp_gateway" {
  description = "ISP Router gateway"
  type        = string
  default     = "192.168.1.1"
}

# OPNsense LAN (to OpenWRT)
variable "opnsense_lan_network" {
  description = "OPNsense LAN network (to OpenWRT)"
  type        = string
  default     = "192.168.10.0/24"
}

variable "opnsense_lan_gateway" {
  description = "OPNsense LAN gateway"
  type        = string
  default     = "192.168.10.1"
}

# OpenWRT LAN (home clients)
variable "openwrt_lan_network" {
  description = "OpenWRT LAN network (home clients)"
  type        = string
  default     = "192.168.20.0/24"
}

variable "openwrt_lan_gateway" {
  description = "OpenWRT LAN gateway"
  type        = string
  default     = "192.168.20.1"
}

# LXC Internal Network
variable "lxc_internal_network" {
  description = "LXC containers internal network"
  type        = string
  default     = "10.0.30.0/24"
}

variable "lxc_internal_gateway" {
  description = "LXC internal gateway (OPNsense)"
  type        = string
  default     = "10.0.30.254"
}

variable "lxc_internal_proxmox_ip" {
  description = "Proxmox host IP on INTERNAL bridge"
  type        = string
  default     = "10.0.30.1"
}

# Management Network
variable "mgmt_network" {
  description = "Management network"
  type        = string
  default     = "10.0.99.0/24"
}

variable "mgmt_proxmox_ip" {
  description = "Proxmox host IP on MGMT bridge"
  type        = string
  default     = "10.0.99.1"
}

variable "mgmt_opnsense_ip" {
  description = "OPNsense IP on MGMT bridge"
  type        = string
  default     = "10.0.99.10"
}

# VPN Networks
variable "vpn_wireguard_network" {
  description = "WireGuard VPN network (Slate AX server)"
  type        = string
  default     = "10.0.200.0/24"
}

variable "vpn_amneziawg_network" {
  description = "AmneziaWG VPN network (Slate AX server, Russia clients)"
  type        = string
  default     = "10.8.2.0/24"
}

# ============================================================
# Storage Configuration
# ============================================================

variable "storage_ssd_id" {
  description = "SSD storage ID (for production VMs)"
  type        = string
  default     = "local-lvm"
}

variable "storage_hdd_id" {
  description = "HDD storage ID (for templates, backups)"
  type        = string
  default     = "local-hdd"
}

variable "storage_local_id" {
  description = "Local storage ID (for ISOs, snippets)"
  type        = string
  default     = "local"
}

# ============================================================
# VM/LXC Defaults
# ============================================================

variable "default_vm_cpu_type" {
  description = "Default CPU type for VMs"
  type        = string
  default     = "host"
}

variable "default_vm_bios" {
  description = "Default BIOS type for VMs"
  type        = string
  default     = "seabios"  # or "ovmf" for UEFI
}

variable "default_lxc_ostemplate" {
  description = "Default OS template for LXC containers"
  type        = string
  default     = "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"
}

# ============================================================
# SSH Configuration
# ============================================================

variable "ssh_public_key" {
  description = "SSH public key for VM/LXC access"
  type        = string
  default     = ""  # Set via terraform.tfvars
}

variable "ssh_private_key_path" {
  description = "Path to SSH private key"
  type        = string
  default     = "~/.ssh/id_rsa"
}

# ============================================================
# Tags & Labels
# ============================================================

variable "default_tags" {
  description = "Default tags for all resources"
  type        = list(string)
  default     = ["terraform", "home-lab", "production"]
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

# ============================================================
# Feature Flags
# ============================================================

variable "enable_monitoring" {
  description = "Enable monitoring stack (Grafana, Prometheus)"
  type        = bool
  default     = true
}

variable "enable_backups" {
  description = "Enable automatic backups"
  type        = bool
  default     = true
}

variable "enable_vpn_servers" {
  description = "Enable VPN servers on OpenWRT (WireGuard, AmneziaWG)"
  type        = bool
  default     = true
}
