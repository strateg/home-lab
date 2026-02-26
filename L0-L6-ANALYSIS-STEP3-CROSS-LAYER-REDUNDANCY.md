# STEP 3: Cross-Layer Redundancy & Optimization Analysis

**Date:** 26 февраля 2026 г.

---

## Executive Summary

Current topology has **3 major redundancy categories** and **7 optimization opportunities** that block 10x growth:

1. **Service naming coupling** (L5 names tied to host-type)
2. **Alert→service binding loose** (L6 alert refs not validated)
3. **Port allocation untracked** (L5 service ports conflict risk)
4. **QoS rules at wrong layer** (L2 instead of L5)
5. **Storage chain not cached** (O(n²) resolution)
6. **Certificate refs scattered** (L5/L2/L6 each manage separately)
7. **Resource profile duplication** (L4 inline + reference collision)

---

## Redundancy Matrix: Data Duplication & Loose Coupling

### R1: Service Names Tied to Host-Type (L5)

**Current state:**
```yaml
# L5-application/services/orangepi5.yaml
services:
  - id: svc-orangepi5-nextcloud
    name: Nextcloud on Orange Pi 5
    host_ref: orangepi5  # Hardcoded in name!
```

**Problem:**
- If Nextcloud migrates to Proxmox (host change), service_id changes
- L6 alerts reference `svc-orangepi5-nextcloud` → break on migration
- L7 runbooks hardcode service names → stale after host reassignment

**Impact at 10x:**
- 200 services × migration probability = 50+ renaming cascades
- Runbook/alert maintenance nightmare

**Solution:**
```yaml
# L5-application/services/core-services.yaml
services:
  - id: svc-nextcloud
    name: Nextcloud
    deployment:
      host_ref: orangepi5  # Separate from ID
      resource_profile_ref: profile-medium
```

**Benefit:** Service ID immutable; host_ref changes don't cascade

**Effort:** Medium (rename all 30 services, update L6/L7 refs)

---

### R2: Alert↔Service Binding Unvalidated (L5↔L6)

**Current state:**
```yaml
# L6-observability/alerts.yaml
alerts:
  - id: alert-nextcloud-down
    service_ref: svc-orangepi5-nextcloud  # Manual string ref
    condition: healthcheck.status == down
```

**Problem:**
- No validator checks if `service_ref` exists in L5
- Alert orphaned if service deleted (no cleanup)
- L6 doesn't know which alerts apply to which services (no index)
- At 10x: 30 services × 30 alerts = 900 refs with no bidirectional mapping

**Solution:**
```yaml
# L6-observability/planning/_service-alert-bindings.yaml
service_alert_bindings:
  svc-nextcloud:
    alert_template_ids:
      - alert-tpl-availability      # Instantiated → alert-nextcloud-availability
      - alert-tpl-disk-full         # Instantiated → alert-nextcloud-disk-full
  svc-postgres:
    alert_template_ids:
      - alert-tpl-availability
      - alert-tpl-connection-pool-high
```

Validator check: all referenced alerts exist in L6/alerts/

**Benefit:** Bidirectional mapping; audit trail for coverage

**Effort:** Low (add index file + validator check)

---

### R3: Port Allocation Untracked (L5)

**Current state:**
```yaml
# L5-application/services/lxc.yaml
services:
  - id: svc-postgres
    ports:
      - port: 5432
        protocol: tcp
  - id: svc-redis
    ports:
      - port: 6379
        protocol: tcp
```

**Problem:**
- No central port registry → collision risk (if two services claim port 8080)
- No reserved port ranges (ephemeral 49152–65535 not protected)
- L2 firewall rules hardcode ports (duplicates L5 port refs)
- At 10x: 200 services with 2–5 ports each = 1000 ports, high collision risk

**Solution:**
```yaml
# L5-application/planning/port-registry.yaml
port_allocation_policy:
  reserved_ranges:
    system: [1, 1023]        # OS reserved (protected by validator)
    well_known: [1024, 49151] # Assign here deliberately
    ephemeral: [49152, 65535] # Auto-allocated by OS

service_port_allocations:
  svc-nextcloud:
    http: 80    # Documented; checked against registry
    https: 443
  svc-postgres:
    primary: 5432
    replica: 5433
```

Validator check: no port collisions, all ports within policy ranges

**Benefit:** Single port registry; collision detection; scaling prep

**Effort:** Medium (audit 30 services, build registry, enhance validator)

---

### R4: QoS Rules Scattered (L2 vs L5)

**Current state:**
```yaml
# L2-network/qos/default.yaml
qos_rules:
  - id: qos-nextcloud-limit
    network_ref: net-internal
    bandwidth_limit: 100Mbps
    # But which service? L5 doesn't know about this!

# L5-application/services/orangepi5.yaml
services:
  - id: svc-nextcloud
    # No reference to L2 QoS rules!
```

**Problem:**
- QoS policy (L2) separated from service (L5) → hard to manage together
- Operator doesn't know which service has which QoS
- Renaming service doesn't auto-update QoS refs
- L6 dashboards can't correlate service performance with QoS policy

**Solution:**
```yaml
# L5-application/services/core-services.yaml
services:
  - id: svc-nextcloud
    traffic_policy:
      qos_profile_ref: qos-nextcloud-web  # New: L5 owns QoS config

# L5-application/planning/qos-profiles.yaml
qos_profiles:
  qos-nextcloud-web:
    bandwidth_limit: 100Mbps
    priority: medium
    burst_allow: yes
```

Validator: all qos_profile_refs exist; no dangling QoS in L2

**Benefit:** QoS policy co-located with service; L6 can correlate

**Effort:** Medium (move QoS ownership from L2 to L5, update validators)

---

### R5: Storage Chain Resolution O(n²) (L3)

**Current state:**
```yaml
# Validator iterates:
# partition → media_attachment → media → volume_group → logical_volume → filesystem → mount_point → storage_endpoint → data_asset
# For each partition: N media_attachments lookups
# For each volume_group: N partition lookups
# Result: O(n²) in 500 partitions = 250,000 operations
```

**Problem:**
- Validator slow on 10x topology (500 partitions, 300 LVs)
- Generator has to re-resolve chains every run (no caching)
- Data asset resolution cascades through 7 layers

**Solution:**
```yaml
# L3-data/planning/storage-chain-cache.yaml
storage_chain_cache:  # Pre-computed during validation
  partition-root-pve:
    vg_ref: vg-system
    lv_refs: [lv-root, lv-var]
    mount_points: [/]
    endpoints: [se-ssd-1]
    data_assets: [da-postgres-data]
```

Validator: cache built once, reused by generator + docs

**Benefit:** 10x speedup in resolution; enables 10x growth

**Effort:** Medium (add caching layer + invalidation strategy)

---

### R6: Certificate Refs Scattered (L5/L2/L6)

**Current state:**
```yaml
# L5-application/certificates/certs.yaml
certificates:
  - id: cert-nextcloud
    domain: nextcloud.home.lab
    san: [www.nextcloud.home.lab]

# L5-application/services/orangepi5.yaml
services:
  - id: svc-nextcloud
    certificate_ref: cert-nextcloud  # Manual ref

# L2-network/firewall/policies/_index.yaml
firewall_policies:
  - id: policy-https-ingress
    certificate_ref: cert-nextcloud  # Duplicate ref!

# L6-observability/alerts.yaml
alerts:
  - id: alert-cert-expiring
    certificate_ref: cert-nextcloud  # Another ref
```

**Problem:**
- Certificate refs scattered → hard to audit
- No bidirectional mapping (which services use cert-nextcloud?)
- Certificate renewal workflow unclear (which refs to update?)
- At 10x: 100 certificates × 3 layers = 300 refs, hard to track

**Solution:**
```yaml
# L5-application/planning/certificate-registry.yaml
certificate_registry:
  cert-nextcloud:
    domain: nextcloud.home.lab
    san: [www.nextcloud.home.lab]
    used_by:
      - type: service
        ref: svc-nextcloud
      - type: firewall_policy
        ref: policy-https-ingress
      - type: alert
        ref: alert-cert-expiring
```

Validator: all cert refs point to registry; unused certs detected

**Benefit:** Single certificate source; audit trail; renewal workflow

**Effort:** Low-Medium (build registry, centralize cert refs)

---

### R7: Resource Profile Duplication (L4)

**Current state:**
```yaml
# L4-platform/resource-profiles/default.yaml
resource_profiles:
  - id: profile-medium
    cpu: 4
    memory: 8Gi

# L4-platform/workloads/lxc/postgres.yaml
lxc:
  - id: lxc-postgres
    resource_profile_ref: profile-medium  # Should use ref, but some inline:
    cpu: 4  # DUPLICATE!
    memory: 8Gi
```

**Problem:**
- Some workloads reference profile, others inline → inconsistency
- Profile changes don't cascade (workload still has inline values)
- Validator can't enforce profile-only model
- At 10x: 200 workloads with mixed profile/inline = chaos

**Solution:**
```yaml
# Validator rule: profile_ref is REQUIRED, inline cpu/memory forbidden
# L4-platform/workloads/lxc/postgres.yaml
lxc:
  - id: lxc-postgres
    resource_profile_ref: profile-medium  # ONLY this; no inline cpu/memory

# If override needed: extend profile, don't duplicate
resource_profile_overrides:
  - profile_ref: profile-medium
    workload_ref: lxc-postgres
    cpu_override: 8  # Only specific overrides
```

Validator: enforce profile-only; detect duplication

**Benefit:** Single source of truth; profile changes cascade

**Effort:** Medium (refactor 50+ workloads, enforce in validator)

---

## Consolidation Strategy: Data-Driven Approach

**Unification principle:** Define service once in L5, auto-derive:
- L6 alerts (from service type + thresholds)
- L6 dashboards (from service type + metrics)
- L2 QoS (from service tier)
- L7 runbooks (from service SLO)

**Example:**
```yaml
# L5-application/services/core-services.yaml
services:
  - id: svc-nextcloud
    type: web-app  # Service type drives everything below
    service_tier: critical  # Tier → SLO, alerts, dashboards
    resource_profile_ref: profile-web-medium
    traffic_policy:
      qos_profile_ref: qos-web-services  # Auto-selected by tier
    dependencies:
      - svc-postgres  # Auto-generate dependency alerts

# Validator auto-generates:
# - L6 alerts: alert-svc-nextcloud-* (from service type)
# - L6 dashboards: dash-svc-nextcloud (from type)
# - L6 SLO: slo-svc-nextcloud (from tier: critical → 99.99%)
# - L7 runbooks: rb-svc-nextcloud-* (from dependencies)
```

**Benefit:** Single definition point; cascading consistency; 10x scaling possible

---

## Summary: Optimization Roadmap

| Priority | Redundancy | Fix | Effort | Benefit |
|----------|------------|-----|--------|---------|
| 1 | Service naming coupling | Decouple ID from host-type | Medium | Enables host migration |
| 2 | Alert binding loose | Add service-alert index + validator | Low | Coverage audit |
| 3 | Port conflicts untracked | Build port registry + validator | Medium | Collision detection |
| 4 | QoS at wrong layer | Move QoS from L2 to L5 | Medium | Service-aware QoS |
| 5 | Storage chain O(n²) | Add caching layer | Medium | 10x speedup |
| 6 | Certificate refs scattered | Centralize in registry | Low-Med | Renewal workflow clarity |
| 7 | Resource duplication | Enforce profile-only model | Medium | Profile consistency |

**Total effort:** ~2–3 weeks (done incrementally)

**10x growth enablement:** Fixes 1, 5, 7 critical; others high-value

---

**Next:** Proceed to STEP 4 (L7 Operations Integration Mapping)
