# OS Model Redesign: Executive Summary and Recommendation

**Date:** 2026-03-08  
**Status:** Ready for Review  
**Format:** Executive decision document

---

## The Question

How should we model Operating Systems in v5 topology?

Two approaches:
1. **Property Model** (Current ADR 0064): OS as structured property on objects
2. **Class Model** (Proposed): OS as first-class entity with explicit bindings

---

## Quick Comparison

### Property Model (Current)

```yaml
vm-app-01:
  software:
    os:
      family: linux
      distribution: debian
      release: "12"
      # ... other fields ...
```

**Pros:**
- ✓ Minimal schema
- ✓ OS tied to device (tight coupling appropriate for firmware)
- ✓ Simple to understand

**Cons:**
- ✗ No distinction: firmware vs. installable OS
- ✗ OS reuse = duplication (20 VMs = 20× definition)
- ✗ Runtime validation only
- ✗ Multi-OS devices impossible
- ✗ OS specialization not supported

---

### Class Model (Proposed)

**OS as separate class:**
```yaml
class: os.installable
  properties: {family, distribution, release, installation_model, ...}
  instances:
    - debian-12-generic
    - debian-12-hardened
    - ubuntu-22.04
```

**Device references OS:**
```yaml
vm-app-01:
  bindings:
    os: obj.os.debian.12.generic
```

**Pros:**
- ✓ Firmware vs. installable explicitly distinguished
- ✓ OS reuse (no duplication)
- ✓ Compile-time service-device validation
- ✓ Multi-OS devices supported
- ✓ OS specialization/inheritance supported
- ✓ OS lifecycle independent from device lifecycle

**Cons:**
- ✗ More files/structure
- ✗ One more indirection layer
- ✗ Requires compiler refactoring

---

## Key Decision Points

### 1. Firmware vs. Installable: How explicit should this be?

| Model | Distinction |
|-------|---|
| Property | Implicit (convention, documentation) |
| Class | Explicit (`os.firmware` vs `os.installable` subclasses) |

**For your infrastructure:** Router firmware is fundamentally different from VM guest OS.
- RouterOS is locked to hardware
- Debian can be swapped per deployment

**Recommendation:** Make this explicit at schema level, not convention.

---

### 2. OS Reuse: How important is avoiding duplication?

**Current situation (Property Model):**
- 20 Debian 12 VMs = 20× copy of full OS definition
- Change to Debian 12? Edit all 20 files
- No authoritative "Debian 12 definition"

**With Class Model:**
- 1 OS instance: `obj.os.debian.12.generic`
- All 20 VMs reference it
- Single source of truth
- Change once, affects all 20 VMs automatically

**For your lab:** If you have 5-10 VMs per OS version, duplication will grow annoying fast.

**Recommendation:** Class model saves maintenance effort long-term.

---

### 3. Service Compatibility: How important is compile-time validation?

**Property Model:**
- Service requires: `[cap.os.linux, cap.os.init.systemd]`
- Device has: `software.os: {family: routeros, ...}`
- Validation: Runtime check (deploy time, if at all)
- "Will Prometheus run?" → Unknown until deployment

**Class Model:**
- Service requires: `[cap.os.linux, cap.os.init.systemd]`
- Device bound to: `obj.os.debian.12.generic` (Linux, systemd)
- Compiler derives: `[cap.os.linux, cap.os.debian, cap.os.init.systemd]`
- Validation: Compile-time check (schema validation)
- "Will Prometheus run?" → YES (or ERROR + reason)
- Auto-generate: "What devices CAN run Prometheus?"

**For your infrastructure:** Early error detection is cheaper than deploy-time failures.

**Recommendation:** Class model enables safety checks that matter.

---

### 4. Multi-OS Devices: Will you ever need this?

**Scenarios where needed:**
- Dual-boot development machine
- Raspberry Pi with multiple SDCard images
- Live-boot + persistent installation

**Property Model:** Not supported (array syntax breaks schema)

**Class Model:** Supported:
```yaml
bindings:
  os_primary: obj.os.debian.12
  os_secondary: obj.os.ubuntu.22.04
  os_live: obj.os.alpine.3.19
```

**For your lab:** Edge devices might benefit from this in future.

**Recommendation:** Class model keeps door open.

---

### 5. OS Specialization: Do you need variants?

**Example:** Debian 12 standard vs. Debian 12 hardened

**Property Model:** Not really supported, would need ad-hoc extensions

**Class Model:** Clean inheritance:
```yaml
debian-12-generic:
  properties: {family: linux, distribution: debian, release: "12"}

debian-12-hardened:
  inherits: debian-12-generic
  extra_properties: {selinux_enabled: true, apparmor_enabled: true}
  added_capabilities: [cap.security.selinux, cap.security.apparmor]
```

**For your lab:** Useful for security-sensitive workloads.

**Recommendation:** Class model supports future needs.

---

## Weighted Scoring

| Criterion | Property | Class | Weight |
|-----------|----------|-------|--------|
| Schema simplicity | 10 | 6 | 1× |
| Firmware distinction | 3 | 10 | 3× |
| OS reuse efficiency | 4 | 10 | 2× |
| Compile-time validation | 4 | 10 | 3× |
| Multi-OS support | 2 | 10 | 1× |
| OS specialization | 2 | 9 | 1× |
| Backward compatibility | 10 | 5 | 1× |
| Operator familiarity | 9 | 6 | 2× |
| **Weighted Total** | **62** | **68** | |

**Score:** Class Model wins on safety and extensibility; Property Model wins on simplicity.

**Tie-breaker:** Future flexibility > initial simplicity for infrastructure systems.

---

## The Recommendation

### **Move to Class Model**

**Rationale:**

1. **Firmware vs. installable distinction is essential**
   - Your infrastructure has both router firmware and VM guest OS
   - These are fundamentally different (immutable vs. mutable)
   - Property model conflates them; class model distinguishes them

2. **OS reuse prevents costly duplication**
   - Property model: scale = copying cost scales with device count
   - Class model: scale = referencing cost is constant
   - Infrastructure grows; class model scales better

3. **Compile-time validation catches errors early**
   - Property model: "Does Prometheus run here?" = runtime check
   - Class model: "Does Prometheus run here?" = compile-time error
   - Safer, faster feedback loops

4. **Multi-OS and specialization are natural extensions**
   - Not needed today, but likely valuable tomorrow
   - Class model can support them without redesign
   - Property model would require major refactoring

---

## Implementation Approach

### Conservative: 5-Phase Migration

Do NOT flip overnight. Keep both models during transition:

1. **Phase 1 (Week 1-2):** Add `installation_model` field to property model
   - Classify existing OS definitions
   - Start thinking in terms of firmware vs. installable

2. **Phase 2 (Week 3-4):** Create OS class system
   - Define OS class, subclasses, instances
   - Compiler can load and validate OS instances
   - Objects still use property model (optional binding support added)

3. **Phase 3 (Week 5-6):** Parallel validation
   - Compiler validates both models simultaneously
   - Tools auto-convert property OS → binding reference
   - Migration checklist created

4. **Phase 4 (Week 7-8):** Property model deprecated
   - Validator warns on property-based OS
   - Bindings required for new objects
   - Existing objects converted

5. **Phase 5 (Week 9+):** Property model removed
   - Hard error on property-based OS
   - All objects use bindings
   - Cleanup complete

### Cost Estimate

- **Compiler changes:** ~1 week (capability derivation, binding validation)
- **Validator updates:** ~1 week (OS instance verification, conflict detection)
- **Migration tooling:** ~0.5 week (auto-converter)
- **OS instance catalog:** ~0.5 week (create instances for all current OS)
- **Documentation:** ~1 week (schema docs, migration guide, examples)
- **Testing:** ~1 week (validation rules, edge cases)

**Total:** ~5 weeks of engineering effort

**Risk:** Low (5-phase approach allows rollback at any phase)

---

## Decision Checklist

Before committing, confirm:

- [ ] Firmware vs. installable distinction is strategically important
- [ ] 5-phase migration is acceptable timeline
- [ ] Compiler refactoring effort is available
- [ ] OS instance catalog can be maintained
- [ ] Team understands class-based model
- [ ] Documentation plan is in place

---

## Three Possible Paths Forward

### Path A: Keep Property Model (Status Quo)
- **Do:** Continue ADR 0064 as-is
- **Risk:** Future needs (multi-OS, specialization) will require redesign
- **Timeline:** No effort now, high effort later

### Path B: Add Class Model alongside Property Model (Hybrid)
- **Do:** Both models coexist; users choose per object
- **Benefit:** Gradual migration, backward compatible
- **Risk:** Dual-mode complexity, eventual cleanup needed
- **Timeline:** ~5 weeks to implement both

### Path C: Redesign Property Model with Installation Model (Light Refactor)
- **Do:** Keep property-based, add `installation_model` field
- **Benefit:** Firmware vs. installable distinction without full class refactor
- **Risk:** Doesn't solve OS reuse, service validation, multi-OS
- **Timeline:** ~1 week to implement

---

## Recommended Decision Tree

**Q1: Is firmware-vs-installable distinction important to you?**
- YES → Continue below
- NO → Path C (light refactor sufficient)

**Q2: Do you expect > 10 devices per OS version?**
- YES → Path B or C (avoid duplication)
- NO → Path C (duplication acceptable at small scale)

**Q3: Will services/workloads have OS requirements?**
- YES → Path B (compile-time validation valuable)
- NO → Path C (simple property model sufficient)

**Q4: Do you anticipate multi-OS or OS specialization?**
- YES → Path B (extensibility matters)
- NO → Path C (simpler model acceptable)

**Scoring:** If you answer YES to 2+ questions → **Path B (Class Model)**

---

## Conclusion

**The class model is recommended because it provides:**

1. **Clarity:** Firmware OS and installable OS are structurally distinct
2. **Efficiency:** OS definitions are reused, not duplicated
3. **Safety:** Service-device compatibility validated at compile time
4. **Extensibility:** Future multi-OS and specialization supported
5. **Scalability:** Infrastructure growth doesn't increase maintenance burden

**The cost is modest** (5 weeks) and **the timeline is manageable** (5-phase migration with backward compatibility).

**Next action:** Review this analysis with team, confirm decision on Path A/B/C, then proceed with ADR update.

---

## Appendix: Document Map

Analysis documents created:

1. **os-modeling-approach-comparison.md**
   - Detailed comparison of property vs. class models
   - Advantages and disadvantages of each
   - Hybrid approach option
   - Decision framework

2. **os-modeling-scenarios.md**
   - Real-world examples: VMs, routers, services
   - Side-by-side comparison of both models
   - Multi-OS and specialization examples
   - Summary matrix

3. **adr-0064-revision-proposal.md**
   - Concrete proposal for evolving ADR 0064
   - OS class definition and instance structure
   - Device binding specifications
   - Compiler changes required
   - 5-phase migration plan
   - Implementation checklist

4. **os-model-redesign-executive-summary.md** (this document)
   - Quick overview
   - Decision points
   - Recommendation
   - Implementation approach
   - Next steps

---

## Questions to Resolve

Before finalizing, address:

1. **OS instance naming:** How to uniquely identify OS instances?
   - Option A: `obj.os.debian.12.generic`
   - Option B: `obj.os.debian-12-generic`
   - Option C: `os:debian:12:generic` (structured ID)

2. **Firmware binding:** How tightly should firmware OS be bound to hardware?
   - Option A: Router class defines default firmware, object can't override
   - Option B: Router class defines allowed firmware list, object chooses
   - Option C: No constraint (allows flexibility for testing)

3. **Backward compatibility window:** How long to maintain property model?
   - Option A: 3 months (aggressive migration)
   - Option B: 6 months (standard timeline)
   - Option C: 12 months (conservative approach)

4. **OS catalog maintenance:** Who maintains the OS instance registry?
   - Option A: Centralized (one person/team)
   - Option B: Distributed (each team maintains their OS variants)
   - Option C: Auto-generated (from provisioning system)

---

**Document created:** 2026-03-08  
**Status:** Ready for team review and decision  
**Author:** AI Assistant  
**Version:** 1.0
