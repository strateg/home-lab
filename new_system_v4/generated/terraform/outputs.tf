# ============================================================
# Terraform Outputs
# Generated from topology.yaml v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with scripts/generate-terraform.py
# ============================================================

# ============================================================
# Proxmox Node Information
# ============================================================

output "proxmox_node" {
  description = "Proxmox node name"
  value       = var.proxmox_node
}

output "proxmox_api_url" {
  description = "Proxmox API URL"
  value       = var.proxmox_api_url
}

# ============================================================
# NOTE: bridges and lxc_containers outputs are defined in their
# respective .tf files (bridges.tf and lxc.tf) to keep related
# resources and outputs together.
# ============================================================

# ============================================================
# Virtual Machines
# ============================================================


# ============================================================
# Management Access URLs
# ============================================================

output "management_urls" {
  description = "Management access URLs for services"
  value = {
    proxmox_web_ui = "https://:8006"
  }
}

# ============================================================
# Network Configuration Summary
# ============================================================

output "network_summary" {
  description = "Network configuration summary"
  value = {
    vmbr0 = {
      subnet  = "192.168.88.2/24"
      comment = "LAN trunk bridge to MikroTik (VLAN-aware)"
      ports   = ["if-eth-builtin"]
    }
  }
}

# ============================================================
# Storage Configuration
# ============================================================

output "storage_pools" {
  description = "Configured storage pools"
  value = {
    storage_local = {
      name = "local"
      type = "dir"
      path = "/var/lib/vz"
    }
    storage_lvm = {
      name = "local-lvm"
      type = "lvmthin"
    }
    storage_hdd = {
      name = "local-hdd"
      type = "dir"
      path = "/mnt/hdd"
    }
  }
}

# ============================================================
# Trust Zones
# ============================================================

output "trust_zones" {
  description = "Infrastructure trust zones"
  value = {
    servers = ["postgresql-db", "redis-cache"]
  }
}

# ============================================================
# Infrastructure Statistics
# ============================================================

output "infrastructure_stats" {
  description = "Infrastructure statistics"
  value = {
    total_bridges       = 1
    total_lxc          = 2
    total_storage_pools = 3
    topology_version   = "4.0.0"
  }
}

# ============================================================
# Next Steps
# ============================================================

output "next_steps" {
  description = "Next steps after Terraform apply"
  value = <<-EOT

    ✅ Terraform infrastructure provisioned successfully!

    📊 Infrastructure Summary:
       - LXC Containers: 2
       - Network Bridges: 1

    🔧 Next steps:

    1. Apply Ansible configuration:
       cd ../ansible
       ansible-playbook -i inventory/production/hosts.yml playbooks/site.yml

    2. Access Proxmox Web UI:
       https://:8006
       User: root

    3. Verify infrastructure:
       terraform output
       cd ../scripts
       ./test-regeneration.sh

    4. Check connectivity:
       ansible all -i ../ansible/inventory/production/hosts.yml -m ping

  EOT
}