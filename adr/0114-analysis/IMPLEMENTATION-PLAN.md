# ADR 0114 Implementation Plan

**Generated:** 2026-08-03
**Method:** SPC Analysis
**Total Effort:** 82h (~2 weeks)

---

## Overview

ADR 0114 consolidates existing architectural decisions (ADRs 0062, 0063, 0076, 0080, 0081, 0106) into a unified mental model. Most components are already implemented. This plan covers the remaining implementation gaps.

### Already Implemented (via referenced ADRs)

| Component | Source ADR |
|-----------|------------|
| 6-stage pipeline | ADR 0080 |
| Plugin microkernel | ADR 0063 |
| Class-Object-Instance model | ADR 0062 |
| Framework distribution | ADR 0076 |
| 1:N project model | ADR 0081 |
| Capability-driven plugins | ADR 0106 |

### Requires Implementation

| Component | ADR 0114 Section |
|-----------|------------------|
| TAIGA naming/renaming | §Framework Identity |
| E4013 diagnostic | §6.1 |
| Versioning semantics (multi-family lock) | §4.1 |
| project.model.lock.yaml | §1.4 |
| Project namespace enforcement | §3.3 |
| Recorded Debt D1 (coupling) | §Recorded Debt |
| Recorded Debt D2 (test fixtures) | §Recorded Debt |

---

## Phase 0: Preparation (4h)

| Task | Deliverable | Effort |
|------|-------------|--------|
| 0.1 | Create tracking issue/epic for ADR 0114 | 0.5h |
| 0.2 | Verify all referenced ADRs are Implemented | 1h |
| 0.3 | Create feature branch `feat/adr-0114-taiga-harmonization` | 0.5h |
| 0.4 | Prepare test plan for each phase | 2h |

---

## Phase 1: TAIGA Identity & Naming (8h)

**Goal:** Rename framework to TAIGA

| Task | Description | Effort | Files |
|------|-------------|--------|-------|
| 1.1 | Audit: find all `infra-topology-framework` occurrences | 1h | ~39 files |
| 1.2 | Update `topology/framework.yaml`: `framework_id: taiga` | 0.5h | 1 file |
| 1.3 | Update documentation references | 2h | docs/, adr/ |
| 1.4 | Update error messages and logs | 1h | topology-tools/ |
| 1.5 | Update CI/CD references | 1h | .github/ |
| 1.6 | Regenerate `framework.lock.yaml` | 0.5h | projects/ |
| 1.7 | Run full test suite | 2h | — |

**Validation:**
```bash
grep -r "infra-topology-framework" . --include="*.py" --include="*.yaml" --include="*.md" | wc -l  # Should be 0
task ci
```

---

## Phase 2: E4013 Diagnostic Implementation (12h)

**Goal:** Add diagnostic "topology requires capability no plugin provides"

| Task | Description | Effort | Location |
|------|-------------|--------|----------|
| 2.1 | Add E4013 to `error-catalog.yaml` | 0.5h | `topology-tools/data/` |
| 2.2 | Implement capability gap detection in validator | 4h | `topology-tools/plugins/validators/` |
| 2.3 | Collect model-level capabilities from compiled topology | 2h | `plugins/compilers/` |
| 2.4 | Collect plugin-provided capabilities from registry | 1h | `kernel/registry/` |
| 2.5 | Compare sets and emit E4013 on gap | 2h | `plugins/validators/` |
| 2.6 | Unit tests for E4013 | 1.5h | `tests/unit/` |
| 2.7 | Integration test with intentional gap | 1h | `tests/plugin_integration/` |

**Validation:**
```bash
pytest tests/unit/validators/test_capability_gap.py
pytest tests/plugin_integration/test_e4013_diagnostic.py
task validate:plugin-manifests
```

---

## Phase 3: Versioning Semantics (16h)

**Goal:** Implement multi-family lockfile

| Task | Description | Effort | Location |
|------|-------------|--------|----------|
| 3.1 | Design `framework.lock.yaml` v2 schema | 2h | `schemas/` |
| 3.2 | Add `framework_api_version` to `framework.yaml` | 1h | `topology/` |
| 3.3 | Implement toolchain version extraction | 2h | `topology-tools/utils/` |
| 3.4 | Implement library hash computation (`model.lock.yaml`) | 3h | `topology-tools/utils/` |
| 3.5 | Update `generate-framework-lock.py` for v2 format | 3h | `topology-tools/utils/` |
| 3.6 | Update `verify-framework-lock.py` for v2 format | 2h | `topology-tools/utils/` |
| 3.7 | Migration path from v1 to v2 lock format | 2h | `topology-tools/utils/` |
| 3.8 | Tests for version compatibility checks | 1h | `tests/unit/` |

**Schema v2 (draft):**
```yaml
# framework.lock.yaml v2
lock_version: 2
generated_at: "2026-08-03T..."

toolchain:
  api_version: "1.x"
  kernel_hash: "sha256:..."

library:
  model_lock_hash: "sha256:..."
  class_modules_hash: "sha256:..."
  object_modules_hash: "sha256:..."

packs:
  - id: base
    version: "1.0.0"
    hash: "sha256:..."
```

**Validation:**
```bash
task framework:lock-refresh
task framework:strict
pytest tests/unit/framework/test_lock_v2.py
```

---

## Phase 4: Project Model Lock (8h)

**Goal:** Implement `project.model.lock.yaml`

| Task | Description | Effort | Location |
|------|-------------|--------|----------|
| 4.1 | Design `project.model.lock.yaml` schema | 1h | `schemas/` |
| 4.2 | Implement project module discovery | 2h | `topology-tools/` |
| 4.3 | Implement project module hash computation | 2h | `topology-tools/utils/` |
| 4.4 | Generate lock during compile | 1.5h | `compile-topology.py` |
| 4.5 | Verify lock during compile | 1h | `compile-topology.py` |
| 4.6 | Tests | 0.5h | `tests/unit/` |

**Validation:**
```bash
task compile:default
test -f projects/home-lab/project.model.lock.yaml
```

---

## Phase 5: Project Namespace Enforcement (6h)

**Goal:** Validate `class.<project>.*` namespace

| Task | Description | Effort | Location |
|------|-------------|--------|----------|
| 5.1 | Add E4014 "Invalid project class namespace" | 0.5h | `error-catalog.yaml` |
| 5.2 | Implement namespace validator in discover stage | 3h | `plugins/discoverers/` |
| 5.3 | Extract project_id from context | 1h | `kernel/` |
| 5.4 | Unit tests | 1h | `tests/unit/` |
| 5.5 | Integration test with invalid namespace | 0.5h | `tests/plugin_integration/` |

**Validation:**
```bash
pytest tests/unit/discoverers/test_namespace_validator.py
task validate:plugin-manifests
```

---

## Phase 6: Resolve Debt D1 — Project Coupling (10h)

**Goal:** Parameterize hardcoded project paths

| Task | Description | Effort | Location |
|------|-------------|--------|----------|
| 6.1 | Audit all `projects/home-lab` references | 1h | grep analysis |
| 6.2 | Add `secrets_root` to project.yaml schema | 1h | `schemas/` |
| 6.3 | Update `compilers.yaml` — remove hardcoded defaults | 2h | `plugins/manifests/` |
| 6.4 | Update `instance_rows_compiler.py` — use context | 2h | `plugins/compilers/` |
| 6.5 | Update templates — use variables not paths | 2h | `templates/ansible/` |
| 6.6 | Verify no hardcoded paths remain | 1h | grep verification |
| 6.7 | Tests | 1h | `tests/` |

**Validation:**
```bash
grep -r "projects/home-lab" topology-tools/ --include="*.py" --include="*.yaml" | grep -v test | wc -l  # Should be 0
task ci
```

---

## Phase 7: Resolve Debt D2 — Test Fixtures (12h)

**Goal:** Prepare `projects/test-lab` as framework fixture

| Task | Description | Effort | Location |
|------|-------------|--------|----------|
| 7.1 | Create minimal `projects/test-lab/topology.yaml` | 2h | `projects/test-lab/` |
| 7.2 | Create representative test instances (5-10) | 3h | `projects/test-lab/topology/instances/` |
| 7.3 | Create `projects/test-lab/project.yaml` | 0.5h | `projects/test-lab/` |
| 7.4 | Update `tests/plugin_integration/test_tuc*.py` | 3h | `tests/` |
| 7.5 | Add test-lab to CI matrix | 1h | `.github/workflows/` |
| 7.6 | Document test-lab as framework fixture | 1h | `docs/` |
| 7.7 | Verify all tests pass with test-lab | 1.5h | — |

**Validation:**
```bash
pytest tests/plugin_integration/ --project=test-lab
task ci
```

---

## Phase 8: Documentation & Finalization (6h)

| Task | Description | Effort | Location |
|------|-------------|--------|----------|
| 8.1 | Update AGENT-RULEBOOK with new rules | 1h | `docs/ai/` |
| 8.2 | Update ADR-RULE-MAP.yaml | 0.5h | `docs/ai/` |
| 8.3 | Update ADR 0114 status to Implemented | 0.5h | `adr/` |
| 8.4 | Update REGISTER.md | 0.5h | `adr/` |
| 8.5 | Create migration guide | 2h | `docs/guides/` |
| 8.6 | Final review and PR | 1.5h | — |

---

## Summary

| Phase | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| 0 | Preparation | 4h | — |
| 1 | TAIGA Naming | 8h | Phase 0 |
| 2 | E4013 Diagnostic | 12h | Phase 0 |
| 3 | Versioning Semantics | 16h | Phase 1 |
| 4 | Project Model Lock | 8h | Phase 3 |
| 5 | Namespace Enforcement | 6h | Phase 2 |
| 6 | Debt D1 (Coupling) | 10h | Phase 1 |
| 7 | Debt D2 (Fixtures) | 12h | Phase 6 |
| 8 | Documentation | 6h | All |
| **TOTAL** | | **82h** | ~2 weeks |

---

## Execution Order (Critical Path)

```
Phase 0 ─────┬──▶ Phase 1 ──▶ Phase 3 ──▶ Phase 4
             │        │
             │        └──▶ Phase 6 ──▶ Phase 7
             │
             └──▶ Phase 2 ──▶ Phase 5
                                         │
                                         ▼
                                    Phase 8
```

**Parallel tracks:**
- Track A: Phases 1 → 3 → 4 (naming → versioning → project lock)
- Track B: Phases 2 → 5 (diagnostics → namespace)
- Track C: Phases 6 → 7 (debt resolution)

---

## Quality Gates

| Gate | When | Criteria |
|------|------|----------|
| G1 | After Phase 1 | `task ci` passes, no old naming |
| G2 | After Phase 2 | E4013 fires on test case |
| G3 | After Phase 3 | Lock v2 generates and verifies |
| G4 | After Phase 5 | Namespace violation rejected |
| G5 | After Phase 7 | All tests pass with test-lab |
| G6 | After Phase 8 | ADR 0114 → Implemented |

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| TAIGA rename breaks CI | Medium | High | Feature flag, gradual rollout |
| Lock v2 incompatible with existing projects | Low | High | Migration script, v1 fallback |
| test-lab insufficient coverage | Medium | Medium | Mirror home-lab structure |
| E4013 false positives | Low | Medium | Whitelist mechanism |

---

## Notes

- This plan prepares the foundation for ADR 0115 (Hash-Based Deploy Idempotency)
- ADR 0115 depends on stable assemble.verify phase and deploy state structure
- Phases can be executed incrementally with separate PRs per phase
