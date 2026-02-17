# ============================================================
# Terraform Provider Configuration
# Generated from topology.yaml v2.0.0
# DO NOT EDIT MANUALLY - Regenerate with scripts/generate-terraform.py
# ============================================================

terraform {
  required_version = ">= 1.5.0"

  # Backend configuration (local by default)
  # Uncomment for production remote backend:
  # backend "s3" {
  #   bucket = "home-lab-terraform-state"
  #   key    = "production/terraform.tfstate"
  #   region = "us-east-1"
  # }

  required_providers {
    # Proxmox Provider
    # https://registry.terraform.io/providers/bpg/proxmox/latest/docs
    # Updated to v0.85+ for network bridge support
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.85.0"
    }

    # Random Provider (for generating passwords, IDs, etc.)
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"
    }

    # Local Provider (for local file operations)
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5.0"
    }

    # TLS Provider (for generating SSH keys)
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0.0"
    }
  }
}

# ============================================================
# Proxmox Provider
# ============================================================

provider "proxmox" {
  endpoint = var.proxmox_api_url
  api_token = var.proxmox_api_token
  insecure = var.proxmox_insecure

  # SSH connection for executing commands on Proxmox host
  ssh {
    agent    = true
    username = var.proxmox_ssh_user
  }
}

# ============================================================
# Additional Providers
# ============================================================

# Random provider for generating random values
provider "random" {}

# Local provider for local file operations
provider "local" {}

# TLS provider for SSH key generation
provider "tls" {}

# ============================================================
# Data Sources
# ============================================================

# Proxmox node: Gamayun
# Model: Dell XPS L701X
# CPU: 2 cores
# RAM: 8 GB

data "proxmox_virtual_environment_nodes" "available_nodes" {}