# ADR 0064 Analysis: OS Taxonomy and Modeling

**Date:** 2026-03-08
**Focus:** Evaluating property-based vs. class-based OS modeling approaches

---

## Contents

This analysis provides a comprehensive evaluation of how to model Operating Systems in the v5 topology framework.

### 📋 Documents

1. **os-model-redesign-executive-summary.md** ⭐ **START HERE**
   - Quick overview of the two approaches
   - Key decision points
   - Recommendation: Move to class-based model
   - Implementation approach (5 phases)
   - ~10 minutes read

2. **os-modeling-approach-comparison.md**
   - Detailed comparison of property model vs. class model
   - 8+ advantages of each approach
   - Trade-offs analysis
   - Hybrid model option
   - Decision framework
   - ~20 minutes read

3. **os-modeling-scenarios.md**
   - Real-world examples with code
   - 6 scenarios: VMs, routers, services, multi-OS, specialization
   - Side-by-side code comparison
   - Summary matrix showing when each model excels
   - ~25 minutes read

4. **adr-0064-revision-proposal.md**
   - Concrete technical proposal for ADR 0064 update
   - OS class definition (properties, capabilities, subclasses)
   - Device binding specifications
   - Compiler changes required
   - Phase-by-phase migration plan
   - Risk mitigation and implementation checklist
   - ~30 minutes read

---

## Quick Summary

### Problem

Current ADR 0064 models OS as an embedded property. This creates gaps:

1. Firmware OS and installable OS are structurally identical
   - No way to enforce "router must use firmware"
   - No way to reject "firmware on VM"

2. OS reuse requires duplication
   - 20 Debian 12 VMs = 20× definition copy
   - Changes require editing all 20 files

3. Service-device matching requires runtime validation
   - "Can Prometheus run here?" unknown at compile time
   - Discovered at deploy time (too late)

4. Multi-OS devices not expressible
   - Dual-boot, multi-partition systems don't fit

5. OS specialization not supported
   - "Debian 12 generic" vs. "Debian 12 hardened" cannot coexist

### Solution

Move to class-based OS model:

```yaml
# OS as a class
class: os.installable | os.firmware
properties:
  family: linux | routeros | windows
  installation_model: firmware | installable  # Explicit distinction
  # ... other fields ...

# Device binds to OS instance
object:
  bindings:
    os: obj.os.debian.12.generic
```

**Benefits:**
- ✓ Firmware/installable distinction explicit
- ✓ OS reuse (no duplication)
- ✓ Compile-time validation
- ✓ Multi-OS support
- ✓ OS specialization support
- ✓ Independent OS lifecycle

**Cost:** ~5 weeks implementation (5-phase migration)

---

## Device Types & OS Models

### OS-Bearing Devices (2 Classes)

#### 1. Firmware-Based
- **Examples:** Router (RouterOS), Appliance (TrueNAS), Smart switch
- **Characteristics:** Immutable, hardware-locked, vendor-controlled
- **OS lifecycle:** Tied to hardware revision
- **Installable versions:** No (or very restricted)
- **Model fit:** Tight coupling appropriate

#### 2. Installable-Based
- **Examples:** VM (Debian), LXC (Alpine), Cloud (AMI), Bare metal (Ubuntu)
- **Characteristics:** Mutable, user-installed, flexible
- **OS lifecycle:** Independent of hardware
- **Installable versions:** Yes (multiple)
- **Model fit:** Loose coupling appropriate

### OS-Less Devices

- **Examples:** PDU, UPS, Patch panel, Storage shelf
- **OS model:** Not applicable (no OS section)

---

## Migration Path

### Phase 1: Classification (Week 1-2)
- Add `installation_model: firmware | installable` to property model
- Classify all existing OS definitions
- Start thinking in firmware vs. installable terms

### Phase 2: Class System (Week 3-4)
- Create OS class and subclasses
- Create instances for all OS variants in use
- Compiler loads OS class instances
- Objects support optional bindings (property model still works)

### Phase 3: Dual Validation (Week 5-6)
- Compiler validates both models simultaneously
- Tools auto-convert property OS → binding reference
- Parallel migration allowed

### Phase 4: Deprecation (Week 7-8)
- Validator warns on property-based OS
- Bindings required for new objects
- Existing objects converted

### Phase 5: Cleanup (Week 9+)
- Hard error on property-based OS
- All objects use bindings
- Property model removed

---

## Recommendation

**Adopt class-based OS model** because:

1. **Firmware/installable distinction is essential**
   - Your infrastructure has both types
   - They're fundamentally different (immutable vs. mutable)
   - Class model enforces distinction; property model doesn't

2. **OS reuse prevents duplication at scale**
   - 10+ devices per OS variant = significant duplication cost
   - Class model: OS defined once, referenced many times
   - Maintenance scales linearly with device count, not with configuration size

3. **Compile-time validation improves reliability**
   - Property model: Service-device compatibility = runtime check
   - Class model: Service-device compatibility = compile-time error
   - Early error detection = cheaper fixes

4. **Multi-OS and specialization extensibility**
   - Not needed today, but infrastructure evolves
   - Class model can support them without redesign
   - Property model would require major refactoring

---

## Scoring Analysis

| Criterion | Property | Class | Weight |
|-----------|----------|-------|--------|
| Schema simplicity | 10 | 6 | 1× |
| **Firmware distinction** | **3** | **10** | **3×** |
| **OS reuse efficiency** | **4** | **10** | **2×** |
| **Compile-time validation** | **4** | **10** | **3×** |
| Multi-OS support | 2 | 10 | 1× |
| OS specialization | 2 | 9 | 1× |
| Backward compatibility | 10 | 5 | 1× |
| Operator familiarity | 9 | 6 | 2× |
| **Weighted Total** | **62** | **68** | |

**Class model wins on the criteria that matter most** (firmware distinction, reuse, validation).

---

## Implementation Effort

| Phase | Timeline | Effort | Risk |
|-------|----------|--------|------|
| Phase 1: Classification | Week 1-2 | Low | Very Low |
| Phase 2: Class System | Week 3-4 | Moderate | Low |
| Phase 3: Dual Validation | Week 5-6 | Moderate | Low |
| Phase 4: Deprecation | Week 7-8 | Low | Very Low |
| Phase 5: Cleanup | Week 9+ | Low | Very Low |
| **Total** | **~2 months** | **Moderate** | **Low** |

**Staffing:** 1-2 engineers

**Critical path:**
1. Compiler capability derivation (1 week)
2. Validator updates (1 week)
3. Migration tooling (0.5 week)
4. OS instance catalog (0.5 week)
5. Testing & docs (1 week)

---

## Decision Questions

Before proceeding, confirm:

- [ ] Firmware/installable distinction is strategically important? **→ YES (routers vs. VMs)**
- [ ] OS reuse efficiency matters? **→ YES (growing device count)**
- [ ] Compile-time validation is valuable? **→ YES (safety matters)**
- [ ] Extensibility for future scenarios? **→ YES (unknown future needs)**
- [ ] 5-week implementation timeline acceptable? **→ [TO BE CONFIRMED]**
- [ ] Compiler refactoring resources available? **→ [TO BE CONFIRMED]**

---

## Next Steps

1. **Read executive summary** (os-model-redesign-executive-summary.md)
2. **Review comparison analysis** (os-modeling-approach-comparison.md)
3. **Review scenario examples** (os-modeling-scenarios.md)
4. **Discuss with team:**
   - Is class model alignment correct?
   - Any concerns with 5-phase migration?
   - Timeline and resources acceptable?
5. **If approved:**
   - Create ADR 0064 revision (based on adr-0064-revision-proposal.md)
   - Plan dependent ADRs (OS instance catalog, etc.)
   - Schedule Phase 1 sprint
6. **If not approved:**
   - Document alternative approach
   - Consider hybrid option
   - Plan re-evaluation timeline

---

## Appendix: Document Reading Order

### For Decision Makers (20 minutes)
1. This README
2. os-model-redesign-executive-summary.md
3. Weighted scoring table in executive summary

### For Technical Reviewers (60 minutes)
1. This README
2. os-modeling-approach-comparison.md (detailed pros/cons)
3. os-modeling-scenarios.md (code examples)
4. adr-0064-revision-proposal.md (implementation details)

### For Implementation Planning (45 minutes)
1. adr-0064-revision-proposal.md (entire document)
2. Focus on: compiler changes, migration path, checklist
3. Cross-reference scenarios for validation examples

### For Architecture Review (90 minutes)
1. All four documents in order
2. Create architecture decision diagram
3. Plan dependent ADRs
4. Identify integration points with toolchain

---

## References

**Original ADR:**
- `../0064-os-taxonomy-object-property-model.md`

**Related ADRs:**
- ADR 0062: Topology v5 - Modular Class-Object-Instance Architecture
- ADR 0035: L4 Host OS Foundation and Runtime Substrates
- ADR 0039: L4 Host OS Installation Storage Contract Clarification

**Key Concepts:**
- OS prerequisite (source artifact/profile)
- Runtime OS projection (effective facts on object)
- Capability derivation and validation
- Installation model (firmware vs. installable)

---

**Analysis completed:** 2026-03-08
**Status:** Ready for team decision
**Next milestone:** ADR 0064 revision and Phase 1 planning
