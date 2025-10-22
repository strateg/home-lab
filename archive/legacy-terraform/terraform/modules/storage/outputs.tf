# Storage Module Outputs
# Information about configured storage pools

# ============================================================
# Storage Pool IDs
# ============================================================

output "ssd_storage_id" {
  description = "SSD storage datastore ID (for production VMs)"
  value       = var.ssd_storage_id
}

output "hdd_storage_id" {
  description = "HDD storage datastore ID (for templates/backups)"
  value       = var.hdd_storage_id
}

output "local_storage_id" {
  description = "Local storage datastore ID (for ISOs/snippets)"
  value       = "local"
}

# ============================================================
# Storage Configuration Summary
# ============================================================

output "storage_summary" {
  description = "Storage pools configuration summary"
  value = {
    ssd = {
      id           = var.ssd_storage_id
      type         = "lvmthin"
      size_gb      = var.ssd_size_gb
      content      = ["images", "rootdir"]
      purpose      = "Production VMs and high-performance workloads"
      enabled      = var.enable_ssd_storage
    }
    hdd = {
      id           = var.hdd_storage_id
      type         = "directory"
      size_gb      = var.hdd_size_gb
      mount_point  = var.hdd_mount_point
      content      = ["backup", "iso", "vztmpl", "snippets"]
      purpose      = "Templates, backups, and cold storage"
      enabled      = var.enable_hdd_storage
    }
    local = {
      id           = "local"
      type         = "directory"
      path         = "/var/lib/vz"
      content      = ["iso", "vztmpl", "snippets"]
      purpose      = "Proxmox system files"
      enabled      = var.manage_local_storage
    }
  }
}

# ============================================================
# Storage Strategy
# ============================================================

output "storage_strategy" {
  description = "Storage allocation strategy"
  value       = var.storage_strategy
}

# ============================================================
# Backup Configuration
# ============================================================

output "backup_retention" {
  description = "Backup retention policy"
  value = var.enable_backup_pruning ? {
    enabled      = true
    keep_last    = var.backup_keep_last
    keep_daily   = var.backup_keep_daily
    keep_weekly  = var.backup_keep_weekly
    keep_monthly = var.backup_keep_monthly
    keep_yearly  = var.backup_keep_yearly
  } : {
    enabled = false
  }
}

# ============================================================
# Storage Capacity Planning
# ============================================================

output "capacity_planning" {
  description = "Storage capacity planning information"
  value = {
    total_capacity_gb = var.ssd_size_gb + var.hdd_size_gb
    ssd_capacity_gb   = var.ssd_size_gb
    hdd_capacity_gb   = var.hdd_size_gb

    recommended_allocation = {
      ssd = {
        opnsense_vm        = "32 GB"
        lxc_postgresql     = "8 GB"
        lxc_redis          = "4 GB"
        lxc_nextcloud      = "20 GB"
        lxc_others         = "8 GB each"
        reserved_free      = "20-30 GB"
      }
      hdd = {
        vm_templates       = "50 GB"
        lxc_templates      = "20 GB"
        backups            = "200 GB"
        iso_images         = "30 GB"
        reserved_free      = "100 GB"
      }
    }
  }
}

# ============================================================
# Usage Examples
# ============================================================

output "usage_examples" {
  description = "Examples of how to use storage in VM/LXC configs"
  value = <<-EOT

    # Use SSD storage for production VM:
    resource "proxmox_virtual_environment_vm" "opnsense" {
      disk {
        datastore_id = module.storage.ssd_storage_id  # "${var.ssd_storage_id}"
        size         = 32
      }
    }

    # Use SSD storage for database LXC:
    resource "proxmox_virtual_environment_container" "postgresql" {
      disk {
        datastore_id = module.storage.ssd_storage_id  # "${var.ssd_storage_id}"
        size         = 8
      }
    }

    # Use HDD storage for backups:
    vzdump <vmid> --storage ${var.hdd_storage_id}

    # Download ISO to HDD:
    cd /mnt/hdd/template/iso
    wget https://example.com/os.iso

    # Create LXC template on HDD:
    pveam update
    pveam download ${var.hdd_storage_id} debian-12-standard_12.7-1_amd64.tar.zst

  EOT
}

# ============================================================
# NFS Storage (if enabled)
# ============================================================

output "nfs_storage_config" {
  description = "NFS storage configuration (if enabled)"
  value = var.enable_nfs_storage ? {
    enabled     = true
    id          = var.nfs_storage_id
    server      = var.nfs_server
    export      = var.nfs_export
    shared      = true
    content     = ["backup", "iso", "vztmpl"]
  } : {
    enabled = false
  }
}
