# ADR 0064 Analysis: One-Page Executive Summary

**Date:** 2026-03-08  
**Project:** home-lab topology v5  
**Status:** Analysis Complete → Ready for Decision

---

## The Question

**How should we model Operating Systems in our topology?**

Two options:
1. **Property Model** (current): OS as structured property on devices
2. **Class Model** (proposed): OS as first-class entity with explicit bindings

---

## The Answer: Choose Class Model ✓

**Reason:** Your infrastructure has firmware devices (routers) AND installable devices (VMs). They're fundamentally different. Property model treats them the same; class model distinguishes them.

**Supporting factors:**
- 🔄 **Reuse**: No duplication across 20+ devices per OS variant
- 🛡️ **Safety**: Compile-time validation catches service-device mismatches
- 📦 **Extensibility**: Multi-OS devices and specialization (future-proof)
- 🏗️ **Clarity**: Firmware vs. installable distinction is explicit

---

## Quick Comparison

| Aspect | Property | Class |
|--------|----------|-------|
| **Firmware distinction** | ✗ Implicit | ✓ Explicit |
| **OS reuse** | ✗ Duplication | ✓ No duplication |
| **Validation** | ✗ Runtime | ✓ Compile-time |
| **Multi-OS support** | ✗ No | ✓ Yes |
| **Schema complexity** | ✓ Simple | ~ Moderate |
| **Maintenance burden** | ✗ High | ✓ Low |
| **Score** | 62/100 | **68/100** |

---

## The Path Forward: 5 Phases, 5-6 Weeks

```
Phase 1: Classification (1-2 wk)
├─ Add installation_model field to schema
├─ Classify existing OS definitions
└─ Validator enforces new field

Phase 2: Class System (2-3 wk)
├─ Create OS class and subclasses
├─ Create instances for all OS variants
├─ Compiler capability derivation
└─ Service-device compatibility checker

Phase 3: Parallel Validation (1-2 wk)
├─ Both models supported simultaneously
├─ Migration tooling (auto-convert property → binding)
└─ 50% of objects migrated

Phase 4: Deprecation (1 wk)
├─ Warn on property-based OS
├─ Bindings required for new objects
└─ Migrate remaining 50%

Phase 5: Cleanup (1 wk)
├─ Remove property model support
├─ Hard error on property-based OS
└─ Legacy code removed
```

**Risk:** LOW (reversible until Phase 4)  
**Effort:** ~70-90 hours (1-2 engineers)  
**Impact:** Zero breaking changes until Phase 4

---

## Three Paths Forward

### Path A: Keep Property Model (Status Quo)
- **Now:** No work
- **Later:** Will need redesign in 1-2 years when scale hits limits
- **Recommendation:** ✗ Not recommended

### Path B: Both Models (Hybrid)
- **Now:** 5-6 weeks to implement both
- **Later:** Maintain dual code paths indefinitely
- **Recommendation:** ~ Acceptable but suboptimal

### Path C: Full Class Model (Recommended)
- **Now:** 5-6 weeks implementation
- **Later:** Clean architecture, better maintainability
- **Recommendation:** ✓✓ Best choice

---

## Key Differences Explained

### Firmware-Based OS (e.g., RouterOS)
- Hardware-locked (specific router model only)
- Immutable (cannot change without vendor tools)
- Vendor-controlled release schedule
- Example: Mikrotik RB3011 + RouterOS 7.1

**Property model:** Treats like any OS (doesn't capture immutability)  
**Class model:** `os.firmware` subclass (explicit distinction)

### Installable OS (e.g., Debian)
- User-controlled (any compatible hardware)
- Mutable (can upgrade/downgrade versions)
- Independent release schedule
- Examples: Debian 12, Ubuntu 22.04, Alpine 3.19

**Property model:** Works but has duplication (20 VMs = 20 definitions)  
**Class model:** Single definition, all VMs reference it

---

## Validation Benefit Example

**Scenario:** Prometheus service needs Linux + systemd + apt

**Property model:**
- Developer configures VM as: `{family: routeros, ...}`
- Error discovered at DEPLOY TIME
- Cost: High (must fix infrastructure, restart deployment)

**Class model:**
- Developer tries to bind: `bindings.os: obj.os.routeros-7`
- Compiler checks: RouterOS lacks cap.os.apt
- Error reported at SCHEMA VALIDATION TIME
- Cost: Low (fix 1 line in config file)

---

## The Cost-Benefit Analysis

### Investment (One-time)
- **Engineering:** 70-90 hours
- **Timeline:** 6-8 weeks
- **Staffing:** 1-2 engineers

### Benefits (Recurring)
- **Maintenance:** Reuse prevents duplication (+years of benefit)
- **Reliability:** Early error detection prevents deploy failures
- **Scalability:** Scales well as device count grows
- **Extensibility:** Supports multi-OS and specialization without redesign

**ROI breakeven:** Occurs around 15-20 devices per OS variant (you'll have this within 1 year)

---

## What You Need to Do Now

### Step 1: Review (30 minutes)
- Read this one-pager
- Skim the decision matrix (shows specific scenarios)
- Discuss with team

### Step 2: Decide (5 minutes)
- **Recommend:** Path C (Class Model)
- **Vote:** Team consensus
- **Log:** Document decision

### Step 3: Plan (1 hour)
- Assign Phase 1 lead
- Reserve 1-2 engineers for 5 weeks
- Create Phase 1 user stories

### Step 4: Kickoff (Week of 2026-03-22)
- Start Phase 1: Add classification field to schema
- Target completion: Week of 2026-05-17 (Phase 5 cleanup)

---

## Where to Find Details

All analysis documents are in: `adr/0064-analysis/`

| Document | Read When | Duration |
|----------|-----------|----------|
| **README.md** | You want overview | 15 min |
| **Executive Summary** | You're decision maker | 10 min |
| **Decision Matrix** | You want scenarios | 20 min |
| **Comparison** | You want detailed pros/cons | 25 min |
| **Scenarios** | You want code examples | 30 min |
| **Proposal** | You're implementing | 40 min |
| **Next Steps** | You're planning execution | 20 min |
| **INDEX.md** | You need navigation | 5 min |

---

## Questions? Quick Answers

**Q: Will this break existing infrastructure?**  
A: No. Phase 3 runs both models in parallel. Phase 4 is when breaking changes start (with deprecation warnings first).

**Q: Can we pause or rollback?**  
A: Yes, easily through Phase 3. Phase 4-5 are harder to rollback but still possible.

**Q: What if we change our mind?**  
A: Phase 1-2 is easily reversible. Recommend committing after Phase 2 validation.

**Q: Why not just add a field to the property model?**  
A: We could (Phase 1 does this), but it doesn't solve OS reuse, multi-OS, or compile-time validation problems. Would just postpone the redesign.

**Q: Will team learn the new model?**  
A: Yes. Much easier than learning property model from scratch (it's just inheritance + bindings, patterns already used in v5).

---

## Recommendation Summary

### ✅ Adopt Class Model Because:

1. **Your infrastructure demands it**
   - Firmware routers + installable VMs = two fundamentally different OS types
   - Property model conflates them; class model distinguishes them

2. **It scales with your growth**
   - Small labs: property model fine
   - Your lab: ~20 devices per variant → class model pays for itself
   - Large labs: class model becomes essential

3. **It improves reliability**
   - Catch "Prometheus can't run here" at schema time, not deploy time
   - Automatic compatibility matrix generation
   - No more surprises at 2am during deployment

4. **It future-proofs the architecture**
   - Multi-OS devices (just add more bindings)
   - OS specialization (inheritance)
   - OS lifecycle management (independent)
   - All cost zero to add if you build the right foundation now

5. **It's affordable**
   - 70-90 hours engineering effort
   - Can be done in 5-6 weeks
   - Low risk with 5-phase rollout

---

## Next Action

**This week:** 
1. Share analysis with team
2. Schedule 30-minute architecture review
3. Vote on Path C adoption
4. Assign Phase 1 lead

**Week of 2026-03-15:**
1. Create ADR 0064 revision
2. Plan Phase 1 sprint
3. Begin implementation

**Expected completion:** Week of 2026-05-17

---

**Status:** Ready for team decision  
**Recommendation:** Proceed with class model (Path C)  
**Timeline:** 6-8 weeks to full implementation  
**Next milestone:** Architecture review meeting

For detailed analysis, see: `adr/0064-analysis/`
