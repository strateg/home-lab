# PRE-IMPLEMENTATION-REVIEW: ADR 0087 Unified Container Ontology

**Date:** 2026-04-06
**Reviewer:** Claude (Architectural Guardian)
**ADR Status:** Accepted
**Implementation Readiness:** READY with conditions

---

## 1. Readiness Assessment

### 1.1 ADR Document Completeness

| Section | Status | Notes |
| ------- | ------ | ----- |
| Context | COMPLETE | Clear problem statement |
| Decision | COMPLETE | 6 decisions + 5 hardening clauses (5g-5k) |
| Implementation Plan | COMPLETE | 6-phase plan with dependency graph |
| Acceptance Criteria | COMPLETE | 32 ACs (AC-1 to AC-32) |
| Out of Scope | COMPLETE | 3 items explicitly deferred |
| Consequences | COMPLETE | Positive/negative/risks documented |
| Analysis Artifacts | COMPLETE | GAP, ONTOLOGY, IMPL-PLAN, SWOT |

**Verdict:** ADR document is architecturally complete.

### 1.2 Current Implementation State

Based on codebase analysis, significant **partial implementation** already exists:

| Component | State | Evidence |
| --------- | ----- | -------- |
| `class.compute.workload.lxc` | EXISTS | `/topology/class-modules/compute/workload/class.compute.workload.lxc.yaml` |
| `class.compute.workload.docker` | EXISTS | `/topology/class-modules/compute/workload/class.compute.workload.docker.yaml` |
| `class.compute.workload.vm` | EXISTS | `/topology/class-modules/compute/workload/class.compute.workload.vm.yaml` |
| `class.compute.hypervisor.proxmox` | EXISTS | `/topology/class-modules/compute/hypervisor/class.compute.hypervisor.proxmox.yaml` |
| Other hypervisor classes | EXISTS | vbox, hyperv, vmware, xen classes present |
| Docker object | EXISTS | `obj.docker.container.generic.yaml` |
| Docker L4 instances | EXISTS | 12 instances in `L4-platform/docker/` with host sharding |
| L5 Docker service rewiring | PARTIAL | `svc-grafana@docker.srv-orangepi5` targets `docker-grafana` (L4) |
| LXC validator plugin | EXISTS | `lxc_refs_validator.py` with tests |
| VM validator plugin | EXISTS | `vm_refs_validator.py` |
| Service runtime validator | EXISTS | Supports Docker L4 targets (line 209) |

**Critical Finding:** Phases 1 and 2 class definitions are largely DONE. Validation and migration governance layers are incomplete.

### 1.3 Missing Components for Phase 1 Completion

| Missing | Required By | Priority |
| ------- | ----------- | -------- |
| `class.compute.workload` abstract base | Phase 1 | HIGH |
| `docker_refs_validator.py` plugin | Phase 1 (AC-6: cycle detection) | HIGH |
| host_ref DAG validator | Phase 1 (AC-6) | HIGH |
| L5->L1 Docker deprecation warnings | Phase 1 (AC-5) | HIGH |
| Host-shard path validator | Phase 1 (AC-7) | MEDIUM |
| Migration state tracking | AC-29 | MEDIUM |
| Ownership proof CI gate | AC-30 | MEDIUM |
| Tests for Docker refs | Phase 1 gate | HIGH |
| `--allow-deprecated` CI flag | Migration governance | LOW |

---

## 2. Critical Path Analysis

### 2.1 Phase 1 Critical Path (Docker Promotion MVP)

```text
[DONE] Create class.compute.workload.lxc
[DONE] Create class.compute.workload.docker
[DONE] Create Docker L4 instances (12 files)
[DONE] Host-sharded L4 directories
[PARTIAL] L5 service rewiring (some services updated)
[TODO] Create class.compute.workload abstract base
[TODO] Create docker_refs_validator.py
[TODO] Add host_ref DAG cycle detection
[TODO] Add L5->L1 Docker deprecation warning
[TODO] Integration tests for Docker class
[TODO] Negative tests for cycle detection
[TODO] Update service_runtime_refs to warn on L1 Docker targets
```

**Estimated Remaining Effort:** 3-5 days

### 2.2 Phase 2 Critical Path (Hypervisor Platform Split)

```text
[DONE] Create class.compute.hypervisor.proxmox
[DONE] Create class.compute.hypervisor.vbox
[DONE] Create class.compute.hypervisor.hyperv
[DONE] Create class.compute.hypervisor.vmware
[DONE] Create class.compute.hypervisor.xen
[DONE] Add vm_constraints to proxmox class
[TODO] Update class.compute.hypervisor to v2.0 abstract base
[TODO] Add execution_model linkage validation
[TODO] Update obj.proxmox.ve to reference new class
[TODO] Integration tests for hypervisor classes
```

**Estimated Remaining Effort:** 2-3 days

### 2.3 Parallel Execution Strategy

Phases 1 and 2 are independent and CAN run in parallel:

```text
Week 1:
  [Thread A] Phase 1: docker_refs_validator + cycle detection
  [Thread B] Phase 2: hypervisor abstract base + execution_model

Week 2:
  [Thread A] Phase 1: L5 deprecation warnings + tests
  [Thread B] Phase 2: obj.proxmox.ve update + tests

Week 3 (Merge Gate):
  - Both phases complete
  - Phase 3 can begin (depends on Phase 2)
```

---

## 3. Blocking Dependencies

### 3.1 Technical Dependencies

| Dependency | Blocking | Resolution |
| ---------- | -------- | ---------- |
| Plugin registry supports new validator | Phase 1 | Verify plugins.yaml manifest |
| PluginContext.subscribe works for DAG validation | Phase 1 | Already proven in lxc_refs_validator |
| class.compute.workload base class | All workload classes | Create first |
| Hypervisor abstract base v2.0 | Phase 3 | Refactor current class |
| Volume format enum in class.storage.volume | Phase 4 | Coordinate with L3 work |

### 3.2 Data Dependencies

| Dependency | Blocking | Resolution |
| ---------- | -------- | ---------- |
| All Docker L4 instances exist | L5 rewiring | DONE (12 instances) |
| L5 services updated to target L4 | Phase 1 gate | PARTIAL - audit remaining |
| obj.proxmox.ve exists | Phase 2 | DONE - already uses `@extends: class.compute.hypervisor.proxmox` |
| Host OS with docker capability | Runtime validation | VERIFY on srv-orangepi5 |

**Note:** `obj.proxmox.ve` already references `class.compute.hypervisor.proxmox` via `@extends`. Phase 2 gate AC-9 is satisfied.

### 3.3 Process Dependencies

| Dependency | Blocking | Resolution |
| ---------- | -------- | ---------- |
| ADR 0086 plugin contract | All new validators | COMPLIANT |
| ADR 0088 semantic-only manifests | Migration state | VERIFY alignment |
| Test suite baseline | Phase gates | Run `pytest tests -q` |

---

## 4. Risk Assessment

### 4.1 High-Priority Risks

| Risk | Probability | Impact | Mitigation |
| ---- | ----------- | ------ | ---------- |
| Breaking existing L4/L5 during migration | HIGH | HIGH | Feature flags, aliases, comprehensive tests |
| Missing host_ref cycle detection | MEDIUM | HIGH | Implement before Phase 1 gate |
| Service runtime refs miss L4 Docker | LOW | HIGH | Already handled (line 209 in validator) |
| Topology file count explosion | MEDIUM | MEDIUM | Defaults inheritance pattern |

### 4.2 Dependency Risks

| Risk | Description | Mitigation |
| ---- | ----------- | ---------- |
| Phase 3 blocked on Phase 2 | VM validation requires hypervisor constraints | Parallel Phase 1+2 first |
| Phase 4 blocked on Phase 1+3 | Storage needs both workload types | Sequence correctly |
| Phase 5 blocked on Phase 1 | Nested scope needs Docker base | Sequence correctly |

---

## 5. Pre-Implementation Checklist

### 5.1 Before Starting Phase 1

- [ ] Verify all 12 Docker L4 instances compile: `python topology-tools/compile-topology.py`
- [ ] Audit L5 services with `runtime.type: docker` for L4 target_ref
- [ ] Confirm `plugins.yaml` manifest can register new validators
- [ ] Create `class.compute.workload.yaml` abstract base
- [ ] Confirm test baseline: `python -m pytest tests -q`

### 5.2 Before Starting Phase 2

- [ ] Document current `class.compute.hypervisor` usage
- [ ] Verify `obj.proxmox.ve` exists and references current class
- [ ] Plan execution_model enum (bare_metal | hosted)
- [ ] Identify which instances need linkage refs

### 5.3 Gate Validation Commands

```bash
# Phase 1 Gate
python -m pytest tests -q
python topology-tools/compile-topology.py
V5_SECRETS_MODE=passthrough python scripts/orchestration/lane.py validate-v5

# Audit L5 Docker services
grep -r "runtime:" projects/home-lab/topology/instances/L5-application/ | grep -i docker

# Check host_ref in Docker L4
grep -r "host_ref:" projects/home-lab/topology/instances/L4-platform/docker/
```

---

## 6. Phase 1 File Creation Order

### 6.1 Recommended Sequence

| Order | File | Rationale |
| ----- | ---- | --------- |
| 1 | `topology/class-modules/compute/workload/class.compute.workload.yaml` | Abstract base needed first |
| 2 | Update `class.compute.workload.lxc.yaml` with `@extends` | Inherit from abstract base |
| 3 | Update `class.compute.workload.docker.yaml` with `@extends` | Inherit from abstract base |
| 4 | `topology-tools/plugins/validators/docker_refs_validator.py` | New validator for Docker instances |
| 5 | `topology-tools/plugins/validators/host_ref_dag_validator.py` | Cycle and depth detection |
| 6 | Update `plugins.yaml` manifest | Register new validators |
| 7 | `tests/plugin_integration/test_docker_refs_validator.py` | Unit tests |
| 8 | `tests/plugin_integration/test_host_ref_dag_validator.py` | Unit tests |
| 9 | Update `service_runtime_refs_validator.py` | Add L5->L1 Docker deprecation warning |
| 10 | Audit and update remaining L5 Docker services | Complete rewiring |

### 6.2 Class Definition: `class.compute.workload.yaml`

```yaml
@class: class.compute.workload
@title: Compute Workload Abstract Base
@summary: Abstract base class for compute workloads (LXC, Docker, VM).
@layer: L4
@version: 1.0.0
@abstract: true

# Common properties inherited by all workload types
os_policy: required
firmware_policy: forbidden  # Override in VM class
os_cardinality:
  min: 1
  max: 1
multi_boot: false
allowed_os_install_models:
- container_base
- installable  # For VMs

# Reference contracts
host_ref_required: true
host_ref_target_layer: L1
host_ref_target_alternative_layer: L4  # For nested (Docker-in-LXC)

# Common capabilities
required_capabilities: []
optional_capabilities: []

invariants:
- subclass must define concrete policies
- instance overrides must not violate class invariants
```

### 6.3 Validator: `docker_refs_validator.py` Structure

```python
"""Docker container reference validator."""

class DockerRefsValidator(ValidatorJsonPlugin):
    """Validate Docker container references and host capabilities."""

    _DOCKER_CLASSES = {"class.compute.workload.docker"}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # 1. Validate host_ref targets L1 device OR L4 LXC
        # 2. Validate host declares docker capability
        # 3. Validate image reference format
        # 4. Validate network refs (if present)
        # 5. Validate storage/volume refs (if present)
        pass
```

### 6.4 Validator: `host_ref_dag_validator.py` Structure

```python
"""Host reference DAG validator - cycle and depth detection."""

class HostRefDagValidator(ValidatorJsonPlugin):
    """Validate host_ref forms a DAG with max depth 2."""

    _WORKLOAD_CLASSES = {
        "class.compute.workload.lxc",
        "class.compute.workload.docker",
        "class.compute.workload.vm",
    }
    _MAX_DEPTH = 2

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # 1. Build host_ref graph from all workload instances
        # 2. Run DFS to detect cycles
        # 3. Check depth from L1 roots
        # 4. Emit errors for cycles or depth > 2
        pass

    def _detect_cycle(self, graph: dict, start: str) -> list[str] | None:
        """DFS-based cycle detection returning cycle path if found."""
        pass

    def _compute_depth(self, graph: dict, node: str) -> int:
        """Compute depth from L1 root for given node."""
        pass
```

---

## 7. Validation Strategy

### 7.1 Test Coverage Requirements

| Test Type | Count | Coverage |
| --------- | ----- | -------- |
| Unit tests for docker_refs_validator | 10+ | Host ref validation, capability checks |
| Unit tests for host_ref_dag_validator | 5+ | Cycle detection, depth limits |
| Integration tests for Docker L4 | 3+ | Full compile with L5 services |
| Negative tests | 5+ | Invalid refs, cycles, depth violations |
| Regression tests | All existing | Ensure no breakage |

### 7.2 Negative Test Scenarios (AC-6)

1. `host_ref` cycle: A -> B -> A (ERROR)
2. `host_ref` depth > 2: L1 -> L4 -> L4 -> L4 (ERROR)
3. Docker on non-Docker host (ERROR)
4. L5 Docker service targeting L1 without L4 (WARNING -> future ERROR)

---

## 8. Migration Governance Artifacts

### 8.1 Feature Flag Location

Add to `projects/home-lab/framework.lock.yaml`:

```yaml
adr_0087:
  phase1_enabled: false  # Set true when Phase 1 complete
  phase2_enabled: false
  migration_mode: legacy  # legacy | migrating | migrated | rollback
```

### 8.2 Deprecation Warning Template

```python
# In service_runtime_refs_validator.py
if runtime_type == "docker" and target_layer == "L1":
    diagnostics.append(
        self.emit_diagnostic(
            code="W0087",
            severity="warning",
            stage=stage,
            message=(
                f"Service '{row_id}': runtime.target_ref points to L1 device '{target_ref}'; "
                "ADR 0087 requires Docker services to target L4 Docker containers. "
                "This pattern will become ERROR in Phase 3."
            ),
            path=f"{row_prefix}.runtime.target_ref",
        )
    )
```

---

## 9. Recommendations

### 9.1 Immediate Actions

1. **Create abstract base class** - `class.compute.workload.yaml` is foundational
2. **Implement host_ref_dag_validator** - Cycle detection is safety-critical (AC-6)
3. **Add L5->L1 Docker warning** - Migration signal required (AC-5)
4. **Run full test suite** - Establish baseline before changes

### 9.2 Deferred Actions

- Phase 3-6 implementation - wait for Phase 1+2 gates
- Ownership proof CI gate - implement after core validators
- `--allow-deprecated` flag - implement with Phase 3 ERROR promotion

### 9.3 Architectural Recommendations

1. **Reuse lxc_refs_validator patterns** - The existing validator provides proven patterns for:
   - Row subscription via `ctx.subscribe()`
   - Reference validation helper methods
   - Capability checking
   - Deprecation warning emission

2. **Keep validators focused** - One validator per concern:
   - `docker_refs_validator` - Docker-specific validation
   - `host_ref_dag_validator` - Global DAG invariants
   - `service_runtime_refs_validator` - L5 service contracts

3. **Use feature flags for rollback** - Each phase gate sets a flag that enables/disables new behavior

---

## 10. Conclusion

**ADR 0087 is READY for implementation** with the following conditions:

1. **Phase 1 and 2 can proceed in parallel** - their class definitions are independent
2. **Core validators (docker_refs, host_ref_dag) must be created first** - they enforce safety invariants
3. **Test coverage must be established before Phase 1 gate** - regression prevention is critical
4. **Migration governance (feature flags, deprecation warnings) must be implemented** - safe rollback path

**Total Estimated Effort:** 5-8 days for Phase 1+2 in parallel

**Next Steps:**
1. Create `class.compute.workload.yaml` abstract base
2. Implement `host_ref_dag_validator.py`
3. Implement `docker_refs_validator.py`
4. Add deprecation warning to `service_runtime_refs_validator.py`
5. Create comprehensive test suite
6. Run Phase 1 gate checklist
