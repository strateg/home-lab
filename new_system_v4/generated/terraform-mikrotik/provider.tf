# =============================================================================
# MikroTik RouterOS Provider Configuration
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    routeros = {
      source  = "terraform-routeros/routeros"
      version = "~> 1.40"
    }
  }
}

# -----------------------------------------------------------------------------
# RouterOS Provider
# -----------------------------------------------------------------------------
# Authentication via REST API (RouterOS 7.x required)
# Ensure www-ssl service is enabled on the router

provider "routeros" {
  hosturl  = var.mikrotik_host
  username = var.mikrotik_username
  password = var.mikrotik_password
  insecure = var.mikrotik_insecure  # Set to false in production with valid cert
}

# -----------------------------------------------------------------------------
# System Identity
# -----------------------------------------------------------------------------

resource "routeros_system_identity" "router" {
  name = "MikroTik Chateau LTE7 ax"
}