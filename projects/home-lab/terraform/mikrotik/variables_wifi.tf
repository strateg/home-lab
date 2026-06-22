# WiFi variables
# This file is manually maintained
# NOTE: WiFi resources are not supported by routeros provider - use RSC scripts

variable "wifi_vpn_germany_passphrase" {
  description = "WPA2 passphrase for VPN-Germany WiFi network"
  type        = string
  sensitive   = true
}
