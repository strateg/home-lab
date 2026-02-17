# =============================================================================
# MikroTik Terraform Variables
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

# -----------------------------------------------------------------------------
# MikroTik Connection
# -----------------------------------------------------------------------------

variable "mikrotik_host" {
  description = "MikroTik router URL (https://ip:port)"
  type        = string
  default     = "https://192.168.88.1:8443"
}

variable "mikrotik_username" {
  description = "MikroTik API username"
  type        = string
  default     = "terraform"
}

variable "mikrotik_password" {
  description = "MikroTik API password"
  type        = string
  sensitive   = true
}

variable "mikrotik_insecure" {
  description = "Skip TLS certificate verification"
  type        = bool
  default     = true  # Set to false with valid certificate
}

# -----------------------------------------------------------------------------
# WireGuard VPN
# -----------------------------------------------------------------------------

variable "wireguard_private_key" {
  description = "WireGuard server private key (generate with: wg genkey)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "wireguard_peers" {
  description = "List of WireGuard peers"
  type = list(object({
    name       = string
    public_key = string
    allowed_ips = list(string)
    comment    = optional(string)
  }))
  default = []
}

# -----------------------------------------------------------------------------
# Container Configuration
# -----------------------------------------------------------------------------

variable "adguard_password" {
  description = "AdGuard Home admin password (bcrypt hash)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "tailscale_authkey" {
  description = "Tailscale authentication key"
  type        = string
  sensitive   = true
  default     = ""
}