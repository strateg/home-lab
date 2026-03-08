# OS Modeling: Decision Matrix & Scenarios

**Date:** 2026-03-08  
**Purpose:** Help choose between property and class models based on specific scenarios

---

## Decision Matrix: Quick Selection

### Scenario 1: Single-OS Infrastructure (All Devices Use Fixed OS)

**Characteristics:**
- All VMs run Debian 12
- All routers run RouterOS 7
- No variation or specialization
- Low change rate

| Aspect | Property Model | Class Model |
|--------|---|---|
| Schema complexity | ⭐⭐ Simple | ⭐⭐⭐⭐ Structured |
| OS definition | Embedded in each device | Centralized in OS class |
| Reuse efficiency | ⭐ (20 copies) | ⭐⭐⭐⭐⭐ (1 definition) |
| Maintenance | Per-device | Single source |
| Service validation | Runtime | Compile-time |
| **Recommendation** | ✓ Acceptable | ✓ Better long-term |

---

### Scenario 2: Multi-OS, Multi-Variant Infrastructure

**Characteristics:**
- Multiple OS families (Linux, RouterOS, Windows, proprietary)
- Multiple distributions (Debian, Ubuntu, Alpine)
- Multiple release versions (Debian 11, 12, 13)
- Specialization variants (standard, hardened, minimal)
- Frequent OS updates

| Aspect | Property Model | Class Model |
|--------|---|---|
| Schema complexity | ⭐⭐⭐ Scattered | ⭐⭐⭐⭐ Organized |
| OS definition | Duplicated 50+ times | Centralized, ~20 instances |
| Reuse efficiency | ⭐ (High duplication) | ⭐⭐⭐⭐⭐ (No duplication) |
| Maintenance | Error-prone | Single update → all devices |
| Service validation | Unreliable | Guaranteed |
| **Recommendation** | ✗ Not recommended | ✓✓✓ Highly recommended |

---

### Scenario 3: Firmware vs. Installable Mixed

**Characteristics:**
- Router devices with firmware OS
- VM devices with installable OS
- Appliances with proprietary firmware
- Need to enforce firmware on routers, installable on VMs

| Aspect | Property Model | Class Model |
|--------|---|---|
| Distinction | Implicit (documentation) | Explicit (schema enforcement) |
| Risk of mixing | Possible (developer error) | Prevented (compiler error) |
| Validation | Convention-based | Rule-based |
| Enforcement | Manual review | Automatic |
| **Recommendation** | ~ Requires discipline | ✓✓ Strongly recommended |

---

### Scenario 4: Service/Workload Requirements

**Characteristics:**
- Services have explicit OS requirements
- Prometheus: needs Linux + systemd + apt
- PostgreSQL: needs Linux only
- DNS: can be BIND (Linux) or proprietary firmware (RouterOS)
- Need to know: "What can run Prometheus?"

| Aspect | Property Model | Class Model |
|--------|---|---|
| Requirement expression | Supported | Supported |
| Validation timing | Runtime (deploy time) | Compile-time (schema validation) |
| Error detection | Late (after provisioning) | Early (before deployment) |
| Device compatibility query | Manual/scripted | Automatic (compiler) |
| Compatibility matrix generation | Not automated | Automatic |
| **Recommendation** | ✓ Works | ✓✓ Better |

---

### Scenario 5: Cloud/Container Workloads

**Characteristics:**
- VMs with flexible OS choice
- Containers with specific base images
- AWS AMIs, GCP images, Docker bases
- Multi-instance deployments with same OS config
- Dynamic OS selection per deployment

| Aspect | Property Model | Class Model |
|--------|---|---|
| Flexibility | ✓ Per-instance config | ✓ Per-instance binding |
| Reuse of OS config | ~ Manual | ✓✓ Automatic reference |
| Image format support | In property | In OS class (cleaner) |
| Multi-image variants | Workaround needed | Native support |
| Build system integration | Script-based | Direct reference |
| **Recommendation** | ✓ Works | ✓✓ Integrates better |

---

### Scenario 6: OS Lifecycle Management

**Characteristics:**
- Track which devices run EOL OS
- Plan upgrades by OS version
- Audit: "All Debian 11 → Debian 12" progress
- Compliance: "Must not run OS < 2 years old"
- Historical tracking: "Device X used Debian 11 until 2025-06-15"

| Aspect | Property Model | Class Model |
|--------|---|---|
| OS instance tracking | Implicit (in each device) | Explicit (OS registry) |
| EOL tracking | Per-device property | Single OS class property |
| Queries | Script devices for OS version | Query OS class instances |
| Compliance automation | Complex scripting | Compiler generates report |
| Upgrade impact analysis | "Update 50 device files" | "Update 1 OS instance" |
| **Recommendation** | ✗ Not practical | ✓✓✓ Essential |

---

## Infrastructure Size vs. Model Fit

### Small Lab (5-20 devices)

**Typical:** Home lab, POC, testing

| Property Model | Class Model |
|---|---|
| ✓ Overhead not noticeable | ~ More structure than needed |
| ✓ Duplication acceptable | ✓ Sets good habits |
| ✓ Simple schema enough | ✓ Future-proof |
| **Score:** 7/10 | **Score:** 7/10 |

**Recommendation:** Either model works; class model better for learning.

---

### Medium Lab (20-100 devices)

**Typical:** Small business, startup, growing infrastructure

| Property Model | Class Model |
|---|---|
| ~ Duplication becomes annoying | ✓ Reuse starts paying off |
| ✗ Updates require touching many files | ✓ Single change, all devices updated |
| ~ Service validation manual | ✓✓ Automated compatibility matrix |
| **Score:** 4/10 | **Score:** 8/10 |

**Recommendation:** Class model recommended; duplication costs exceed implementation cost.

---

### Large Lab (100+ devices)

**Typical:** Enterprise, multi-site, complex infrastructure

| Property Model | Class Model |
|---|---|
| ✗ Duplication is major burden | ✓✓ Reuse essential |
| ✗ OS updates error-prone at scale | ✓ Single source of truth |
| ✗ Compliance audits expensive | ✓✓ Automated reporting |
| **Score:** 2/10 | **Score:** 9/10 |

**Recommendation:** Class model essential; property model becomes unmaintainable.

---

## Device Type Matrix

### By Hardware Category

| Device Type | OS Model | Binding Style | Best Fit |
|-----------|----------|--------|---|
| **VM (KVM, Proxmox, VMware)** | Installable | Flexible choice | Class (multi-variant) |
| **LXC/Container** | Installable | Base image | Class (image reference) |
| **Cloud Instance (AWS, GCP)** | Installable | AMI/image | Class (cloud-specific) |
| **Router (Mikrotik, Ubiquiti)** | Firmware | Hardware-locked | Class (firmware subclass) |
| **Appliance (TrueNAS, Proxmox HW)** | Firmware | Vendor-controlled | Class (firmware subclass) |
| **IoT/Embedded** | Firmware | Hardware-locked | Class (firmware subclass) |
| **Bare-Metal Server** | Installable | Network boot | Class (multi-variant) |
| **PDU, UPS** | None | N/A | N/A |
| **Storage Shelf** | None | N/A | N/A |

**Pattern:** All computing devices benefit from class model, but firmware devices especially.

---

## Complexity vs. Benefit Analysis

### Property Model

**When to use:**
- ✓ Single OS per device
- ✓ No firmware/installable distinction needed
- ✓ No service-OS validation required
- ✓ Very small infrastructure (< 5 devices)
- ✓ Prototype/POC phase

**When NOT to use:**
- ✗ 10+ devices per OS variant (duplication burden)
- ✗ Mixed firmware + installable (ambiguity risk)
- ✗ Service requirements validation (late error detection)
- ✗ OS specialization planned
- ✗ Multi-OS devices anticipated

### Class Model

**When to use:**
- ✓ 10+ devices per OS variant (reuse benefit)
- ✓ Mixed firmware + installable (explicit distinction)
- ✓ Service-OS validation important (safety)
- ✓ OS specialization needed (variants)
- ✓ Multi-OS scenarios likely (extensibility)
- ✓ Long-term infrastructure (5+ year horizon)

**When NOT to use:**
- ✗ Simplicity is paramount priority
- ✗ Tiny infrastructure (< 5 devices, unlikely to grow)
- ✗ One-off deployment (never changes)
- ✗ No compiler/build infrastructure

---

## Risk Analysis

### Property Model Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|---|
| OS definition duplication | High | Medium | Accept, document pattern |
| Firmware/installable confusion | High | High | Strict naming convention |
| Service-OS mismatches | High | High | Manual testing required |
| OS update errors at scale | Medium | High | Careful review process |
| Specialization impossible | Low | Medium | Accept limitation |
| Multi-OS not supported | Low | Low | Redesign if needed |

**Risk score:** 5.5/10 (moderate)

---

### Class Model Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|---|
| Implementation complexity | Medium | Low | 5-phase migration |
| Compiler bugs in bindings | Low | Medium | Comprehensive testing |
| OS instance proliferation | Medium | Low | Registry discipline |
| Migration disruption | Low | Medium | Backward compatibility |
| Operator learning curve | Medium | Low | Training & docs |
| Dangling OS references | Low | High | Compiler validation |

**Risk score:** 3.0/10 (low)

---

## Your Specific Infrastructure Context

**Based on your repository structure** (`v5/` topology, Proxmox, RouterOS, services):

### Identified Device Types
- ✓ VMs on Proxmox (installable OS)
- ✓ RouterOS routers (firmware OS)
- ✓ Services/workloads (OS requirements)
- ✓ Planned cloud instances (AWS, GCP)

### Identified OS Requirements
- ✓ Multiple Debian versions (11, 12, possibly 13)
- ✓ Ubuntu support (22.04, 24.04)
- ✓ Alpine (container/edge)
- ✓ RouterOS (firmware)
- ✓ Hardened variants (planned per ADRs)

### Identified Scenarios
- ✓ Service-device compatibility checking
- ✓ OS upgrade planning
- ✓ Multi-site consistency
- ✓ Compliance/audit trails

---

## Recommendation for Your Lab

### Specific Fit Analysis

| Factor | Assessment |
|--------|---|
| Infrastructure size | Medium (growing) → **Class model scales better** |
| Device diversity | High (VMs + routers + appliances) → **Class model enforces distinctions** |
| OS variety | High (Debian, Ubuntu, Alpine, RouterOS) → **Class model prevents duplication** |
| Service needs | Complex (service-OS requirements) → **Class model validates at compile time** |
| Build automation | Advanced (v5 compiler/validators) → **Class model leverages tooling** |
| Long-term horizon | Multi-year (ADRs plan future) → **Class model future-proof** |

### Score Summary

| Model | Fit Score | Confidence |
|-------|----------|---|
| Property | 5/10 | Medium |
| Class | 8.5/10 | High |

### Confidence Factors

**Why class model is strong fit:**
1. RouterOS firmware requires firmware/installable distinction
2. Multiple Debian versions = significant duplication in property model
3. v5 compiler infrastructure supports class-based validation
4. Multi-year horizon justifies implementation investment
5. Future service/workload layer needs compile-time validation

**Why property model is weak fit:**
1. No natural way to distinguish firmware vs. installable
2. Duplication becomes burden as infrastructure grows
3. Late error detection conflicts with infrastructure-as-code philosophy
4. Extensibility limitations (specialization, multi-OS) will become barriers

---

## Final Decision Matrix

```
Choose PROPERTY MODEL if:
  □ Infrastructure < 10 devices
  □ All devices use same OS
  □ No firmware/installable distinction needed
  □ Speed to deployment > 2 months
  □ No service-OS validation needs

Choose CLASS MODEL if:
  ✓ Infrastructure > 20 devices
  ✓ Mixed firmware + installable devices
  ✓ 10+ variants of any OS
  ✓ Service-OS validation important
  ✓ Multi-year operational horizon
  ✓ Willing to invest 5 weeks in implementation

** For your lab: ALL CHECKBOXES ARE CHECKED FOR CLASS MODEL **
```

---

## Implementation Timeline Estimate

**If choosing CLASS MODEL:**

| Phase | Duration | Key Deliverable |
|-------|----------|---|
| Phase 1: Classification | 1-2 weeks | Add `installation_model` field |
| Phase 2: Class System | 2-3 weeks | Create OS class, instances, compiler support |
| Phase 3: Parallel Validation | 1-2 weeks | Migrate 50% of devices |
| Phase 4: Deprecation | 1 week | Migrate remaining 50%, warn on property use |
| Phase 5: Cleanup | 1 week | Remove property model, deprecation complete |
| **Total** | **6-9 weeks** | **Complete migration** |

**Parallelization opportunity:** Phases 2 & 3 can overlap, reducing timeline to 5-6 weeks.

---

## Conclusion

**For your home-lab infrastructure:**

- **Device diversity** (VMs, routers, appliances) → need firmware distinction
- **Growing size** (20+ devices) → need reuse efficiency
- **Advanced tooling** (v5 compiler) → can support class model
- **Long planning** (multi-year ADRs) → justify 5-week investment

**Recommended:** Adopt class-based OS model with 5-phase migration.

**Next step:** Review ADR 0064 revision proposal and plan Phase 1 kickoff.
