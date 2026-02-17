# ============================================================
# LXC Containers Configuration
# Generated from topology.yaml v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with scripts/generate-terraform.py
# ============================================================

# ============================================================
# LXC: postgresql-db (database)
# Role: database-server
# Description: PostgreSQL Database Server
# ============================================================

resource "proxmox_virtual_environment_container" "lxc_postgresql" {
  node_name = var.proxmox_node
  vm_id     = 200

  description = "PostgreSQL Database Server"
  tags        = ["database", "production"]

  # Resources
  cpu {
    cores = 2
  }

  memory {
    dedicated = 1024
    swap      = 1024
  }

  # Boot configuration
  started = true

  # Operating System
  operating_system {
    template_file_id = "local:vztmpl/debian-12-standard_12.0-1_amd64.tar.zst"
    type             = "debian"
  }

  # Root filesystem
  disk {
    datastore_id = "local-lvm"
    size         = 8
  }

  # Network configuration
  network_interface {
    name   = "eth0"
    bridge = "vmbr2"
    firewall = false
  }

  # Cloud-init / Initialization
  initialization {
    user_account {
      keys = [
        "ssh-ed25519 AAAA...",
      ]
    }

    dns {
      servers = ["192.168.88.1"]
      domain  = "home.local"
    }

    ip_config {
      ipv4 {
        address = "10.0.30.10/24"
        gateway = "10.0.30.1"
      }
    }
  }

  # Features
  features {
    nesting = true
    fuse    = false
  }

  # Console configuration
  console {
    enabled = true
    tty_count = 2
    type = "shell"
  }

  # Startup order
  startup {
    order      = 10
    up_delay   = 30
    down_delay = 30
  }

  # Lifecycle
  lifecycle {
    ignore_changes = [
      network_interface,
      initialization,
    ]
  }
}

# ============================================================
# LXC: redis-cache (cache)
# Role: cache-server
# Description: Redis Cache Server
# ============================================================

resource "proxmox_virtual_environment_container" "lxc_redis" {
  node_name = var.proxmox_node
  vm_id     = 201

  description = "Redis Cache Server"
  tags        = ["cache", "production"]

  # Resources
  cpu {
    cores = 1
  }

  memory {
    dedicated = 512
    swap      = 256
  }

  # Boot configuration
  started = true

  # Operating System
  operating_system {
    template_file_id = "local:vztmpl/debian-12-standard_12.0-1_amd64.tar.zst"
    type             = "debian"
  }

  # Root filesystem
  disk {
    datastore_id = "local-lvm"
    size         = 4
  }

  # Network configuration
  network_interface {
    name   = "eth0"
    bridge = "vmbr2"
    firewall = false
  }

  # Cloud-init / Initialization
  initialization {
    user_account {
      keys = [
      ]
    }

    dns {
      servers = ["192.168.88.1"]
      domain  = "home.local"
    }

    ip_config {
      ipv4 {
        address = "10.0.30.20/24"
        gateway = "10.0.30.1"
      }
    }
  }

  # Features
  features {
    nesting = true
    fuse    = false
  }

  # Console configuration
  console {
    enabled = true
    tty_count = 2
    type = "shell"
  }

  # Startup order
  startup {
    order      = 11
    up_delay   = 30
    down_delay = 30
  }

  # Lifecycle
  lifecycle {
    ignore_changes = [
      network_interface,
      initialization,
    ]
  }
}


# ============================================================
# Outputs
# ============================================================

output "lxc_containers" {
  description = "LXC containers configuration"
  value = {
    lxc_postgresql = {
      id   = proxmox_virtual_environment_container.lxc_postgresql.vm_id
      name = "postgresql-db"
      ip   = "10.0.30.10/24"
    }
    lxc_redis = {
      id   = proxmox_virtual_environment_container.lxc_redis.vm_id
      name = "redis-cache"
      ip   = "10.0.30.20/24"
    }
  }
}