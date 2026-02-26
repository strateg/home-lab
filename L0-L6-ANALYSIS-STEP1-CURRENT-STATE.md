# Topology Layers Analysis: L0–L6 Current State Audit

**Date:** 26 февраля 2026 г.
**Analyst:** AI-assisted topology architecture review
**Scope:** Full 6-step analysis for 10x growth readiness

---

## STEP 1: Current State Audit (L0–L6)

### Layer Summary Table

| Layer | Name | Purpose | Key Responsibilities | External Dependencies | File Org | Growth Constraints |
|-------|------|---------|----------------------|----------------------|----------|-------------------|
| **L0** | Meta | Global config, policies | Version, defaults, security policies | None (root) | Single file `L0-meta.yaml` | Monolithic; security policy growth unstructured |
| **L1** | Foundation | Physical inventory | Devices, interfaces, MACs, media, power/data links | None | Modular: devices/, media/, media-attachments/, data-links/, power-links/ | Device/interface naming space; media registry scaling |
| **L2** | Network | Logical networking | Networks, bridges, trust-zones, firewall, QoS, routing | L1 (device_refs) | Modular: networks/, firewall/, qos/, routing/ | Firewall policy explosion; QoS rule duplication; trust-zone refs |
| **L3** | Data | Storage & data assets | Partitions, volumes, filesystems, endpoints, data assets | L1 (device_ref), L2 (network refs for NAS) | Modular: partitions/, logical-volumes/, storage-endpoints/, data-assets/ | Storage chain resolution O(n²); data asset explosion |
| **L4** | Platform | Compute workloads | VMs, LXC, resource profiles, host OSes, templates | L1 (device_refs), L3 (storage_refs), L2 (network_refs) | Modular: workloads/lxc, workloads/vms, resource-profiles/, templates/ | Resource profile explosion; template duplication; cross-ref validation |
| **L5** | Application | Services | Services (by host), DNS, certificates | L4 (lxc_ref, vm_ref, device_ref), L2 (network_ref) | Modular: services/mikrotik/, services/orangepi5/, services/proxmox/ | Service naming collisions; port binding conflicts; certificate duplication |
| **L6** | Observability | Monitoring & alerts | Healthchecks, monitoring, alerts, dashboards, notifications | All layers (data-driven refs to L4/L5 services) | Modular: healthchecks/, alerts/, dashboards/ | Alert rule explosion (1000+ with 10x growth); notification duplication; dashboard refs loose |

---

## STEP 1 Detail: Layer Bottleneck Analysis

### L0 Meta
**Current State:**
- Single monolithic `L0-meta.yaml` (76 lines)
- Declares version, metadata (changelog), defaults (refs), security policies
- No submodules

**Growth Constraints:**
- Security policy grows (add auth methods, encryption standards, audit logging) → becomes unwieldy
- Defaults/refs multiply (multiple security contexts, multi-tenancy support)
- Changelog becomes large

**Coupling:**
- Referenced by all generators (validator/terraform/ansible/docs)
- Security policy ref by all L1–L5 (all devices/services respect sec-baseline)

**Recommendation:**
- Split L0 into: meta/version.yaml, meta/defaults.yaml, meta/security-policies/, meta/audit-policies/
- Lazy-load policies for scaling

---

### L1 Foundation
**Current State:**
- Modular (devices/, media/, media-attachments/, data-links/, power-links/)
- ~20 devices, ~50 media items, ~100+ links

**Growth Constraints:**
- Device naming space (8-char prefix limit?) may collide at scale
- Media registry becomes flat list → hard to organize by type/location at 100+ items
- Media-attachment bindings O(n²) validation (each device×slot×media combination check)
- Power/data link duplication (redundant cable documentation)

**Coupling:**
- All other layers reference L1 devices (device_refs in L2/L3/L4/L5)
- Storage slots/media-attachments critical for L3 disk bindings

**Recommendation:**
- Introduce media classification (by type/vendor/form-factor) → media/{ssd/hdd/nvme}/
- Device naming schema with namespace prefixes (pve-*, opi5-*, mikrotik-*, etc.)
- Media-attachment lazy validation (resolve only needed bindings)

---

### L2 Network
**Current State:**
- Modular (networks/, firewall/, routing/, qos/, trust-zones/)
- ~10 networks, ~30 firewall policies, ~5 trust zones, ~20 QoS rules

**Growth Constraints:**
- Firewall policies grow combinatorially (source×dest×protocol×action) → 1000+ rules at 10x
- QoS rule names lack namespace (svc-*-qos-out, svc-*-qos-in repeated)
- Trust-zone refs scattered (networks, firewall, routing each have zone_ref) → synchronization risk
- Network CIDR planning becomes unmanageable without overlapping segment registry

**Coupling:**
- Firewall policies ref trust-zones (tight coupling)
- QoS rules bound to networks (should be bound to services in L5?)
- Routing rules ref bridges (L1-derived)

**Recommendation:**
- Introduce network planning layer (L2-network/planning/cidr-registry.yaml)
- Unify firewall-policy structure: firewall-policies/by-type/{ingress,egress,internal}/
- Move QoS from L2 → L5 (bind QoS to service, not network)
- Trust-zone as first-class ref (all policies lookup from zone registry)

---

### L3 Data
**Current State:**
- Modular (partitions/, logical-volumes/, storage-endpoints/, data-assets/)
- Storage chain: partitions → volume-groups → logical-volumes → filesystems → mount-points → endpoints
- ~50 partitions, ~30 logical volumes, ~20 endpoints, ~15 data assets

**Growth Constraints:**
- Storage chain resolution is O(n) nested lookups (partition→vg→lv→fs→mount→endpoint)
- At 10x: 500 partitions, 300 LVs → 10x slowdown in validators/generators
- Data asset refs explosion (asset.storage_endpoint_refs, asset.runtime_refs scatter refs)
- Filesystem mountpoint naming lacks hierarchy (flat /mnt/* namespace)

**Coupling:**
- Data-assets ref storage-endpoints (tight, but unresolved in validators)
- Partitions ref L1 media-attachments (critical for boot/root)
- Logical-volumes ref L4 VMs/LXC via resolved_runtime_refs (backward ref risk)

**Recommendation:**
- Introduce storage-pool abstraction layer (group LVs by purpose: system/data/backup)
- Lazy-resolve storage chains (cache partition-to-endpoint mappings)
- Data-asset refs via pool-id instead of endpoint-refs (decoupling)
- Mount-point hierarchical namespace planning (registry in L3/planning/)

---

### L4 Platform
**Current State:**
- Modular (workloads/lxc/, workloads/vms/, resource-profiles/, templates/)
- ~5 LXC, ~3 VMs, ~10 resource profiles, ~2 VM templates

**Growth Constraints:**
- Resource profiles duplicated across workloads (inline resources vs profile_ref clash)
- LXC/VM template inheritance unspecified (inherits which profile by default?)
- Cross-device resource allocation not planned (can we oversubscribe CPU at 10x?)
- Host OS binding (host_operating_systems) not dynamic (hard-coded per device)

**Coupling:**
- Workloads ref L3 storage (storage_ref, disk_refs)
- Workloads ref L2 networks (interface → network_ref)
- Workloads ref L1 devices (device_ref for location)
- Resource profiles shared (but not versioned)

**Recommendation:**
- Unify resource model: resource-profiles/ as source-of-truth (deprecate inline resources)
- Template inheritance: introduce template-inheritance registry
- Capacity planning layer (L4/planning/resource-capacity.yaml) with aggregation
- Dynamic host-OS selection based on device class

---

### L5 Application
**Current State:**
- Modular (services/mikrotik/, services/orangepi5/, services/proxmox/, services/lxc/)
- ~30 services, ~20 DNS records, ~10 certificates

**Growth Constraints:**
- Service naming by host-type (svc-orangepi5-nextcloud) creates L5↔L4 tight coupling
- Port allocation conflicts (no registry, manual tracking)
- Certificate refs scattered (service.certificate_ref, firewall.cert_ref, etc.)
- Service dependencies (svc-A depends on svc-B) not modeled

**Coupling:**
- Services ref L4 workloads (lxc_ref, vm_ref, device_ref)
- Services ref L2 networks (service.network_ref for listen address)
- Certificates ref services (but validation is weak)

**Recommendation:**
- Introduce service-registry (L5/planning/service-registry.yaml) with namespace-first naming
- Port allocation registry (L5/planning/port-registry.yaml with reserved ranges)
- Service dependency DAG (L5/planning/service-dependencies.yaml)
- Shared certificate store (L5/certificates/ with SAN planning)
- Decouple service naming from host-type (svc-nextcloud → deployed on orangepi5, not in name)

---

### L6 Observability
**Current State:**
- Modular (healthchecks/, alerts/, dashboards/, notification-channels/, network-monitoring/)
- ~10 healthchecks, ~30 alerts, ~5 dashboards, ~3 notification channels, 1 network-monitoring

**Growth Constraints:**
- Alert naming lacks hierarchy (flat alert-* namespace)
- Alert refs to L5 services (alert.service_ref) but no alert-service mapping index
- Dashboard refs loose (dashboard.service_refs not validated)
- Notification rules ad-hoc (no escalation policy, no routing rules)
- Missing modules: SLA/SLO definitions, incident-response playbooks, metric-definitions

**Coupling:**
- Alerts ref L5 services (service_ref) but not type-safe
- Healthchecks ref L4 workloads (lxc_ref/vm_ref)
- Dashboard targets L5/L4 data (but refs unvalidated)
- Network-monitoring refs L2 networks (bridge_ref for tap interfaces)

**Recommendation:**
- Restructure L6 as three sub-layers: metrics, alerts, dashboards (each with own naming namespace)
- Introduce L6/planning/alert-strategy.yaml (escalation, routing, SLA/SLO templates)
- Formalize service↔alert binding contract (L6/references/service-alerts.yaml index)
- Add modules: L6/sla-slo/, L6/incident-response/, L6/metrics-definitions/
- Lazy-load alert rules (only for enabled services)

---

## Summary: Bottleneck Scoring (Priority for Refactoring)

**Critical (must fix for 10x):**
1. L3 storage chain resolution (O(n²) → caching + lazy-load)
2. L5 service naming (decouple from host-type)
3. L6 alert explosion (structured hierarchy + lazy-load)

**High (address in Phase 1):**
4. L2 firewall/QoS growth (unify policy structure, move QoS to L5)
5. L4 resource profile duplication (centralize, version)
6. L6 service↔alert binding (formalize contract)

**Medium (Phase 2):**
7. L0 security policy growth (split into submodules)
8. L1 media registry scaling (classify by type)
9. L5 port/certificate registry (introduce planning layers)

---

**Next:** Proceed to STEP 2 (L6 Observability Modularization Design)
