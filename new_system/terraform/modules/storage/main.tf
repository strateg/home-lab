# Terraform Storage Module
# Proxmox Storage Pools Configuration
# Dell XPS L701X: SSD 180GB (production) + HDD 500GB (templates/backups)

# ============================================================
# SSD Storage - Production VMs and High-Performance Workloads
# ============================================================

# local-lvm - LVM-Thin storage on SSD
# Purpose: Production VMs, LXC containers with high I/O requirements
# Size: ~180 GB (after Proxmox installation)
resource "proxmox_virtual_environment_storage" "local_lvm" {
  count = var.enable_ssd_storage ? 1 : 0

  node_name    = var.node_name
  datastore_id = var.ssd_storage_id

  type = "lvmthin"

  # Content types allowed on this storage
  content_types = [
    "images",   # VM disk images
    "rootdir"   # LXC container root filesystems
  ]

  # Performance optimizations for SSD
  # These are typically set during Proxmox installation
  # but can be verified/updated here

  # Note: LVM-Thin pools are created during Proxmox installation
  # This resource primarily manages the content types and availability
}

# ============================================================
# HDD Storage - Templates, Backups, and Cold Storage
# ============================================================

# local-hdd - Directory storage on HDD
# Purpose: VM/LXC templates, backups, ISO images
# Size: ~500 GB
resource "proxmox_virtual_environment_storage" "local_hdd" {
  count = var.enable_hdd_storage ? 1 : 0

  node_name    = var.node_name
  datastore_id = var.hdd_storage_id

  type = "directory"

  # Mount point on Proxmox host
  path = var.hdd_mount_point

  # Content types for templates and backups
  content_types = [
    "backup",   # VM/LXC backups
    "iso",      # ISO images for VM installation
    "vztmpl",   # LXC container templates
    "snippets"  # Cloud-init snippets, scripts
  ]

  # Shared storage (if NFS/CIFS, set to true)
  shared = false

  # Preallocation mode for better performance
  # Options: "metadata" (default), "falloc", "full"
  preallocation = "metadata"

  # Enable content pruning (for backups)
  prune_backups = var.enable_backup_pruning ? {
    keep_last    = var.backup_keep_last
    keep_hourly  = var.backup_keep_hourly
    keep_daily   = var.backup_keep_daily
    keep_weekly  = var.backup_keep_weekly
    keep_monthly = var.backup_keep_monthly
    keep_yearly  = var.backup_keep_yearly
  } : null
}

# ============================================================
# Local Storage - Proxmox System
# ============================================================

# local - Default local storage (on SSD)
# Purpose: ISO images, snippets, Proxmox system files
# This is created by Proxmox installer, we just manage content types
resource "proxmox_virtual_environment_storage" "local" {
  count = var.manage_local_storage ? 1 : 0

  node_name    = var.node_name
  datastore_id = "local"

  type = "directory"

  path = "/var/lib/vz"

  # Content types for local storage
  content_types = [
    "iso",      # ISO images
    "vztmpl",   # LXC templates (if not using HDD)
    "snippets"  # Cloud-init snippets
  ]

  shared = false
}

# ============================================================
# Optional: NFS/CIFS Remote Storage
# ============================================================

# Example: NFS storage for shared templates/backups
# Uncomment and configure if you have NAS (e.g., TrueNAS)
#
# resource "proxmox_virtual_environment_storage" "nfs_shared" {
#   count = var.enable_nfs_storage ? 1 : 0
#
#   node_name    = var.node_name
#   datastore_id = var.nfs_storage_id
#
#   type = "nfs"
#
#   server       = var.nfs_server
#   export       = var.nfs_export
#   content_types = ["backup", "iso", "vztmpl"]
#
#   shared = true
# }

# ============================================================
# Storage Performance Monitoring
# ============================================================

# Note: Storage performance is monitored via Proxmox built-in tools
# For advanced monitoring, use Prometheus + Grafana (configured via Ansible)

# Check storage usage:
#   pvesm status
#   df -h /var/lib/vz
#   df -h /mnt/hdd

# Check LVM thin pool:
#   lvs -a
#   lvdisplay

# Monitor I/O:
#   iostat -x 1
#   iotop
