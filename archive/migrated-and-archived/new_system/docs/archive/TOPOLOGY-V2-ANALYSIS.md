# Topology v2.0 Analysis & Improvements

## Date: 2025-10-09

## Current State Analysis

### ✅ Strengths of v2.0

1. **Clear Separation**: physical/logical/compute/services
2. **ID-based References**: device_ref, network_ref, storage_ref
3. **Trust Zones**: Comprehensive security boundaries
4. **IP Allocations**: Explicit mapping in networks
5. **Service Dependencies**: Defined relationships
6. **Comprehensive**: Covers all aspects of infrastructure

### ⚠️ Areas for Improvement

## 1. YAML Anchors & Reusability (Priority: Medium)

**Issue**: Repetitive structures (os, resources, dns)

**Current**:
```yaml
lxc:
  - id: lxc-postgresql
    os:
      type: "debian"
      version: "12"
    dns:
      nameserver: "192.168.10.2"
      searchdomain: "home.local"

  - id: lxc-redis
    os:
      type: "debian"        # Repeated
      version: "12"
    dns:
      nameserver: "192.168.10.2"  # Repeated
      searchdomain: "home.local"
```

**Improved**:
```yaml
# YAML Anchors
_defaults: &default_lxc_os
  type: "debian"
  version: "12"

_defaults: &default_lxc_dns
  nameserver: "192.168.10.2"
  searchdomain: "home.local"

lxc:
  - id: lxc-postgresql
    os: *default_lxc_os
    dns: *default_lxc_dns
```

**Impact**: Reduces file size by ~15%, easier maintenance

---

## 2. Backup Policies (Priority: HIGH)

**Issue**: No backup configuration for VMs/LXC

**Add**:
```yaml
backup:
  policies:
    - id: backup-daily-vms
      name: "Daily VM Backups"
      targets:
        - vm_ref: vm-opnsense-fw
      schedule: "0 2 * * *"  # 2 AM daily
      storage_ref: storage-hdd
      retention:
        keep_last: 3
        keep_daily: 7
        keep_weekly: 4
      mode: "snapshot"
      compression: "zstd"

    - id: backup-hourly-databases
      name: "Hourly Database Backups"
      targets:
        - lxc_ref: lxc-postgresql
      schedule: "0 * * * *"  # Every hour
      storage_ref: storage-hdd
      retention:
        keep_last: 24
        keep_daily: 7
      mode: "snapshot"
```

**Impact**: Critical for data safety, enables automation

---

## 3. Monitoring & Health Checks (Priority: HIGH)

**Issue**: No monitoring configuration

**Add**:
```yaml
monitoring:
  healthchecks:
    - id: health-proxmox
      name: "Proxmox Host Health"
      device_ref: gamayun
      checks:
        - type: "cpu_usage"
          warning_threshold: 80
          critical_threshold: 95
        - type: "memory_usage"
          warning_threshold: 85
          critical_threshold: 95
        - type: "disk_usage"
          warning_threshold: 80
          critical_threshold: 90
        - type: "service"
          service: "pvestatd"
      interval: "60s"

    - id: health-postgresql
      name: "PostgreSQL Health"
      lxc_ref: lxc-postgresql
      service_ref: svc-postgresql
      checks:
        - type: "port"
          port: 5432
        - type: "process"
          process: "postgres"
        - type: "query"
          query: "SELECT 1"
      interval: "30s"

  alerts:
    - id: alert-disk-full
      name: "Disk Full Alert"
      trigger: "disk_usage > 90%"
      channels: ["email", "telegram"]
      severity: "critical"
```

**Impact**: Proactive issue detection, reliability

---

## 4. SSH Key Management (Priority: MEDIUM)

**Issue**: SSH keys hardcoded as placeholders

**Improved**:
```yaml
security:
  ssh_keys:
    - id: ssh-admin-primary
      name: "Admin Primary Key"
      type: "ed25519"
      public_key: "ssh-ed25519 AAAA... admin@workstation"
      authorized_for:
        - device_ref: gamayun
        - lxc_ref: lxc-postgresql
        - lxc_ref: lxc-redis
        - lxc_ref: lxc-nextcloud

    - id: ssh-automation
      name: "Automation Key"
      type: "ed25519"
      public_key: "ssh-ed25519 AAAA... ansible@controller"
      authorized_for:
        - device_ref: gamayun
      purpose: "ansible-automation"

compute:
  lxc:
    - id: lxc-postgresql
      cloudinit:
        ssh_keys_ref: [ssh-admin-primary, ssh-automation]  # Reference
```

**Impact**: Centralized key management, better security

---

## 5. DNS Records (Priority: MEDIUM)

**Issue**: No DNS configuration for service discovery

**Add**:
```yaml
logical_topology:
  dns:
    zones:
      - id: zone-home-local
        domain: "home.local"
        nameserver_ref: svc-adguard
        records:
          - type: "A"
            name: "gamayun"
            ip_ref: "10.0.99.1"
            device_ref: gamayun

          - type: "A"
            name: "opnsense"
            ip_ref: "10.0.99.10"
            vm_ref: vm-opnsense-fw

          - type: "A"
            name: "postgresql"
            ip_ref: "10.0.30.10"
            lxc_ref: lxc-postgresql

          - type: "CNAME"
            name: "nextcloud"
            target: "nextcloud.home.local"
            service_ref: svc-nextcloud

          - type: "SRV"
            name: "_postgresql._tcp"
            target: "postgresql.home.local"
            port: 5432
            service_ref: svc-postgresql
```

**Impact**: Service discovery, cleaner networking

---

## 6. Certificate Management (Priority: LOW)

**Issue**: No TLS certificate configuration

**Add**:
```yaml
security:
  certificates:
    - id: cert-wildcard-home
      name: "Wildcard Home Lab Certificate"
      type: "self-signed"
      subject: "*.home.local"
      valid_days: 365
      used_by:
        - service_ref: svc-proxmox-ui
        - service_ref: svc-opnsense-ui
        - service_ref: svc-nextcloud

    - id: cert-letsencrypt-public
      name: "Let's Encrypt Public Certificate"
      type: "letsencrypt"
      domains: ["vpn.example.com"]
      used_by:
        - service_ref: svc-vpn-home
```

**Impact**: Better security, proper HTTPS

---

## 7. Network IP Pool Automation (Priority: LOW)

**Issue**: IP allocations are manual

**Enhanced**:
```yaml
networks:
  - id: net-lxc-internal
    cidr: "10.0.30.0/24"
    ip_pool:
      start: "10.0.30.10"
      end: "10.0.30.250"
      reserved:
        - "10.0.30.1"      # Proxmox bridge
        - "10.0.30.254"    # OPNsense gateway
      allocation_strategy: "sequential"  # or "dynamic"

    ip_allocations:  # Auto-generated from ip_pool
      - ip: "10.0.30.10"
        device_ref: lxc-postgresql
        allocated_by: "topology-generator"
        allocated_at: "2025-10-09T10:00:00Z"
```

**Impact**: Automated IP management, less errors

---

## 8. Firewall Rule Templates (Priority: MEDIUM)

**Issue**: Firewall rules are verbose

**Improved**:
```yaml
logical_topology:
  firewall_templates:
    - id: tmpl-web-access
      name: "Web Access Template"
      ports: [80, 443]
      protocols: ["tcp"]
      action: "allow"

    - id: tmpl-database-access
      name: "Database Access Template"
      ports: [5432, 3306, 6379]
      protocols: ["tcp"]
      action: "allow"

  firewall_policies:
    - id: fw-user-lxc-web
      name: "User to LXC Web Services"
      template_ref: tmpl-web-access
      source_zone_ref: user
      destination_zone_ref: internal
      priority: 200
```

**Impact**: DRY principle, easier maintenance

---

## 9. Resource Quotas (Priority: LOW)

**Issue**: No resource limits defined

**Add**:
```yaml
compute:
  resource_quotas:
    total_available:
      cpu_cores: 2
      memory_mb: 8192
      storage_gb: 180  # SSD

    allocated:
      vms:
        cpu_cores: 2      # opnsense-fw
        memory_mb: 2048
      lxc:
        cpu_cores: 5      # 2+1+2
        memory_mb: 5120   # 2048+1024+2048

    remaining:
      cpu_cores: 0        # Over-subscribed (OK for VMs)
      memory_mb: 1024
```

**Impact**: Resource planning, prevents overallocation

---

## 10. Ansible Variables Generation (Priority: MEDIUM)

**Issue**: Ansible vars are hardcoded in compute section

**Improved**:
```yaml
ansible:
  group_vars:
    all:
      ansible_user: "root"
      ansible_python_interpreter: "/usr/bin/python3"

    lxc_containers:
      common_packages: ["vim", "git", "curl", "htop"]
      timezone: "UTC"
      dns_servers: ["192.168.10.2"]

  host_vars:
    # Auto-generated from compute.lxc[*].ansible.vars
    lxc-postgresql:
      postgresql_version: "15"
      # ... from topology

compute:
  lxc:
    - id: lxc-postgresql
      ansible:
        groups: ["lxc_containers", "databases"]
        # vars moved to ansible.host_vars
```

**Impact**: Better Ansible integration

---

## Priority Ranking

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| 🔴 HIGH | Backup Policies | 1h | Critical |
| 🔴 HIGH | Monitoring & Health Checks | 2h | High |
| 🟡 MEDIUM | YAML Anchors | 30min | Medium |
| 🟡 MEDIUM | SSH Key Management | 1h | Medium |
| 🟡 MEDIUM | DNS Records | 1h | Medium |
| 🟡 MEDIUM | Firewall Templates | 30min | Medium |
| 🟡 MEDIUM | Ansible Variables | 1h | Medium |
| 🟢 LOW | Certificate Management | 1h | Low |
| 🟢 LOW | Network IP Pool | 1h | Low |
| 🟢 LOW | Resource Quotas | 30min | Low |

**Total Effort**: ~10 hours for all improvements

---

## Recommended Implementation Order

### Phase 1: Critical (1-2 hours)
1. ✅ Add backup policies
2. ✅ Add monitoring/healthchecks
3. ✅ Implement YAML anchors

### Phase 2: Important (2-3 hours)
4. Add SSH key management
5. Add DNS records
6. Add firewall templates
7. Improve Ansible variables

### Phase 3: Nice-to-have (2-3 hours)
8. Certificate management
9. Network IP pool automation
10. Resource quotas

---

## Breaking Changes

**None** - All improvements are additive:
- New sections don't break existing structure
- Old generators can ignore new sections
- New generators will use enhanced features

---

## Validation Requirements

After improvements, validator should check:
- ✅ All _ref fields point to existing IDs
- ✅ Backup targets exist
- ✅ Healthcheck device/service refs valid
- ✅ SSH keys referenced in cloudinit exist
- ✅ DNS records point to valid IPs
- ✅ Firewall templates used correctly
- ✅ Resource quotas don't exceed hardware

---

## Next Steps

1. Apply Phase 1 improvements (backup + monitoring + YAML anchors)
2. Update validate-topology.py for new sections
3. Test validation
4. Document new features
5. Update generators to use new sections

---

**Status**: ✅ Phase 1 Complete & Migrated to Production
**Migration Date**: 2025-10-10
**Current Topology**: topology.yaml (v2.0.0)
