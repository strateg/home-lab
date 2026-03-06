# Current State Gap Analysis

**Date:** 2026-03-06
**Focus:** Gaps between current repository state and ADR 0062 target architecture

---

## Executive Summary

This analysis identifies the gaps between the current home-lab repository state and the target v5 architecture defined in ADR 0062. The analysis covers directory structure, implemented components, and missing pieces.

**Overall Readiness:** ~5% complete

**Critical Blockers:** Phase 0 (dual-track workspace) not executed

---

## Directory Structure Analysis

### Target Structure (per ADR 0062)

```
home-lab/
├── v4/                          # Legacy lane (frozen)
│   ├── topology/
│   ├── topology-tools/
│   └── tests/
├── v5/                          # New lane (active)
│   ├── topology/
│   │   ├── class-modules/
│   │   ├── object-modules/
│   │   ├── instances/home-lab/
│   │   ├── model.lock.yaml
│   │   └── profile-map.yaml
│   ├── topology-tools/
│   └── tests/
├── v4-generated/
├── v4-build/
├── v4-dist/
├── v5-generated/
├── v5-build/
├── v5-dist/
└── adr/
```

### Current Structure

```
home-lab/
├── topology/                    # v4 topology (NOT in v4/ yet) ❌
│   ├── class-modules/          # v5 infrastructure (mixed) ⚠️
│   ├── object-modules/         # v5 infrastructure (mixed) ⚠️
│   ├── model.lock.yaml         # v5 infrastructure (mixed) ⚠️
│   └── L0-L7 layer files       # v4 data
├── topology-tools/              # v4 tools (NOT in v4/ yet) ❌
│   ├── migrate-to-v5.py        # v5 migration tool ⚠️
│   └── compile-topology.py     # v5 compiler ⚠️
├── tests/                       # v4 tests (NOT in v4/tests/ yet) ❌
├── generated/                   # v4 artifacts (NOT v4-generated/) ❌
├── build/                       # v4 artifacts (NOT v4-build/) ❌
├── dist/                        # v4 artifacts (NOT v4-dist/) ❌
└── adr/                         # ✅ Correct location
```

**Gap Summary:**
- ❌ No v4/ directory
- ❌ No v5/ directory
- ❌ Artifact roots not versioned (v4-*, v5-*)
- ⚠️ v5 infrastructure mixed with v4 data in topology/

**Impact:** **CRITICAL** - Phase 0 not executed, blocking all migration work

---

## Component Implementation Analysis

### 1. Class Modules

**Target:**
- Comprehensive class catalog for all entity types
- Capability packs defined
- Class contracts with invariants

**Current State:**

| Component | Expected Location | Actual Location | Status |
|-----------|-------------------|-----------------|--------|
| Class directory | `v5/topology/class-modules/` | `topology/class-modules/` | ⚠️ Wrong location |
| Class definitions | Multiple class files | `classes/network/class.network.router.yaml` | ⚠️ Only 1 class |
| Capability catalog | `capability-catalog.yaml` | `capability-catalog.example.yaml` | ⚠️ Example only |
| Capability packs | `capability-packs.yaml` | `capability-packs.example.yaml` | ⚠️ Example only |

**Existing Classes:**
1. ✅ `class.network.router` - Single example

**Missing Classes (estimated 15-20 needed):**
- ❌ `class.network.switch`
- ❌ `class.compute.hypervisor`
- ❌ `class.compute.sbc`
- ❌ `class.compute.vm`
- ❌ `class.compute.container`
- ❌ `class.os.linux`
- ❌ `class.os.windows`
- ❌ `class.service.*` (multiple)
- ❌ `class.storage.*`

**Gap:** ~95% of class modules not defined

---

### 2. Object Modules

**Target:**
- Object definitions for all concrete implementations
- Vendor-specific modules organized by namespace
- Capability bindings

**Current State:**

| Component | Expected Location | Actual Location | Status |
|-----------|-------------------|-----------------|--------|
| Object directory | `v5/topology/object-modules/` | `topology/object-modules/` | ⚠️ Wrong location |
| MikroTik objects | Multiple | 2 files (chateau, CHR) | ⚠️ Minimal |
| Other vendor objects | Multiple vendors | None | ❌ Missing |

**Existing Objects:**
1. ✅ `obj.mikrotik.chateau_lte7_ax`
2. ✅ `obj.mikrotik.chr`

**Missing Objects (estimated 15-25 needed):**
- ❌ Proxmox (hypervisor, LXC, QEMU)
- ❌ Linux distributions (Debian, Ubuntu, Alpine, etc.)
- ❌ Service implementations (Nextcloud, Jellyfin, Prometheus, etc.)
- ❌ Storage implementations

**Gap:** ~90% of object modules not defined

---

### 3. Instance Topology Data

**Target:**
- v5 instance data with `class_ref` and `object_ref`
- No legacy-only fields in new files
- Located in `v5/topology/instances/home-lab/`

**Current State:**

| Component | Expected Location | Actual Location | Status |
|-----------|-------------------|-----------------|--------|
| Instance data | `v5/topology/instances/home-lab/` | `topology/L0-L7.yaml` | ❌ Wrong location, v4 format |
| class_ref usage | All entities | None | ❌ No v5 refs |
| object_ref usage | All entities | None | ❌ No v5 refs |

**Current Format:**
```yaml
# topology/L1-foundation.yaml (v4 format)
devices:
  - id: rtr-mikrotik-chateau
    type: router              # Legacy field
    model: Chateau LTE7 ax    # Legacy field
    # Missing: class_ref, object_ref
```

**Target Format:**
```yaml
# v5/topology/instances/home-lab/L1-foundation.yaml
devices:
  - id: rtr-mikrotik-chateau
    class_ref: class.network.router
    object_ref: obj.mikrotik.chateau_lte7_ax
    # type, model now derived from class/object
```

**Gap:** 0% of instance data migrated to v5 format

---

### 4. Compilation Infrastructure

**Target:**
- 5-stage compiler (load → normalize → resolve → validate → emit)
- Diagnostics envelope with JSON + text output
- Error catalog integration

**Current State:**

| Component | Expected Location | Actual Location | Status |
|-----------|-------------------|-----------------|--------|
| Compiler | `v5/topology-tools/compile-topology.py` | `topology-tools/compile-topology.py` | ⚠️ Exists, wrong location |
| Diagnostics schema | `topology-tools/schemas/diagnostics.schema.json` | Same | ✅ Exists |
| Error catalog | `topology-tools/data/error-catalog.yaml` | Same | ✅ Exists |
| Model lock schema | `topology-tools/schemas/model-lock.schema.json` | Same | ✅ Exists |
| Profile map schema | `topology-tools/schemas/profile-map.schema.json` | Same | ✅ Exists |

**Compiler Implementation Status:**

Need to verify implementation:
- ❓ Are all 5 stages implemented?
- ❓ Does it support class/object resolution?
- ❓ Does it emit diagnostics per schema?
- ❓ Does it handle profiles?

**Gap:** Infrastructure exists but operational status unknown

---

### 5. Validation Infrastructure

**Target:**
- Schema validation for class/object/instance
- Link validation (instance → object → class)
- Inheritance validation (merge + invariants)
- Layer validation (L0-L7 directional contracts)
- Capability contract validation

**Current State:**

| Component | Expected Location | Status |
|-----------|-------------------|--------|
| Capability checker | `topology-tools/check-capability-contract.py` | ✅ Exists |
| Legacy validators | `scripts/validators/` | ✅ Exist (v4 focused) |
| v5 validators | `v5/topology-tools/validators/` | ❌ Not created |

**Existing Validators (v4):**
- ✅ Foundation checks
- ✅ Reference checks
- ✅ Network checks
- ✅ Storage checks

**Missing Validators (v5):**
- ❌ Class-object-instance link validator
- ❌ Merge precedence validator
- ❌ Invariant protection validator
- ❌ Capability signature validator (beyond basic checks)

**Gap:** v4 validators exist, v5-specific validators missing

---

### 6. Model Governance

**Target:**
- Operational `model.lock.yaml` with all pins
- Profile maps with production/modeled/test-real
- CI enforcement of strict mode

**Current State:**

| Component | Expected Location | Actual Location | Status |
|-----------|-------------------|-----------------|--------|
| model.lock | `v5/topology/model.lock.yaml` | `topology/model.lock.example.yaml` | ⚠️ Example only |
| profile-map | `v5/topology/profile-map.yaml` | `topology/profile-map.example.yaml` | ⚠️ Example only |
| CI enforcement | GitHub Actions | N/A | ❌ Not implemented |

**model.lock.yaml Status:**
- Has schema ✅
- Has example ✅
- No operational file ❌
- Not enforced in CI ❌

**profile-map.yaml Status:**
- Has schema ✅
- Has example ✅
- No operational file ❌
- No profile compilation ❌

**Gap:** Governance contracts defined but not operational

---

### 7. Migration Tooling

**Target:**
- Migration script that adds class_ref/object_ref
- Validation against class/object modules
- Integration with Phase 1 mapping table

**Current State:**

| Component | Expected Location | Actual Location | Status |
|-----------|-------------------|-----------------|--------|
| Migration script | `v5/topology-tools/migrate-to-v5.py` | `topology-tools/migrate-to-v5.py` | ⚠️ Partial, wrong location |
| Inventory script | `v5/topology-tools/inventory-v4.py` | N/A | ❌ Not created |
| Mapping table | `v5/topology/instances/home-lab/v4-to-v5-mapping.yaml` | N/A | ❌ Not created |

**migrate-to-v5.py Current Capabilities:**
- ✅ L3 storage → storage_endpoints
- ✅ L4 inline resources → resource_profiles
- ✅ L4 LXC ansible.vars → L5 service config
- ✅ L5 external_services → services with docker runtime
- ❌ Does NOT add class_ref/object_ref
- ❌ Does NOT validate against modules

**Gap:** Migration script exists but incomplete for Phase 4

---

### 8. Generator Infrastructure

**Target:**
- Generators read from canonical JSON (not YAML)
- v4 and v5 generators operate independently
- Plugin architecture for v5 generators (Phase 7)

**Current State:**

| Component | Expected Location | Status |
|-----------|-------------------|--------|
| v4 generators | `v4/scripts/generators/` | ❌ Still at `scripts/generators/` |
| v5 generators | `v5/topology-tools/generators/` | ❌ Not created |
| Generator base classes | Both v4 and v5 | ✅ Exist in `scripts/generators/common/` |

**Existing Generators (v4):**
- ✅ Terraform (MikroTik, Proxmox)
- ✅ Ansible inventory
- ✅ Bootstrap scripts
- ✅ Documentation
- ✅ Diagrams

**v5 Generator Status:**
- ❌ No v5-specific generators yet
- ❌ Generators still read YAML not JSON
- ❌ No plugin infrastructure

**Gap:** v4 generators exist, v5 generators not started

---

### 9. Test Infrastructure

**Target:**
- Separate v4/tests/ and v5/tests/
- v5 tests cover class/object/instance contracts
- Test profiles (production/modeled/test-real)

**Current State:**

| Component | Expected Location | Actual Location | Status |
|-----------|-------------------|-----------------|--------|
| v4 tests | `v4/tests/` | `tests/` | ❌ Wrong location |
| v5 tests | `v5/tests/` | N/A | ❌ Not created |

**Existing Tests:**
- ✅ Unit tests for validators
- ✅ Unit tests for generators
- ✅ Integration tests for topology loading

**Missing Tests (v5):**
- ❌ Class module validation tests
- ❌ Object module validation tests
- ❌ Link resolution tests
- ❌ Merge precedence tests
- ❌ Profile substitution tests

**Gap:** v4 tests exist, v5 tests not started

---

### 10. CI/CD Infrastructure

**Target:**
- Dual-lane CI (v4 and v5 run separately)
- Path guards (PRs target correct lane)
- Artifact validation (outputs go to v4-* or v5-*)
- Model lock enforcement
- Profile matrix testing

**Current State:**

| Component | Status |
|-----------|--------|
| Dual-lane CI | ❌ Not implemented |
| Path guards | ❌ Not implemented |
| Artifact validation | ❌ Not implemented |
| Model lock check | ❌ Not implemented |
| Profile matrix | ❌ Not implemented |

**Existing CI (v4):**
- ✅ Validation runs
- ✅ Generator runs
- ✅ Test runs

**Gap:** No v5 CI infrastructure

---

### 11. Documentation

**Target:**
- Migration guide for developers
- v5 topology authoring guide
- Class/object module authoring guide
- Plugin development guide (Phase 7)

**Current State:**

| Document | Expected Location | Status |
|----------|-------------------|--------|
| ADR 0062 | `adr/0062-*.md` | ✅ Exists |
| Migration guide | `docs/migration-v4-to-v5.md` | ❌ Not created |
| v5 authoring guide | `v5/topology/GUIDE.md` | ❌ Not created |
| Class module guide | `v5/topology/class-modules/GUIDE.md` | ⚠️ README exists |
| Object module guide | `v5/topology/object-modules/GUIDE.md` | ⚠️ README exists |
| Plugin guide | `v5/topology-tools/PLUGIN-GUIDE.md` | ❌ Not created |

**Existing Documentation:**
- ✅ ADR 0062 (comprehensive)
- ✅ Class/object README files (minimal)
- ✅ Modular guide (`topology/MODULAR-GUIDE.md` - v4 focused)

**Gap:** v5-specific documentation minimal

---

## Gap Priority Matrix

### Critical (Blocking)

| Gap | Impact | Phase |
|-----|--------|-------|
| No v4/ directory | Blocks all migration | Phase 0 |
| No v5/ directory | Blocks all migration | Phase 0 |
| Artifact roots not versioned | Blocks dual-track | Phase 0 |
| No class definitions | Blocks Phase 2-8 | Phase 2 |
| No object definitions | Blocks Phase 3-8 | Phase 3 |
| No v5 instance data | Blocks Phase 4-8 | Phase 4 |

### High (Required)

| Gap | Impact | Phase |
|-----|--------|-------|
| No inventory script | Slows Phase 1 | Phase 1 |
| Migration script incomplete | Blocks Phase 4 | Phase 4 |
| No operational model.lock | Blocks Phase 5 | Phase 5 |
| No operational profiles | Blocks Phase 5 | Phase 5 |
| No v5 generators | Blocks Phase 6 | Phase 6 |
| No plugin infrastructure | Blocks Phase 7 | Phase 7 |

### Medium (Important)

| Gap | Impact | Phase |
|-----|--------|-------|
| Compiler status unknown | Uncertainty in Phase 4-8 | Phase 4 |
| No v5 validators | Reduces validation quality | Phase 6 |
| No v5 tests | Reduces confidence | All |
| No dual-lane CI | Increases manual overhead | Phase 0 |

### Low (Nice to have)

| Gap | Impact | Phase |
|-----|--------|-------|
| Documentation minimal | Slows onboarding | All |
| No parity tooling | Slows Phase 6 | Phase 6 |

---

## Component Completeness Matrix

| Component | Designed | Implemented | Tested | Operational |
|-----------|----------|-------------|--------|-------------|
| **Architecture** |
| Class-Object-Instance model | ✅ | ❌ | ❌ | ❌ |
| Capability model | ✅ | ⚠️ | ❌ | ❌ |
| Compilation pipeline | ✅ | ❓ | ❌ | ❌ |
| Diagnostics | ✅ | ❓ | ❌ | ❌ |
| **Data** |
| Class modules | ✅ | 5% | ❌ | ❌ |
| Object modules | ✅ | 10% | ❌ | ❌ |
| Instance topology | ✅ | 0% | ❌ | ❌ |
| Model lock | ✅ | 0% | ❌ | ❌ |
| Profiles | ✅ | 0% | ❌ | ❌ |
| **Infrastructure** |
| Workspace split | ✅ | 0% | ❌ | ❌ |
| Compiler | ✅ | ❓ | ❌ | ❌ |
| Validators | ✅ | 30% | ⚠️ | ⚠️ (v4 only) |
| Generators | ✅ | 0% (v5) | ❌ | ❌ |
| Plugin system | ✅ (ADR 0063) | 0% | ❌ | ❌ |
| **Governance** |
| Migration script | ✅ | 50% | ⚠️ | ❌ |
| CI dual-lane | ✅ | 0% | ❌ | ❌ |
| Path guards | ✅ | 0% | ❌ | ❌ |
| Lock enforcement | ✅ | 0% | ❌ | ❌ |

**Overall Completeness: ~5%**

---

## Risk Assessment by Gap

### High-Risk Gaps

1. **Phase 0 not executed (CRITICAL)**
   - **Risk:** All downstream work blocked
   - **Probability:** 100% (it's a fact)
   - **Impact:** Project cannot progress
   - **Mitigation:** Execute Phase 0 immediately

2. **Compiler implementation status unknown**
   - **Risk:** May need significant rework
   - **Probability:** 50%
   - **Impact:** Delays Phase 4-8
   - **Mitigation:** Audit compiler implementation

3. **No class/object modules**
   - **Risk:** Long critical path
   - **Probability:** 100%
   - **Impact:** 4-6 weeks of work
   - **Mitigation:** Parallelization, prioritization

### Medium-Risk Gaps

4. **Migration script incomplete**
   - **Risk:** Phase 4 delays
   - **Probability:** 80%
   - **Impact:** 1-2 weeks rework
   - **Mitigation:** Enhance script early

5. **No v5 generators**
   - **Risk:** Phase 6 blocked
   - **Probability:** 100%
   - **Impact:** 2-3 weeks work
   - **Mitigation:** Reuse v4 generator patterns

### Low-Risk Gaps

6. **Documentation minimal**
   - **Risk:** Slower onboarding
   - **Probability:** 100%
   - **Impact:** Inefficiency, confusion
   - **Mitigation:** Incremental documentation

---

## Immediate Actions Required

### Week 1: Foundation

1. ✅ **Execute Phase 0** (2-3 days)
   - Create v4/ and v5/ directories
   - Rename artifact roots
   - Update all script paths
   - Update CI

2. ✅ **Audit compiler implementation** (1 day)
   - Verify 5-stage implementation
   - Test diagnostics output
   - Identify gaps

### Week 2-3: Inventory and Planning

3. ✅ **Create inventory automation** (2-3 days)
   - Script to scan v4 topology
   - Generate mapping table
   - Identify gaps

4. ✅ **Start capability catalog** (2-3 days)
   - Extract from v4 topology
   - Define capability IDs
   - Group into packs

### Week 4-8: Core Implementation

5. ✅ **Define class modules** (15-20 days, can parallelize)
6. ✅ **Define object modules** (10-15 days, can parallelize)
7. ✅ **Enhance migration script** (2-3 days)

---

## Conclusion

**Current State:** ~5% complete relative to ADR 0062 target

**Critical Blocker:** Phase 0 not executed

**Key Gaps:**
- ❌ Workspace structure (v4/, v5/)
- ❌ Class modules (~95% missing)
- ❌ Object modules (~90% missing)
- ❌ v5 instance data (100% missing)
- ❌ Operational model governance (lock, profiles)

**Positive Notes:**
- ✅ ADR 0062 provides clear target
- ✅ Some infrastructure exists (schemas, examples)
- ✅ Migration script started
- ✅ v4 system is stable baseline

**Recommendation:** Execute Phase 0 immediately to unblock the migration.
