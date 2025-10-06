# Terraform Required Providers
# Home Lab Infrastructure

terraform {
  required_providers {
    # Proxmox Provider
    # https://registry.terraform.io/providers/bpg/proxmox/latest
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.50.0"
    }

    # Random Provider
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"
    }

    # Local Provider
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5.0"
    }

    # TLS Provider (для генерации SSH ключей)
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0.0"
    }
  }
}
