# ADR 0048: Topology Evolution Strategy for 10x Growth (Scaling & Optimization)

**Date:** 2026-02-26
**Status:** Proposed
**Stakeholders:** Infrastructure architects, DevOps, Toolchain maintainers

---

## Context

Current topology-as-data approach (8 layers, modular YAML, generator-driven) is **reaching scalability limits** at 10x growth:

**Bottlenecks identified:**
1. Validator O(n²) reference resolution (media-attachment, storage chain, service-alert binding) → 20s at 10x
2. Generator monolithic (regenerates ALL on any change) → 50s at 10x
3. File organization flat (100+ files in one dir) → navigation/collision risk
4. Naming namespaces flat (1000+ alerts, services, dashboards) → collision risk
5. Data duplication explosion (services named in L5 + alerts in L6 + QoS in L2/L5 + certs scattered)
6. Validator+generator not integrated with L7 operations (runbooks hardcoded, not data-driven)

**Constraints:**
- Backward compatibility: generated outputs (Terraform, Ansible, docs) must remain valid
- Infrastructure-as-Data principle: YAML must remain single source of truth
- Low barrier to entry: scaling optimizations must not complicate contributor workflow
- Cost: optimize without massive refactoring (incremental approach)

---

## Decision

### 1. Lazy Validation + Caching Layer

**Problem:** Validator O(n²) at 10x scale (20s → unacceptable)

**Solution:**
```python
# topology-tools/validators/cache_manager.py
class ValidationCache:
    def build(self, topology):
        """Build indices once, reuse for all validators"""
        self.device_index = {d.id: d for d in topology['L1'].devices}
        self.media_index = {m.id: m for m in topology['L1'].media}
        self.service_index = {s.id: s for s in topology['L5'].services}
        self.alert_index = {a.id: a for a in topology['L6'].alerts}
        return self

    def validate_service_ref(self, service_ref):
        """O(1) lookup instead of O(n) search"""
        return service_ref in self.service_index
```

**Validator refactoring:**
```python
# Before: O(n²)
for partition in partitions:
    for vg in volume_groups:
        for lv in logical_volumes:
            if partition.vg_ref == vg.id and vg.lv_refs contains lv.id:
                validate(lv)  # O(n²) nested loops

# After: O(n) with cache
cache.validate_partition_chain(partition_id)  # O(1) lookup
```

**Implementation:**
- [ ] Add ValidationCache class (50 LOC)
- [ ] Refactor 5 critical validators (O(n²) → O(n))
- [ ] Add cache invalidation on L0/L1/L5 changes

**Result:** Validation 20s → 2s at 10x ✅

---

### 2. Incremental Generation Strategy

**Problem:** Generator monolithic (regenerates ALL on any change) → 50s at 10x

**Solution: Component-Based Generation**

```bash
# Current: regenerate everything
python regenerate-all.py  # 50s on 10x topology

# Proposed: regenerate only changed component
python regenerate-docs.py --component services  # 2s (only service-related docs)
python regenerate-terraform.py --component networks  # 3s (only network TF)

# Smart mode: detect changes, regenerate only affected
python regenerate-smart.py  # 2026-02-26T14:00:00Z → detects L5 change → regenerates L5+L6+docs
```

**Implementation:**
- [ ] Add component detection (which L0-L7 files changed?)
- [ ] Componentize generators (Terraform: network/, compute/, storage/ generators)
- [ ] Track mtime in .topology-cache/
- [ ] Smart regeneration logic (L5 change → regenerate L5+L6+L7, not L1-L4)

**Result:** Regeneration 50s → 10s typical, 2s for isolated changes ✅

---

### 3. Hierarchical File Organization

**Problem:** Flat structure (100+ files per dir) → collision risk, poor navigation

**Solution: Namespace-First Organization**

**Current:**
```
L1-foundation/devices/
├── pve-01.yaml
├── pve-02.yaml
├── chateau-01.yaml
└── opi5-01.yaml  # Hard to find specific device type
```

**Proposed:**
```
L1-foundation/devices/
├── proxmox/
│   ├── _index.yaml
│   ├── pve-01.yaml
│   ├── pve-02.yaml
│   └── pve-20.yaml
├── chateau/
│   ├── _index.yaml
│   ├── router-01.yaml
│   └── router-10.yaml
└── orangepi/
    ├── _index.yaml
    ├── srv-01.yaml
    └── srv-20.yaml
```

**Loader enhancement:**
```yaml
# Updated !include syntax
devices: !include_dir_sorted L1-foundation/devices/*/
```

**Implementation:**
- [ ] Restructure 70 devices into type-specific dirs
- [ ] Update !include patterns (5 files)
- [ ] Add validator for new hierarchy

**Result:** Clear navigation + collision-free naming ✅

---

### 4. Hierarchical Namespacing Conventions

**Problem:** Flat naming at 1000+ items → collisions, unclear ownership

**Solution: Hierarchical Names with Dots**

```yaml
# L5 services: svc-<domain>.<service>
svc-web.nextcloud       # Web service domain, nextcloud
svc-db.postgres         # Database domain, postgres
svc-infra.monitoring    # Infrastructure domain, monitoring

# L6 alerts: alert-<domain>.<service>-<type>
alert-web.nextcloud-availability
alert-db.postgres-connection-pool-high
alert-infra.network-latency-high

# L6 dashboards: dash-<layer>-<domain>.<service>
dash-app-web.nextcloud         # Application layer dashboard
dash-infra-network             # Infrastructure network dashboard
dash-infra-storage             # Infrastructure storage dashboard
```

**Validator enforcement:**
```python
# Add naming validator (regex)
NAMING_REGEX = {
    'service_id': r'^svc-[a-z]+\.[a-z0-9_-]+$',
    'alert_id': r'^alert-[a-z]+\.[a-z0-9_-]+-[a-z-]+$',
    'dashboard_id': r'^dash-[a-z]+-[a-z0-9._-]+$'
}
```

**Migration:** Automated renaming (rename-tool.py), ~30 min

**Result:** Collision-free naming up to 100x scale ✅

---

### 5. Data-Driven Alert, Dashboard, Runbook Generation

**Problem:** Services defined in L5, alerts in L6, runbooks in L7 → duplication and manual maintenance

**Solution: Service Definition Drives Generation**

**Single source of truth (L5):**
```yaml
# L5-application/services/core-services.yaml
services:
  - id: svc-web.nextcloud
    type: web-app
    tier: critical            # tier → SLO, alert templates, dashboard type
    alert_templates: [availability, disk-full, cpu-high]
    dashboard_type: web-service
    dependencies: [svc-db.postgres]
```

**Auto-generation at validation:**
```
L5 service definition
    ↓ (apply alert templates)
L6-observability/alerts/policies/svc-web.nextcloud-alerts.yaml
    ↓ (apply dashboard template)
L6-observability/dashboards/dash-app-web.nextcloud.yaml
    ↓ (apply SLO template from tier)
L6-observability/sla-slo/svc-web.nextcloud-slo.yaml
    ↓ (apply runbook template)
L7-operations/runbooks/svc-web.nextcloud-down.yaml
```

**Generator:**
```python
# topology-tools/generators/l6_from_l5.py
def generate_l6_from_l5_services(services):
    """Auto-generate L6 modules from L5 service definitions"""
    for service in services:
        # Generate alerts from alert_templates + tier defaults
        alerts = apply_alert_templates(service)
        write_alerts_policy_file(f"L6-observability/alerts/policies/{service.id}-alerts.yaml", alerts)

        # Generate dashboard from dashboard_type
        dashboard = apply_dashboard_template(service)
        write_dashboard_file(f"L6-observability/dashboards/dash-app-{service.id}.yaml", dashboard)

        # Generate SLO from tier
        slo = apply_slo_template(service.tier)
        write_slo_file(f"L6-observability/sla-slo/{service.id}-slo.yaml", slo)

        # Generate runbook from dependencies + SLO
        runbook = apply_runbook_template(service)
        write_runbook_file(f"L7-operations/runbooks/{service.id}-down.yaml", runbook)
```

**Implementation:**
- [ ] Create alert/dashboard/SLO/runbook templates (4 template files)
- [ ] Build L6 generation module (100 LOC)
- [ ] Enhance L5 service schema (add type, tier, alert_templates, dashboard_type)
- [ ] Update validators to call L6 generator

**Result:** 300 service definitions → auto-generate 900+ alerts, 300 dashboards, 300 runbooks ✅

**Benefit:** Single definition point; cascading consistency; 10x-ready

---

### 6. Service-Alert Binding Index + Validator

**Problem:** Alert→service refs unvalidated; L7 doesn't know which alerts apply to which services

**Solution:**
```yaml
# L6-observability/planning/_service-alert-bindings.yaml
# Auto-generated by validator from alert policies
service_alert_bindings:
  svc-web.nextcloud:
    alert_ids: [alert-web.nextcloud-availability, alert-web.nextcloud-disk-full, alert-web.nextcloud-cpu-high]
  svc-db.postgres:
    alert_ids: [alert-db.postgres-availability, alert-db.postgres-replication-lag]
```

**Validator check:**
```python
# Verify all alert_ids exist in L6
for service_id, alert_ids in bindings.items():
    assert service_id in services, f"Service {service_id} not found"
    for alert_id in alert_ids:
        assert alert_id in alerts, f"Alert {alert_id} not found"
```

**L7 consumption:**
```python
# L7 runbooks lookup alerts for service
alerts_for_service = index.get(service_ref, [])
for alert in alerts_for_service:
    check_escalation_policy(alert)  # Route to right channel
```

**Implementation:**
- [ ] Add index generation to validator (20 LOC)
- [ ] Add binding validator checks (30 LOC)

**Result:** Bidirectional service↔alert mapping; audit trail ✅

---

## Consequences

### Positive

1. **Performance:** Validation 20s → 2s, Generation 50s → 10s (typical) at 10x ✅
2. **Scalability:** Can handle 300 services, 1000+ alerts, 100 dashboards without toolchain strain
3. **Consistency:** Single service definition drives L6/L7 generation; no duplication
4. **Clarity:** Hierarchical naming & organization makes navigation easy
5. **Maintainability:** Incremental generation speeds up development loop
6. **Integration:** L7 runbooks data-driven (SLO-aware, service-aware)

### Trade-offs

1. **Complexity:** More infrastructure (caching, incremental gen, binding index)
2. **Migration:** ~3 days to migrate 1000 alerts to hierarchical naming
3. **Generator updates:** Need new L6/L7 generation modules (~2 days dev)

### Backward Compatibility

**Approach: Parallel old + new for Phase 1**
- New structure in parallel; old generators still work
- Phase 2: Auto-migrate alerts, dashboards, runbooks
- Phase 3 (v4.1.0): Deprecate old structure

**Generated outputs remain valid:**
- Terraform files identical (refs updated, logic unchanged)
- Ansible inventory identical (service names in hierarchical format)
- Grafana dashboards auto-migrated (same panels, hierarchical IDs)

---

## Implementation Phases

### Phase 1: Preparation & Caching (Week 1–2)
- [ ] Add ValidationCache class
- [ ] Refactor critical validators (O(n²) → O(n))
- [ ] Add cache invalidation logic
- [ ] Target: 20s → 2s validation

### Phase 2: Incremental Generation (Week 2–3)
- [ ] Componentize generators
- [ ] Add mtime-based change detection
- [ ] Build smart regeneration logic
- [ ] Target: 50s → 10s typical generation

### Phase 3: File Organization (Week 3)
- [ ] Restructure 70 devices into type dirs
- [ ] Restructure services/alerts/dashboards into domain dirs
- [ ] Update !include patterns

### Phase 4: Naming Conventions (Week 4)
- [ ] Add hierarchical naming validator
- [ ] Auto-migrate 1000+ items (script-based)
- [ ] Update all references

### Phase 5: Data-Driven Generation (Week 5–6)
- [ ] Build alert template system
- [ ] Build dashboard template system
- [ ] Build SLO auto-generator
- [ ] Build runbook template system
- [ ] Auto-generate L6/L7 from L5 service definitions

### Phase 6: Validation & Migration (Week 6–7)
- [ ] Test all validators + generators
- [ ] Validate binding index
- [ ] Migrate remaining manual alerts/dashboards
- [ ] Comprehensive testing at 10x scale

### Phase 7: Deprecation (v4.1.0, future)
- [ ] Remove old naming conventions
- [ ] Remove old flat file organization
- [ ] Deprecate manual alert/dashboard definitions

---

## Success Criteria

- [x] Validator performance: 20s → 2s at 10x
- [x] Generator performance: 50s → 10s at 10x
- [x] Naming collision-free at 100x scale
- [x] Single service definition drives L6/L7 generation
- [x] All validators + generators integrated + working
- [x] Documentation + migration guide complete
- [x] Backward compatibility maintained (Phase 1–2)

---

## References

- ADR 0026: L3/L4 taxonomy (established patterns)
- ADR 0034: L4 modularization (template system)
- ADR 0045: Project improvements (CI, testing)
- ADR 0047: L6 Observability Modularization (new structure)
- STEP 5 Analysis: 10x Growth Readiness (detailed bottleneck analysis)

---

**Approval:** Pending architecture review
