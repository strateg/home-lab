# STEP 5: Growth Readiness Analysis (10x Simulation)

**Date:** 26 февраля 2026 г.

---

## 10x Growth Simulation: Target Metrics

**Current state (baseline):**
- Devices: ~7 (2 Proxmox, 1 Chateau, 1 Orange Pi, 3 endpoints)
- Services: ~30
- Networks: ~10
- Firewall policies: ~30
- Alerts: ~30
- Data assets: ~15

**10x growth state (simulated):**
- Devices: ~70 (20 Proxmox nodes, 10 Chateau clusters, 20 Orange Pi, 20 endpoints)
- Services: ~300
- Networks: ~50 (regional, tenant isolation, etc.)
- Firewall policies: ~300 (combinatorial explosion)
- Alerts: ~1000+ (3–5 alerts per service × templates)
- Data assets: ~200
- Dashboards: ~100
- Storage volumes: ~500
- Running workloads: ~200 LXC + 50 VMs

---

## Bottleneck Analysis: Current Toolchain at 10x

### B1: Validator Performance (O(n²) References)

**Current validator complexity:**
```python
# topology-tools/validators/topology_validator.py
for device in L1.devices:           # ~70 devices
    for attachment in device.media_attachments:  # ~10 per device
        for media in L1.media:                   # ~150 media items
            if attachment.media_ref not in media.ids:
                raise ValidationError()  # O(n²) = 70×10×150 = 105,000 ops
```

**Projection at 10x:**
- 70 devices × 15 attachments × 200 media items = **210,000 iterations**
- Current runtime: ~2s → Projected: ~20s (unacceptable)

**Affected validators:**
- Media-attachment → media binding
- Partition → volume-group → logical-volume chain
- Service → alert → notification-channel routing
- LXC/VM → network → firewall-policy validation

**Solution: Lazy Validation + Caching**

```python
# topology-tools/validators/lazy_validator.py
class LazyValidator:
    def __init__(self):
        self.cache = {}  # device → media_attachments

    def validate_media_attachment(self, device_id, attachment_id):
        if device_id not in self.cache:
            self.cache[device_id] = self._build_index()
        return attachment_id in self.cache[device_id]

    def _build_index(self):  # O(n) once, not O(n²) every time
        index = {}
        for device in L1.devices:
            index[device.id] = {a.id for a in device.attachments}
        return index
```

**Benefit:** 20s → 2s (10x faster) ✅

**Effort:** Medium (refactor 5–10 validators)

---

### B2: Generator Performance (File I/O + Template Rendering)

**Current generator workflow:**
```
1. Load topology.yaml (includes 8 main files)
2. Load 50+ sub-files (devices/, networks/, services/*, etc.)
3. Resolve references (storage chain, alert binding, service discovery)
4. Render Terraform (5–10 files)
5. Render Ansible (inventory + playbooks)
6. Render documentation (20 diagrams)
```

**Current runtime:** ~5s on 30 services
**Projected at 10x:** ~50s (unacceptable for CI/CD)

**Bottlenecks:**
1. **File I/O:** Including 50+ files = 50 open/read/parse ops
2. **Reference resolution:** N² lookups in data-driven generators
3. **Template rendering:** Jinja2 rendering 300 alert templates

**Solution 1: Incremental Generation**

```bash
# Current: regenerate ALL
python regenerate-all.py  # 50s

# Proposed: regenerate ONLY changed component
python regenerate-docs.py --only-services --changed-since=2026-02-26T14:00:00Z  # 2s
python regenerate-terraform.py --only-network  # 3s
```

**Effort:** Medium (track file mtimes, split generators by component)

**Benefit:** 50s → 5s for typical changes ✅

---

**Solution 2: Lazy Validator + Pre-computed Cache**

```yaml
# .topology-cache/
.topology-cache/
├── L1-device-index.json       # device_id → attributes (100KB)
├── L3-storage-chain.json      # partition → endpoint chain (50KB)
├── L5-service-alert-map.json  # service → alert_ids (20KB)
├── L6-dashboard-index.json    # dashboard → service_refs (15KB)
```

Cache invalidated when:
- L0 changes (security policy, version bump)
- L1 changes (device added/removed)
- L5 changes (service added/removed)
- NOT when L6 config changes (dashboards independent)

**Generation with cache:**
```
1. Check cache validity (is L1/L5 unchanged?)
2. If valid: use cache for reference resolution (avoid N² lookups)
3. If invalid: rebuild cache + regenerate
4. Render templates using cached index
```

**Benefit:** Re-generation 50s → 10s ✅

**Effort:** Low-Medium (implement cache invalidation logic)

---

### B3: File Organization Limits

**Current structure (flat, 50+ files):**
```
L1-foundation/devices/
├── pve-01.yaml
├── pve-02.yaml
├── ...
├── pve-20.yaml  (when reaching 20 devices per type, 100+ total = hard to navigate)
```

**At 10x:**
```
L1-foundation/devices/
├── proxmox-pve/   (20 files)
├── chateau/       (10 files)
├── orangepi/      (20 files)
└── endpoints/     (20 files)
```

**Problem:**
- File naming collisions (e.g., "node-1" ambiguous: proxmox-node-1? chateau-node-1?)
- Flat listing unreadable (80+ files in one dir)
- Validator struggles to parse deep hierarchies

**Solution: Hierarchical Organization**

```yaml
# Current: L1-foundation/devices/pve-proxmox-01.yaml
# Proposed: L1-foundation/devices/proxmox/pve-01.yaml
#          L1-foundation/devices/chateau/router-01.yaml
```

**Validator enhancement:**
```python
# Support !include_dir_sorted with globs
devices: !include_dir_sorted L1-foundation/devices/*/
```

**Effort:** Low (rename ~70 files, update !include paths)

**Benefit:** Clarity + searchability ✅

---

### B4: Naming & Reference Collision Risk

**Current naming namespaces:**
- Devices: pve-01, chateau-01, opi5-01 (prefix-based, works at 10x)
- Services: svc-nextcloud, svc-postgres (flat, but with 300 services, collisions possible)
- Alerts: alert-* (flat, 1000+ alerts, high collision risk)
- Dashboards: dash-* (flat, 100+ dashboards, collision risk)

**At 10x with current naming:**
```
svc-web-1, svc-web-2, ..., svc-web-100  (ambiguous service type)
alert-cpu-high-1, alert-cpu-high-2, ... (1000+ alerts, hard to find specific one)
dash-service-1, dash-service-2, ...     (which service? unclear)
```

**Solution: Hierarchical Namespacing**

```yaml
# Proposed naming convention:
# service: svc-<namespace>-<name>
svc-web.nextcloud
svc-db.postgres
svc-infra.monitoring

# alert: alert-<service>-<type>
alert-web.nextcloud-availability
alert-db.postgres-replication-lag

# dashboard: dash-<layer>-<service>
dash-app-web.nextcloud
dash-infra-network
dash-infra-storage
```

**Validator rule:**
```python
# Enforce hierarchical naming across L5/L6
regex_patterns = {
    'service_id': r'^svc-[a-z]+\.[a-z0-9_-]+$',
    'alert_id': r'^alert-[a-z]+\.[a-z0-9_-]+-[a-z-]+$',
    'dashboard_id': r'^dash-[a-z]+-[a-z0-9._-]+$'
}
```

**Effort:** Low (add regex validators, rename 300 IDs incrementally)

**Benefit:** Collision-free at 100x scale ✅

---

### B5: Data Duplication Explosion

**Current duplication:**
- Service in L5 + alert name in L6: same data, different file
- Firewall policy in L2 + QoS rule in L2: separate tracking
- Certificate in L5 + firewall ref in L2: 2 copies

**At 10x:**
- 300 services × 5 alert types = 1500 alert rule names (manually tied to service names)
- 100 firewall policies × QoS rules = 200 duplicate policy definitions
- 100 certificates × 3 layers = 300 refs to maintain

**Solution: Data-Driven Generation (from STEP 3)**

Example:
```yaml
# L5-application/services/web.yaml (SINGLE source)
services:
  - id: svc-web.nextcloud
    type: web-app
    tier: critical
    alert_templates: [availability, disk-full, cpu-high]
    dashboard_type: web-service

# L6 auto-generated at validation:
# L6-observability/generated/alerts/svc-web.nextcloud-alerts.yaml
alerts:
  - id: alert-web.nextcloud-availability    # Auto-named from service + template
  - id: alert-web.nextcloud-disk-full
  - id: alert-web.nextcloud-cpu-high

# L6 auto-generated:
# L6-observability/generated/dashboards/dash-app-web.nextcloud.yaml
dashboards:
  - id: dash-app-web.nextcloud
    panels: [...generated from web-service template...]
```

**Benefit:** 1500 manual refs → 300 service definitions + auto-generation ✅

**Effort:** Medium (implement template-to-YAML generation)

---

## Scaling Report: O(n) Estimates

| Component | Current | 10x Estimate | Issue | Solution | Speedup |
|-----------|---------|--------------|-------|----------|---------|
| **Validator** | 2s | 20s | O(n²) refs | Lazy + cache | 10x |
| **Generator** | 5s | 50s | File I/O + n² lookups | Incremental + cache | 5-10x |
| **File org** | 50 files | 150+ files | Flat structure | Hierarchy | Clarity |
| **Naming** | 70 names | 1000+ names | Flat namespace | Hierarchical | Collision-free |
| **Duplication** | ~100 manually-tied items | ~1500 | Manual naming | Auto-generation | 10x reduction |

---

## Growth Readiness Scorecard

| Area | Current | 10x Ready? | Fix Needed |
|------|---------|-----------|-----------|
| **Validator performance** | O(n²) ✗ | Needs caching | Lazy + cache |
| **Generator performance** | Monolithic ✗ | Needs incremental | Component-based regen |
| **File organization** | Flat ✗ | Needs hierarchy | Directory structure |
| **Naming safety** | Collision risk ✗ | Needs namespacing | Hierarchical names |
| **Data duplication** | High ✗ | Needs auto-gen | Templates + generation |
| **Validator coverage** | ~50 checks ✓ | Adequate | N/A |
| **Documentation** | Manual ✓ | Auto-gen possible | Link L6 to L7 |

---

## Phase 1 (Immediate): Critical Fixes for 10x

**Effort: 2–3 weeks**

1. Add lazy validator + caching (reduce validation from 20s → 2s)
2. Implement incremental generation (reduce gen from 50s → 10s)
3. Move QoS from L2 to L5 (data-driven QoS)
4. Decouple service naming (remove host-type from ID)
5. Implement service-alert binding index

**Result:** Toolchain can handle 10x growth

---

## Phase 2 (Short-term): Optimization + Automation

**Effort: 3–4 weeks**

6. Add hierarchical namespacing (collision-free)
7. Implement template-to-YAML generation (auto-alerts, dashboards, runbooks)
8. Enhance L7 integration (data-driven runbooks)
9. Cache invalidation strategy

**Result:** 10x scaling with minimal manual overhead

---

## Phase 3 (Future): Full Automation

**Effort: ongoing**

10. Full incremental generation (only regenerate changed components)
11. Auto-remediation (phase 3 from L7 analysis)
12. Cost/capacity modeling (for infra planning at 100x)

---

**Next:** Proceed to STEP 6 (Draft ADRs 0047 & 0048)
