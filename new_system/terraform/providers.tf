# Terraform Providers Configuration
# Home Lab Infrastructure

terraform {
  required_version = ">= 1.5.0"

  # Remote backend configuration (optional, для production)
  # backend "local" {
  #   path = "terraform.tfstate"
  # }

  # Для production рекомендуется использовать remote backend:
  # backend "s3" {
  #   bucket = "home-lab-terraform-state"
  #   key    = "production/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# Proxmox Provider
# https://registry.terraform.io/providers/bpg/proxmox/latest/docs
provider "proxmox" {
  endpoint = var.proxmox_api_url
  api_token = var.proxmox_api_token_id

  # For token authentication (recommended)
  # api_token = "user@pam!token_id=token_secret"

  # For username/password authentication (not recommended)
  # username = var.proxmox_username
  # password = var.proxmox_password

  # Skip TLS verification if using self-signed certificate
  insecure = var.proxmox_tls_insecure

  # SSH connection for executing commands on Proxmox host
  ssh {
    agent    = true
    username = var.proxmox_ssh_user
    # private_key = file(var.proxmox_ssh_private_key_path)
  }

  # Timeout settings
  timeout = 600  # 10 minutes
}

# Random provider for generating random values
provider "random" {
  # Used for generating random passwords, IDs, etc.
}

# Local provider for local file operations
provider "local" {
  # Used for generating local files from templates
}
