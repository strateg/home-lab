# =============================================================================
# MikroTik DNS Configuration
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

# -----------------------------------------------------------------------------
# DNS Settings
# -----------------------------------------------------------------------------
# Note: Primary DNS is handled by AdGuard Home container
# MikroTik forwards to AdGuard container on localhost

resource "routeros_ip_dns" "dns" {
  servers               = ["127.0.0.1"]  # AdGuard container
  allow_remote_requests = true
  cache_size            = 100
  cache_max_ttl         = "1w"
}

# -----------------------------------------------------------------------------
# Static DNS Records
# -----------------------------------------------------------------------------

resource "routeros_ip_dns_record" "router" {
  name    = "router.home.local"
  address = "192.168.88.1"
  type    = "A"
  ttl     = "3600"
  comment = "MikroTik router"
}

resource "routeros_ip_dns_record" "mikrotik" {
  name    = "mikrotik.home.local"
  address = "192.168.88.1"
  type    = "A"
  ttl     = "3600"
  comment = "MikroTik router alias"
}

resource "routeros_ip_dns_record" "gamayun" {
  name    = "gamayun.home.local"
  address = "192.168.88.2"
  type    = "A"
  ttl     = "3600"
  comment = "Proxmox host"
}

resource "routeros_ip_dns_record" "proxmox" {
  name    = "proxmox.home.local"
  address = "10.0.99.2"
  type    = "A"
  ttl     = "3600"
  comment = "Proxmox Web UI (management)"
}

resource "routeros_ip_dns_record" "orangepi" {
  name    = "orangepi.home.local"
  address = "192.168.88.3"
  type    = "A"
  ttl     = "3600"
  comment = "Orange Pi 5 application server"
}

resource "routeros_ip_dns_record" "opi5" {
  name    = "opi5.home.local"
  address = "10.0.30.50"
  type    = "A"
  ttl     = "3600"
  comment = "Orange Pi 5 server interface"
}

resource "routeros_ip_dns_record" "postgresql" {
  name    = "postgresql.home.local"
  address = "10.0.30.10"
  type    = "A"
  ttl     = "3600"
  comment = "PostgreSQL database server"
}

resource "routeros_ip_dns_record" "redis" {
  name    = "redis.home.local"
  address = "10.0.30.20"
  type    = "A"
  ttl     = "3600"
  comment = "Redis cache server"
}

resource "routeros_ip_dns_record" "nextcloud" {
  name    = "nextcloud.home.local"
  address = "10.0.30.50"
  type    = "A"
  ttl     = "3600"
  comment = "Nextcloud on Orange Pi 5"
}

resource "routeros_ip_dns_record" "jellyfin" {
  name    = "jellyfin.home.local"
  address = "10.0.30.50"
  type    = "A"
  ttl     = "3600"
  comment = "Jellyfin media server on Orange Pi 5"
}

resource "routeros_ip_dns_record" "grafana" {
  name    = "grafana.home.local"
  address = "10.0.30.50"
  type    = "A"
  ttl     = "3600"
  comment = "Grafana on Orange Pi 5"
}

resource "routeros_ip_dns_record" "prometheus" {
  name    = "prometheus.home.local"
  address = "10.0.30.50"
  type    = "A"
  ttl     = "3600"
  comment = "Prometheus on Orange Pi 5"
}

resource "routeros_ip_dns_record" "db_cname" {
  name    = "db.home.local"
  cname   = "postgresql.home.local"
  type    = "CNAME"
  ttl     = "3600"
  comment = "Database alias"
}

resource "routeros_ip_dns_record" "cache_cname" {
  name    = "cache.home.local"
  cname   = "redis.home.local"
  type    = "CNAME"
  ttl     = "3600"
  comment = "Cache alias"
}

resource "routeros_ip_dns_record" "cloud_cname" {
  name    = "cloud.home.local"
  cname   = "nextcloud.home.local"
  type    = "CNAME"
  ttl     = "3600"
  comment = "Cloud storage alias"
}

resource "routeros_ip_dns_record" "media_cname" {
  name    = "media.home.local"
  cname   = "jellyfin.home.local"
  type    = "CNAME"
  ttl     = "3600"
  comment = "Media server alias"
}

resource "routeros_ip_dns_record" "monitor_cname" {
  name    = "monitor.home.local"
  cname   = "grafana.home.local"
  type    = "CNAME"
  ttl     = "3600"
  comment = "Monitoring alias"
}

