# Migration Plan Assessment (Phases 0-8)

**Date:** 2026-03-06
**Focus:** Detailed assessment of the 8-phase v4 to v5 migration plan

---

## Migration Plan Overview

ADR 0062 defines an 8-phase migration plan with clear objectives and exit criteria for each phase. This analysis assesses each phase's completeness, dependencies, and implementation readiness.

---

## Phase Assessment Summary

| Phase | Status | Completeness | Blocking Issues | Est. Effort |
|-------|--------|--------------|-----------------|-------------|
| Phase 0 | ❌ Not Started | ✅ 100% | None | 2-3 days |
| Phase 1 | ❌ Blocked | ✅ 90% | Phase 0 | 1-2 weeks |
| Phase 2 | ❌ Blocked | ⚠️ 70% | Phase 1 | 2-3 weeks |
| Phase 3 | ❌ Blocked | ⚠️ 70% | Phase 2 | 2-3 weeks |
| Phase 4 | ⚠️ Partial | ⚠️ 60% | Phase 3 | 1-2 weeks |
| Phase 5 | ❌ Blocked | ⚠️ 50% | Phase 4 | 1 week |
| Phase 6 | ❌ Blocked | ⚠️ 40% | Phase 5 | 2-4 weeks |
| Phase 7 | ❌ Blocked | ⚠️ 30% | Phase 6, ADR 0063 | 3-4 weeks |
| Phase 8 | ❌ Blocked | ⚠️ 50% | Phase 7 | 2 weeks |

**Overall Completion:** ~5% (only Phase 0 prep work and partial Phase 4 migration script)

**Critical Path:** Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4

**Total Estimated Duration:** 14-21 weeks (3.5-5 months) if executed sequentially

---

## Phase 0: Freeze and Workspace Split

### Objective
Freeze legacy v4 for net-new feature work and create explicit dual-track structure.

### Actions Defined

1. ✅ **Move operational tree into v4/**
   - `topology` → `v4/topology/`
   - `topology-tools` → `v4/topology-tools/`

2. ✅ **Move v4 tests**
   - Current tests → `v4/tests/`

3. ✅ **Rename artifact roots**
   - `generated/` → `v4-generated/`
   - `build/` → `v4-build/`
   - `dist/` → `v4-dist/`

4. ✅ **Scaffold v5 roots**
   - `v5/topology/`
   - `v5/topology-tools/`
   - `v5/tests/`

5. ✅ **Scaffold v5 artifact roots**
   - `v5-generated/`
   - `v5-build/`
   - `v5-dist/`

6. ✅ **Update v4 script output paths**
   - All v4 scripts must write to `v4-*` roots

7. ✅ **Mark v4 as frozen in docs and CI**

8. ✅ **Add lane-specific commands**
   - `validate-v4`, `validate-v5`
   - `build-v4`, `build-v5`

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| Every PR targets either v4 or v5 | ✅ Yes (CI path check) | Low |
| No v5 features in v4 paths | ✅ Yes (policy + review) | Medium |
| No new tests outside v4/tests or v5/tests | ✅ Yes (CI path check) | Low |
| No pipelines write to unversioned roots | ✅ Yes (CI output check) | Low |

### Current State
- ❌ **v4/ directory does not exist**
- ❌ **v5/ directory does not exist**
- ❌ **Artifact roots not renamed**
- ✅ Current topology structure at root level

### Implementation Readiness: ✅ 100%

**Ready to execute immediately.** All actions are clear and mechanical.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Break existing scripts/CI | High | High | Test in branch, update all paths systematically |
| Incomplete path updates | Medium | High | Automated grep/sed, then manual verification |
| Confusion about which lane to use | Low | Medium | Clear documentation, PR template |

### Effort Estimate

- **File moves:** 2-4 hours
- **Path updates:** 4-8 hours
- **CI updates:** 2-4 hours
- **Documentation:** 2-4 hours
- **Testing:** 4-8 hours

**Total:** 2-3 days

### Recommended Approach

1. **Create branch:** `feat/phase-0-dual-track`
2. **Execute moves:**
   ```bash
   mkdir v4
   git mv topology v4/
   git mv topology-tools v4/
   git mv tests v4/tests  # if tests/ exists
   git mv generated v4-generated
   git mv build v4-build
   git mv dist v4-dist  # if exists
   ```
3. **Scaffold v5:**
   ```bash
   mkdir -p v5/topology/{class-modules,object-modules,instances/home-lab}
   mkdir -p v5/topology-tools
   mkdir -p v5/tests
   mkdir -p v5-generated v5-build v5-dist
   ```
4. **Update all script paths** (grep for `topology/`, `generated/`, etc.)
5. **Test:** Run existing generators, ensure output goes to v4-* roots
6. **Update CI** (GitHub Actions, pre-commit, etc.)
7. **Merge** to main after verification

### Dependencies
**None** - This is the foundation phase.

---

## Phase 1: Inventory and Mapping

### Objective
Map all active v4 entities to target v5 class/object bindings.

### Actions Defined

1. ⚠️ **Build v4-to-v5 mapping table**
   - Entities: L1 devices, L4 workloads (LXC/VMs), L5 services
   - Target: Class and Object assignments

2. ⚠️ **Classify unresolved entities**
   - Identify entities without clear class/object mapping
   - Document capability gaps

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| 100% active entities have planned class_ref/object_ref | ✅ Yes (checklist) | Medium |

### Current State
- ❌ No inventory script exists
- ❌ No mapping table exists
- ✅ Some class modules started (`class.network.router.yaml`)
- ✅ Some object modules started (`obj.mikrotik.*.yaml`)

### Implementation Readiness: ⚠️ 90%

**Mostly ready.** Need to create inventory automation.

### Missing Details

1. **Inventory script format**
   - CSV? YAML? Markdown table?
   - Recommend: YAML for machine-readability

2. **Mapping validation**
   - How to verify mapping completeness?
   - Recommend: Script to check all v4 entities have v5 targets

3. **Capability gap handling**
   - What if class doesn't exist for entity type?
   - What if object doesn't support required capability?

### Recommended Approach

**Create inventory automation:**

```python
# v5/topology-tools/inventory-v4.py
# Scans v4/topology/ and generates:
#   - v5/topology/instances/home-lab/v4-to-v5-mapping.yaml
#   - v5/topology/instances/home-lab/unresolved-entities.yaml
#   - v5/topology/instances/home-lab/capability-gaps.yaml
```

**Mapping table format:**

```yaml
# v4-to-v5-mapping.yaml
entities:
  - v4_layer: L1_foundation
    v4_id: rtr-mikrotik-chateau
    v4_type: router
    v4_model: Chateau LTE7 ax
    v5_class_ref: class.network.router
    v5_object_ref: obj.mikrotik.chateau_lte7_ax
    status: ready
    notes: ""

  - v4_layer: L4_platform
    v4_id: lxc-nextcloud
    v4_type: lxc
    v4_platform_type: lxc-unprivileged
    v5_class_ref: class.compute.container
    v5_object_ref: obj.proxmox.lxc
    status: unresolved
    notes: "Need class.compute.container definition"
```

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Incomplete inventory | Medium | High | Automated extraction + manual review |
| Class/object naming inconsistency | Medium | Medium | Naming convention document |
| Capability gaps discovered late | Medium | High | Early capability audit |

### Effort Estimate

- **Inventory script:** 1-2 days
- **Manual entity classification:** 3-5 days
- **Capability gap analysis:** 2-3 days
- **Documentation:** 1-2 days

**Total:** 1-2 weeks

### Dependencies
- **Blocks on:** Phase 0 (need v5/ structure)
- **Blocks:** Phase 2 (need mapping to know which classes to create)

---

## Phase 2: Class Module Coverage

### Objective
Create/complete class modules required by mapped entities.

### Actions Defined

1. ⚠️ **Define class contracts**
   - Capability semantics
   - Capability packs
   - Invariants

2. ⚠️ **Enforce capability checker coverage**
   - All classes must pass capability contract validation

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| All mapped object targets reference existing class modules | ✅ Yes (validation script) | Low |

### Current State
- ✅ Class module directory exists (`topology/class-modules/`)
- ✅ One example class: `class.network.router.yaml`
- ❌ Most classes not defined yet
- ⚠️ Capability checker exists (`check-capability-contract.py`)

### Implementation Readiness: ⚠️ 70%

**Mostly ready.** Need to scale from 1 class to ~10-20 classes.

### Missing Details

1. **Complete class catalog**
   - What classes are needed for home-lab?
   - Estimate: 10-20 classes across L1/L4/L5

2. **Capability catalog population**
   - Example exists, but operational catalog empty
   - Need ~50-100 capabilities defined

3. **Class validation rules**
   - Beyond capability checks, what else?
   - Invariants? Constraints?

### Recommended Class List (Preliminary)

**L1 Foundation:**
- `class.network.router`
- `class.network.switch`
- `class.compute.hypervisor`
- `class.compute.sbc` (single-board computer)
- `class.storage.nas`

**L4 Platform:**
- `class.compute.vm`
- `class.compute.container` (LXC)
- `class.os.linux`
- `class.os.windows`

**L5 Application:**
- `class.service.web`
- `class.service.database`
- `class.service.monitoring`
- `class.service.storage`

**Total:** ~15-20 classes

### Recommended Approach

1. **Populate capability catalog**
   - Extract from existing topology
   - Group into packs
   - Document semantics

2. **Create class modules systematically**
   - Start with L1 (foundation)
   - Then L4 (platform)
   - Then L5 (application)

3. **Validate each class**
   - Run capability checker
   - Document invariants
   - Review with team

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-complicated class hierarchy | Medium | Medium | Keep flat, avoid inheritance |
| Capability explosion | Medium | High | Use packs, strict promotion rules |
| Class-object impedance mismatch | Low | High | Iterate with object definitions |

### Effort Estimate

- **Capability catalog:** 3-5 days
- **Class definitions:** 1-2 days per class × 15 classes = 15-30 days
- **Validation and iteration:** 3-5 days

**Total:** 2-3 weeks (if done in parallel) or 4-6 weeks (if sequential)

### Dependencies
- **Blocks on:** Phase 1 (need mapping to know which classes)
- **Blocks:** Phase 3 (objects need classes to reference)

---

## Phase 3: Object Module Coverage

### Objective
Create/complete object modules for all mapped implementations.

### Actions Defined

1. ⚠️ **Define object contracts**
   - Implementation details
   - Supported capabilities
   - Initialization model

2. ⚠️ **Validate class/object compatibility**
   - Object satisfies class requirements
   - Capability signature matches

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| All mapped instance targets resolve to valid objects | ✅ Yes (validation script) | Low |

### Current State
- ✅ Object module directory exists (`topology/object-modules/`)
- ✅ Two MikroTik objects defined
- ❌ Most objects not defined yet

### Implementation Readiness: ⚠️ 70%

**Mostly ready.** Need to scale from 2 objects to ~15-25 objects.

### Missing Details

1. **Complete object catalog**
   - What objects needed for home-lab inventory?
   - Estimate: 15-25 objects

2. **Object validation beyond capability**
   - Configuration schema validation?
   - Template compatibility checks?

3. **Generator hooks**
   - How do objects specify generator behavior?
   - Wait for plugin model (Phase 7)?

### Recommended Object List (Preliminary)

**Network (MikroTik):**
- `obj.mikrotik.chateau_lte7_ax` ✅
- `obj.mikrotik.chr` ✅

**Hypervisors:**
- `obj.proxmox.ve_8`

**Containers:**
- `obj.proxmox.lxc`

**VMs:**
- `obj.proxmox.qemu`

**Operating Systems:**
- `obj.linux.debian_12`
- `obj.linux.ubuntu_22_04`
- `obj.linux.alpine_3_18`

**Services:**
- `obj.nextcloud.server`
- `obj.jellyfin.server`
- `obj.prometheus.server`
- `obj.grafana.server`
- (etc., one per major service type)

**Total:** ~15-25 objects

### Recommended Approach

1. **Define objects in order of dependency**
   - Devices first (routers, hypervisors)
   - VMs/containers next
   - Services last

2. **Validate each object against class**
   - Capability signature match
   - Required capabilities satisfied

3. **Document generator needs**
   - What templates needed?
   - What data transformations needed?
   - Defer implementation to Phase 7

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Object-class mismatch | Medium | High | Iterative validation with class authors |
| Vendor-specific leakage | Low | Medium | Strict `vendor.*` namespace enforcement |
| Generator coupling | Medium | Medium | Document needs, implement in Phase 7 |

### Effort Estimate

- **Object definitions:** 1 day per object × 20 objects = 20 days
- **Validation:** 2-3 days
- **Documentation:** 2-3 days

**Total:** 2-3 weeks (if done in parallel) or 4-5 weeks (if sequential)

### Dependencies
- **Blocks on:** Phase 2 (need classes to reference)
- **Blocks:** Phase 4 (instance data needs objects)

---

## Phase 4: Topology Data Migration

### Objective
Migrate instance data to explicit v5 bindings.

### Actions Defined

1. ⚠️ **Add class_ref and object_ref**
   - For all migrated entities in `v5/topology/instances/home-lab/`

2. ✅ **Keep legacy-only fields out of new files**

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| v5 compilation passes with no unresolved class/object links | ✅ Yes (compiler) | Low |

### Current State
- ⚠️ **Migration script exists:** `topology-tools/migrate-to-v5.py`
- ❌ No v5 instance data files yet
- ❌ Script not integrated with class/object modules

### Implementation Readiness: ⚠️ 60%

**Partial.** Migration script exists but needs enhancement.

### Missing Details

1. **Migration script enhancements needed**
   - Add `class_ref` and `object_ref` fields (not just v4 field cleanup)
   - Integrate with Phase 1 mapping table
   - Validate against Phase 2/3 class/object modules

2. **Instance data structure**
   - How to organize v5 instances?
   - One file per layer? Per entity type?

3. **Compilation integration**
   - Does `compile-topology.py` support v5 yet?
   - Class/object resolution logic needed

### Migration Script Current Capabilities

**What it does:**
- Migrates L3 storage → storage_endpoints
- Migrates L4 LXC inline resources → resource_profiles
- Migrates L4 LXC ansible.vars → L5 services config
- Migrates L5 external_services → services with runtime.type=docker
- Backfills storage_endpoint_ref from storage_ref

**What it doesn't do:**
- ❌ Add `class_ref` fields
- ❌ Add `object_ref` fields
- ❌ Validate against class/object modules
- ❌ Handle all entity types (focuses on L3-L5)

### Recommended Enhancement

```python
# Enhance migrate-to-v5.py with:

def add_class_and_object_refs(topology: Dict, mapping: Dict) -> int:
    """Add class_ref and object_ref based on Phase 1 mapping."""
    updated = 0

    # For each entity in v4 topology:
    #   1. Look up in mapping table
    #   2. Add class_ref and object_ref
    #   3. Validate refs exist in modules

    return updated
```

### Recommended Approach

1. **Load Phase 1 mapping table**
2. **Enhance migration script** to add refs
3. **Run migration on v4 topology**
4. **Output to v5/topology/instances/home-lab/**
5. **Validate with compiler** (class/object resolution)
6. **Iterate** until compilation passes

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Mapping table incomplete | Medium | High | Phase 1 thoroughness |
| Migration script bugs | Medium | Medium | Extensive testing, dry-run mode |
| Class/object refs invalid | Low | High | Validation before commit |

### Effort Estimate

- **Script enhancement:** 2-3 days
- **Migration execution:** 1 day
- **Validation and fixes:** 3-5 days
- **Iteration:** 2-3 days

**Total:** 1-2 weeks

### Dependencies
- **Blocks on:** Phase 3 (need objects to reference)
- **Blocks:** Phase 5 (lock/profile need migrated data)

---

## Phase 5: Lock and Profile Operationalization

### Objective
Make version and profile governance executable.

### Actions Defined

1. ⚠️ **Finalize model.lock.yaml**
   - Pin core_model_version
   - Pin class versions
   - Pin object versions

2. ⚠️ **Finalize profile-map.yaml**
   - production / modeled / test-real profiles

3. ⚠️ **Enforce strict model-lock in CI**

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| All three profiles compile and validate | ✅ Yes (CI) | Low |
| Compatibility checks pass | ✅ Yes (validation) | Medium |

### Current State
- ✅ model.lock.example.yaml exists
- ✅ profile-map.example.yaml exists
- ❌ No operational lock file
- ❌ No operational profile maps
- ❌ CI doesn't enforce lock

### Implementation Readiness: ⚠️ 50%

**Half ready.** Schemas exist, but no operational implementation.

### Missing Details

1. **Lock file generation**
   - Manual or automated?
   - How to compute versions?

2. **Profile substitution logic**
   - Where does this happen? Compiler stage?
   - How to validate substitutions?

3. **CI integration**
   - How to enforce strict mode?
   - What does failure look like?

### Recommended Approach

1. **Generate initial lock file**
   ```bash
   # Create script:
   python v5/topology-tools/generate-model-lock.py \
     --topology v5/topology/ \
     --output v5/topology/model.lock.yaml
   ```

2. **Create profile maps**
   - Start with production (1:1 mapping)
   - Add modeled (virtual substitutions)
   - Add test-real (behavior overrides)

3. **Implement profile compilation**
   ```bash
   python v5/topology-tools/compile-topology.py \
     --topology v5/topology/ \
     --profile production \
     --output v5-build/topology-production.json
   ```

4. **Add CI checks**
   - Validate lock file is up to date
   - Compile all three profiles
   - Fail if any profile fails

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Profile substitution bugs | Medium | Medium | Extensive testing |
| Lock file drift | Medium | Medium | Automated generation + CI check |
| Capability signature mismatch | Low | High | Validation before substitution |

### Effort Estimate

- **Lock generation script:** 2 days
- **Profile creation:** 2-3 days
- **Compiler integration:** 2-3 days
- **CI integration:** 1-2 days

**Total:** 1 week

### Dependencies
- **Blocks on:** Phase 4 (need instance data)
- **Blocks:** Phase 6 (parity needs profiles)

---

## Phase 6: Generation and Validation Parity

### Objective
Achieve functional parity for generated artifacts.

### Actions Defined

1. ⚠️ **Route v5 generation from canonical JSON**
2. ⚠️ **Compare key outputs v4 vs v5**
3. ⚠️ **Close parity gaps or document accepted differences**

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| Parity checklist approved for production-critical artifacts | ⚠️ Subjective | High |

### Current State
- ❌ v5 generation not implemented
- ❌ No parity comparison tooling
- ❌ No parity checklist defined

### Implementation Readiness: ⚠️ 40%

**Low readiness.** Major implementation work required.

### Missing Details

1. **Which artifacts are "production-critical"?**
   - Terraform configs? Ansible inventory? Documentation?
   - Need explicit list

2. **Parity criteria**
   - Exact match? Semantic equivalence? Acceptable differences?

3. **Generator refactoring scope**
   - Can v4 generators read JSON? Or need rewrite?

### Critical Artifacts (Recommended)

| Artifact | v4 Source | v5 Source | Priority |
|----------|-----------|-----------|----------|
| Terraform (MikroTik) | topology.yaml | topology.json | **Critical** |
| Terraform (Proxmox) | topology.yaml | topology.json | **Critical** |
| Ansible inventory | topology.yaml | topology.json | **Critical** |
| Network diagrams | topology.yaml | topology.json | **High** |
| Documentation | topology.yaml | topology.json | **Medium** |
| Bootstrap scripts | topology.yaml | topology.json | **Medium** |

### Recommended Approach

1. **Define parity checklist**
   - List all artifacts
   - Define parity criteria per artifact

2. **Create parity comparison tool**
   ```bash
   python v5/topology-tools/compare-outputs.py \
     --v4-dir v4-generated/ \
     --v5-dir v5-generated/ \
     --checklist parity-checklist.yaml \
     --output parity-report.html
   ```

3. **Refactor generators iteratively**
   - Start with Terraform (highest priority)
   - Then Ansible inventory
   - Then documentation

4. **Accept or close gaps**
   - Document accepted differences
   - Fix unacceptable differences

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Generator refactoring breaks v4 | Medium | High | Maintain v4 and v5 generators separately |
| Parity impossible due to model differences | Low | High | Document and accept |
| Scope creep (too many artifacts) | Medium | Medium | Prioritize critical artifacts only |

### Effort Estimate

- **Parity checklist:** 1-2 days
- **Comparison tooling:** 2-3 days
- **Generator refactoring:** 2-3 days per generator × 5 generators = 10-15 days
- **Gap resolution:** 3-5 days

**Total:** 2-4 weeks

### Dependencies
- **Blocks on:** Phase 5 (need profiles)
- **Blocks:** Phase 7 (plugin migration needs working generators)

---

## Phase 7: Plugin Microkernel Migration

### Objective
Migrate runtime extension model to plugin architecture.

### Actions Defined

1. ❌ **Introduce plugin manifest schema and registry**
2. ❌ **Migrate generators → validators → compiler hooks**
3. ❌ **Remove hardcoded dispatch from v5 runtime**

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| New module onboarding requires no core branching | ⚠️ Subjective | Medium |
| Plugin dependency/order rules enforced in CI | ✅ Yes | Low |

### Current State
- ⚠️ **ADR 0063 is "Proposed" not "Accepted"**
- ❌ No plugin infrastructure implemented
- ❌ No plugin manifests

### Implementation Readiness: ⚠️ 30%

**Low readiness.** Depends on ADR 0063 acceptance.

### Blocking Issues

1. **ADR 0063 not accepted**
   - Cannot start implementation until approved

2. **Plugin contract not finalized**
   - Manifest format, API version, etc.

### Missing Details

1. **Plugin loading mechanism**
   - Python import? External process? WASM?

2. **Plugin registry**
   - Central? Distributed? How to discover?

3. **Plugin API stability**
   - Versioning strategy?
   - Backward compatibility?

### Recommended Approach

**First:** Get ADR 0063 accepted

**Then:**

1. **Implement plugin microkernel**
   - Core orchestrator
   - Plugin discovery
   - Dependency resolution

2. **Migrate generators to plugins**
   - Start with simplest generator (docs?)
   - Then terraform, ansible, bootstrap

3. **Migrate validators to plugins**
   - Layer validators
   - Reference validators
   - Capability validators

4. **Remove hardcoded logic**
   - Replace with plugin dispatch

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Plugin API churn | Medium | High | Version carefully, maintain compat |
| Performance regression | Low | Medium | Benchmark, optimize plugin loading |
| Complexity increase | Medium | Medium | Good documentation, examples |

### Effort Estimate

- **Microkernel implementation:** 1 week
- **Plugin manifest schema:** 2-3 days
- **Generator migration:** 1-2 days per generator × 5 = 5-10 days
- **Validator migration:** 3-5 days
- **Testing and iteration:** 1 week

**Total:** 3-4 weeks

### Dependencies
- **Blocks on:** Phase 6 (need working generators), **ADR 0063 acceptance**
- **Blocks:** Phase 8 (cutover needs stable plugin architecture)

---

## Phase 8: Cutover and Legacy Retirement Preparation

### Objective
Make v5 the default operational lane.

### Actions Defined

1. ⚠️ **Switch primary CI and build/deploy defaults to v5**
2. ⚠️ **Keep v4 in maintenance mode for defined period**
3. ⚠️ **Prepare removal plan for legacy-only fields**

### Exit Criteria

| Criterion | Checkable | Risk |
|-----------|-----------|------|
| v5 lane is default for production workflows | ✅ Yes | Low |
| Legacy removal gate date documented | ✅ Yes | Low |
| Rollback policy documented and tested | ⚠️ Testing hard | High |

### Current State
- ❌ v5 not operational
- ❌ No cutover plan beyond ADR guidance
- ❌ No rollback plan

### Implementation Readiness: ⚠️ 50%

**Half ready.** ADR provides guidance but lacks operational detail.

### Missing Details

1. **Cutover mechanics**
   - Big bang? Gradual? Per-artifact?

2. **Rollback plan**
   - How to revert if v5 fails?
   - What triggers rollback?

3. **Maintenance mode policy**
   - What fixes allowed in v4?
   - How long to maintain?

4. **Legacy field removal timeline**
   - ADR says "no earlier than 2026-10-01"
   - Need specific date

### Recommended Cutover Strategy

**Option A: Big Bang**
- Switch all CI/deployment to v5 on cutover date
- ⚠️ High risk

**Option B: Gradual**
- Phase 8a: v5 for documentation generation
- Phase 8b: v5 for Ansible inventory
- Phase 8c: v5 for Terraform (critical path)
- Phase 8d: Deprecate v4

**Recommendation:** Option B (gradual)

### Recommended Approach

1. **Document cutover checklist**
   - All critical artifacts passing parity
   - All profiles working
   - Plugin architecture stable
   - Team trained on v5

2. **Implement gradual cutover**
   - Start with low-risk artifacts
   - Monitor for issues
   - Expand gradually

3. **Prepare rollback**
   - Keep v4 lane functional
   - Document rollback procedure
   - Test rollback in dev environment

4. **Set legacy removal date**
   - Based on cutover success
   - Communicate to team
   - Update ADR 0062

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| v5 regression in production | Medium | **Critical** | Gradual cutover, extensive testing |
| Rollback fails | Low | **Critical** | Test rollback procedure |
| Team resistance | Low | Medium | Training, communication |

### Effort Estimate

- **Cutover planning:** 2-3 days
- **Gradual cutover execution:** 1 week per phase × 4 phases = 4 weeks
- **Monitoring and fixes:** 1 week
- **Rollback preparation and testing:** 2-3 days

**Total:** 2 weeks planning + 5 weeks execution = **7 weeks total**

But overlaps with stabilization, so **effective: ~2 weeks** of dedicated work

### Dependencies
- **Blocks on:** Phase 7 (need stable v5 infrastructure)
- **Blocks:** Nothing (end of migration)

---

## Overall Migration Timeline

### Sequential Execution (Conservative)

| Phase | Weeks | Cumulative |
|-------|-------|------------|
| Phase 0 | 0.5 | 0.5 weeks |
| Phase 1 | 1.5 | 2 weeks |
| Phase 2 | 3 | 5 weeks |
| Phase 3 | 3 | 8 weeks |
| Phase 4 | 1.5 | 9.5 weeks |
| Phase 5 | 1 | 10.5 weeks |
| Phase 6 | 3 | 13.5 weeks |
| Phase 7 | 4 | 17.5 weeks |
| Phase 8 | 2 | 19.5 weeks |

**Total: ~20 weeks (5 months)**

### Parallelized Execution (Aggressive)

Some phases can overlap:
- Phase 2 and 3 (classes and objects) can be partially parallel
- Phase 6 generators can be done in parallel

**Optimistic: ~14 weeks (3.5 months)**

---

## Completion Criteria Analysis

ADR 0062 defines 13 completion criteria. Current status:

| # | Criterion | Status | Blocker |
|---|-----------|--------|---------|
| 1 | Dual-lane repository structure | ❌ | Phase 0 |
| 2 | Dual-lane test suites | ❌ | Phase 0 |
| 3 | All entities have class_ref/object_ref | ❌ | Phase 4 |
| 4 | model.lock.yaml complete, CI strict mode | ❌ | Phase 5 |
| 5 | profile-map.yaml with 3 profiles, all pass | ❌ | Phase 5 |
| 6 | Artifact roots versioned (v4-*, v5-*) | ❌ | Phase 0 |
| 7 | v4 scripts write to v4-* only | ❌ | Phase 0 |
| 8 | Diagnostics schema validation passes | ❌ | Phase 6 |
| 9 | Capability contract checks pass | ❌ | Phase 2-3 |
| 10 | Production artifacts reach parity | ❌ | Phase 6 |
| 11 | Plugin microkernel complete | ❌ | Phase 7 |
| 12 | v5 default in CI for 1+ stabilization cycle | ❌ | Phase 8 |
| 13 | Rollback procedure documented and tested | ❌ | Phase 8 |

**Current Completion: 0/13 (0%)**

---

## Recommendations

### Immediate Actions (Week 1)

1. ✅ **Execute Phase 0**
   - This is the foundation
   - No dependencies
   - 2-3 days effort

2. ✅ **Get ADR 0063 accepted**
   - Required for Phase 7
   - Can be done in parallel with Phase 0-6

### Short-term Actions (Month 1)

3. ✅ **Build inventory automation (Phase 1)**
   - Required for all subsequent phases

4. ✅ **Define capability catalog (Phase 2)**
   - Required for class definitions

### Medium-term Actions (Month 2-3)

5. ✅ **Create class and object modules (Phase 2-3)**
   - Can be partially parallelized
   - Highest effort phases

6. ✅ **Enhance and run migration script (Phase 4)**
   - Depends on Phase 2-3 completion

### Long-term Actions (Month 4-5)

7. ✅ **Implement profiles and lock (Phase 5)**
8. ✅ **Achieve parity (Phase 6)**
9. ✅ **Plugin migration (Phase 7)**
10. ✅ **Cutover (Phase 8)**

---

## Conclusion

The 8-phase migration plan is **comprehensive and well-structured**. Key findings:

✅ **Strengths:**
- Clear phase boundaries
- Explicit exit criteria
- Logical dependencies
- Reasonable timeline

⚠️ **Weaknesses:**
- Some implementation details missing (but acceptable for ADR level)
- Phase 6 parity criteria somewhat subjective
- Phase 8 rollback testing difficult

❌ **Critical Gap:**
- **Phase 0 not executed** - this is blocking everything

**Overall Assessment:** Migration plan is **implementation-ready** after Phase 0 execution.

**Recommended First Step:** Execute Phase 0 immediately (2-3 days effort).
