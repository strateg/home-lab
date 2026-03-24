# Storage Module Variables
# Proxmox Storage Pools Configuration

# ============================================================
# Node Configuration
# ============================================================

variable "node_name" {
  description = "Proxmox node name"
  type        = string
}

# ============================================================
# SSD Storage Configuration
# ============================================================

variable "enable_ssd_storage" {
  description = "Enable SSD storage management"
  type        = bool
  default     = true
}

variable "ssd_storage_id" {
  description = "SSD storage datastore ID"
  type        = string
  default     = "local-lvm"
}

variable "ssd_size_gb" {
  description = "SSD total size in GB (for documentation)"
  type        = number
  default     = 180
  # Note: Actual size is set during Proxmox installation
}

# ============================================================
# HDD Storage Configuration
# ============================================================

variable "enable_hdd_storage" {
  description = "Enable HDD storage management"
  type        = bool
  default     = true
}

variable "hdd_storage_id" {
  description = "HDD storage datastore ID"
  type        = string
  default     = "local-hdd"
}

variable "hdd_mount_point" {
  description = "HDD mount point on Proxmox host"
  type        = string
  default     = "/mnt/hdd"
  # Must be created and mounted before Terraform apply
}

variable "hdd_size_gb" {
  description = "HDD total size in GB (for documentation)"
  type        = number
  default     = 500
}

# ============================================================
# Local Storage Configuration
# ============================================================

variable "manage_local_storage" {
  description = "Manage local storage (created by Proxmox installer)"
  type        = bool
  default     = false
  # Usually not needed, as Proxmox installer creates it
}

# ============================================================
# Backup Configuration
# ============================================================

variable "enable_backup_pruning" {
  description = "Enable automatic backup pruning"
  type        = bool
  default     = true
}

variable "backup_keep_last" {
  description = "Keep last N backups"
  type        = number
  default     = 3
}

variable "backup_keep_hourly" {
  description = "Keep hourly backups"
  type        = number
  default     = 0
  # 0 = disabled
}

variable "backup_keep_daily" {
  description = "Keep daily backups"
  type        = number
  default     = 7
  # Keep 1 week of daily backups
}

variable "backup_keep_weekly" {
  description = "Keep weekly backups"
  type        = number
  default     = 4
  # Keep 1 month of weekly backups
}

variable "backup_keep_monthly" {
  description = "Keep monthly backups"
  type        = number
  default     = 6
  # Keep 6 months of monthly backups
}

variable "backup_keep_yearly" {
  description = "Keep yearly backups"
  type        = number
  default     = 1
  # Keep 1 year backup
}

# ============================================================
# NFS/CIFS Remote Storage (Optional)
# ============================================================

variable "enable_nfs_storage" {
  description = "Enable NFS remote storage"
  type        = bool
  default     = false
}

variable "nfs_storage_id" {
  description = "NFS storage datastore ID"
  type        = string
  default     = "nfs-shared"
}

variable "nfs_server" {
  description = "NFS server IP or hostname"
  type        = string
  default     = ""
  # Example: "192.168.1.100"
}

variable "nfs_export" {
  description = "NFS export path"
  type        = string
  default     = ""
  # Example: "/mnt/pool/proxmox"
}

# ============================================================
# Storage Strategy
# ============================================================

variable "storage_strategy" {
  description = "Storage allocation strategy"
  type = object({
    ssd_for_production  = bool  # Use SSD for production VMs
    hdd_for_templates   = bool  # Use HDD for templates
    hdd_for_backups     = bool  # Use HDD for backups
    ssd_for_databases   = bool  # Use SSD for database LXC
  })
  default = {
    ssd_for_production = true
    hdd_for_templates  = true
    hdd_for_backups    = true
    ssd_for_databases  = true
  }
}
