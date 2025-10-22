# Terraform Outputs
# Home Lab Infrastructure

# ============================================================
# Proxmox Node Info
# ============================================================

output "proxmox_node_name" {
  description = "Proxmox node name"
  value       = var.proxmox_node_name
}

output "proxmox_api_url" {
  description = "Proxmox API URL"
  value       = var.proxmox_api_url
}

# ============================================================
# Network Information
# ============================================================

output "network_summary" {
  description = "Network configuration summary"
  value = {
    isp_network          = var.isp_network
    opnsense_lan_network = var.opnsense_lan_network
    openwrt_lan_network  = var.openwrt_lan_network
    lxc_internal_network = var.lxc_internal_network
    mgmt_network         = var.mgmt_network
    vpn_wireguard        = var.vpn_wireguard_network
    vpn_amneziawg        = var.vpn_amneziawg_network
  }
}

output "management_ips" {
  description = "Management IPs for accessing services"
  value = {
    proxmox_web_ui = "https://${var.mgmt_proxmox_ip}:8006"
    opnsense_web_ui = "https://${var.mgmt_opnsense_ip}"
    openwrt_glinet_ui = "http://${var.openwrt_lan_gateway}"
    openwrt_luci = "http://${var.openwrt_lan_gateway}:81"
    adguard_home = "http://${var.openwrt_lan_gateway}:3000"
  }
}

# ============================================================
# Hardware Resources
# ============================================================

output "hardware_resources" {
  description = "Available hardware resources (Dell XPS L701X)"
  value = {
    cpu_cores  = var.hardware_cpu_cores
    ram_mb     = var.hardware_ram_mb
    ssd_size_gb = var.hardware_ssd_size_gb
    hdd_size_gb = var.hardware_hdd_size_gb
  }
}

# ============================================================
# Storage Configuration
# ============================================================

output "storage_pools" {
  description = "Configured storage pools"
  value = {
    ssd_production = var.storage_ssd_id
    hdd_templates_backups = var.storage_hdd_id
    local_iso = var.storage_local_id
  }
}

# ============================================================
# Environment Info
# ============================================================

output "environment" {
  description = "Current environment"
  value       = var.environment
}

output "default_tags" {
  description = "Default tags applied to resources"
  value       = var.default_tags
}

# ============================================================
# Feature Flags Status
# ============================================================

output "enabled_features" {
  description = "Enabled features"
  value = {
    monitoring   = var.enable_monitoring
    backups      = var.enable_backups
    vpn_servers  = var.enable_vpn_servers
  }
}

# ============================================================
# Next Steps
# ============================================================

output "next_steps" {
  description = "Next steps after Terraform apply"
  value = <<-EOT

    ✅ Terraform infrastructure provisioned successfully!

    Next steps:

    1. Apply Ansible configuration:
       cd ../ansible
       ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml

    2. Access Proxmox Web UI:
       https://${var.mgmt_proxmox_ip}:8006
       User: root

    3. Access OPNsense Firewall:
       https://${var.mgmt_opnsense_ip}
       User: root

    4. Access OpenWRT (GL.iNet UI):
       http://${var.openwrt_lan_gateway}

    5. Access AdGuard Home:
       http://${var.openwrt_lan_gateway}:3000

    6. Check infrastructure health:
       cd ../scripts
       ./health-check.sh

  EOT
}
