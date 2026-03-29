# ADR 0082 Analysis: Plugin Module-Pack Composition and Index-First Discovery

- Date: 2026-03-29
- Status: Complete
- Scope: Analysis deliverables per ADR 0082 §Decision

---

## 1. Current State Baseline

| Metric | Value |
|--------|-------|
| Base framework plugins (topology-tools/plugins/) | 60 |
| Class modules with plugins | 1 (router: 1 plugin) |
| Object modules with plugins | 5 (glinet:1, mikrotik:3, network:1, orangepi:1, proxmox:2) |
| Total module-level plugins | 9 |
| Total plugins | 69 |
| module-index.yaml entries | 6 (1 class + 5 object) |
| Object modules without plugins | ~9 (cloud, service, software, storage, observability, operations, power, _shared) |
| Existing boundary tests | Yes (level boundaries, distribution boundary, manifest discovery) |
| Discovery modes | Index-first + fallback recursive scan |
| Framework lock | SHA-256 integrity on full framework |

---

## 2. Option Matrix (Deliverable 1)

### Option A: Current Structure + Index-First Hardening

**Description**: Maintain current layout. Harden module-index.yaml to be authoritative
(no fallback scan in production). Add completeness validation.

| Dimension | Assessment |
|-----------|------------|
| Migration cost | **Zero** — no structural changes |
| Build complexity | **Unchanged** — copy topology/ + topology-tools/ |
| Module boundary enforcement | **Convention-based** — tests enforce, not structure |
| Per-module versioning | **None** — whole-framework version only |
| Incremental rebuild | **Not possible** — full rebuild always |
| AI workspace impact | **None** — no change to navigation or context |
| ADR 0081 compliance | **Full** — trivially preserved |
| Scale ceiling | ~15-20 modules before flat layout friction |

**Hardening actions required**:

1. Make module-index.yaml authoritative (fail if missing in production mode).
2. Add CI completeness check: all plugins.yaml on disk must be in index.
3. Add CI inverse check: all index entries must point to existing files.
4. Add schema_version validation for module-index.yaml.
5. Consider auto-generation of module-index.yaml from filesystem.

### Option B: Internal Module-Pack Build Assembly

**Description**: Each class/object module gets a formal module-pack manifest
(`module-pack.yaml`) with version, integrity hash, and declared dependencies.
A build step pre-assembles all module-packs into the single framework artifact.

| Dimension | Assessment |
|-----------|------------|
| Migration cost | **High** — new build step, per-module manifests, CI changes |
| Build complexity | **Increased** — assembly pipeline, per-module hashing |
| Module boundary enforcement | **Structural** — build rejects malformed packs |
| Per-module versioning | **Yes** — explicit version per module-pack |
| Incremental rebuild | **Possible** — hash-based change detection |
| AI workspace impact | **Moderate** — more manifests, deeper nesting |
| ADR 0081 compliance | **Full** — assembly produces single artifact |
| Scale ceiling | 50+ modules comfortable |

**Required infrastructure**:

1. `module-pack.yaml` schema per module (id, version, integrity, dependencies, exports).
2. Assembly script (`build-framework-distribution.py` extension).
3. Per-module integrity computation.
4. Module dependency resolution at build time.
5. Module-pack validation CI step.
6. Updated framework.lock.yaml with per-module checksums.

### Option C: Hybrid — Metadata Lock Extensions

**Description**: Keep current directory structure. Extend module-index.yaml with per-module
metadata (version, integrity, capability exports). No separate build assembly step, but
enriched metadata enables future evolution and per-module verification.

| Dimension | Assessment |
|-----------|------------|
| Migration cost | **Low** — extend existing YAML, add verification |
| Build complexity | **Minimal increase** — integrity computation during build |
| Module boundary enforcement | **Convention + metadata** — tests + integrity checks |
| Per-module versioning | **Yes** — declared in extended index |
| Incremental rebuild | **Partial** — integrity change detection possible |
| AI workspace impact | **Minimal** — one file gets richer, layout unchanged |
| ADR 0081 compliance | **Full** — trivially preserved |
| Scale ceiling | ~30-40 modules before metadata-only approach limits |

**Extended module-index.yaml schema (proposed)**:

```yaml
schema_version: 2

class_modules:
  - id: router
    version: 1.0.0
    plugins_manifest: class-modules/router/plugins.yaml
    integrity: sha256-<hash>
    capabilities_exported: [router.ports, router.data_channels]

object_modules:
  - id: mikrotik
    version: 1.2.0
    plugins_manifest: object-modules/mikrotik/plugins.yaml
    integrity: sha256-<hash>
    depends_on_class: [router]
    capabilities_exported: [mikrotik.terraform, mikrotik.bootstrap]
```

---

## 3. AI Productivity Impact Analysis (Deliverable 2)

### Navigation Complexity

| Option | Files to Navigate | Context Stability | Verdict |
|--------|-------------------|-------------------|---------|
| A | Same as today: topology.yaml → module-index.yaml → plugins.yaml per module | **Stable** | ✅ Best |
| B | +1 module-pack.yaml per module, +assembly config | **Moderate churn** during migration | ⚠️ Acceptable |
| C | Same as A + enriched index | **Stable** | ✅ Best |

### Prompt/Context Stability

- **Option A**: AI agents already navigate this structure effectively. No change.
- **Option B**: AI must understand module-pack manifests, assembly pipeline, and two-stage build. ~15-20% more context tokens per task.
- **Option C**: module-index.yaml grows by ~50 lines for 6 modules. Negligible context cost.

### Typical Edit/Test Loop Cost

| Scenario | Option A | Option B | Option C |
|----------|----------|----------|----------|
| Add new object plugin | Edit plugins.yaml + module-index.yaml, run tests | Edit plugins.yaml + module-pack.yaml + module-index.yaml, run assembly + tests | Edit plugins.yaml + module-index.yaml (auto-integrity), run tests |
| Add new object module | Create dir + plugins.yaml, update module-index.yaml | Create dir + plugins.yaml + module-pack.yaml, update assembly config | Create dir + plugins.yaml, update module-index.yaml |
| Debug plugin failure | Direct: read plugin → read test → fix | One extra layer: which module-pack? → read plugin → fix → reassemble | Same as A |

### AI Productivity Verdict

**Option C ≈ Option A >> Option B** for current scale (6 modules / 69 plugins).
Option B justified only at >20 modules where assembly benefits outweigh overhead.

---

## 4. Runtime Invariants (Deliverable 3)

### Path Resolution Invariants

| Invariant | A | B | C |
|-----------|---|---|---|
| Monorepo: `topology/class-modules/<id>/plugins/` resolves | ✅ Unchanged | ✅ Post-assembly | ✅ Unchanged |
| Standalone: `framework/topology/class-modules/<id>/plugins/` resolves | ✅ Copy | ✅ Assembled | ✅ Copy |
| Base manifest path relative to topology-tools/ | ✅ | ✅ | ✅ |
| Module plugin paths relative to module root | ✅ | ✅ | ✅ |

### Discovery Invariants

| Invariant | A | B | C |
|-----------|---|---|---|
| Merge order: kernel → framework → class → object → project | ✅ | ✅ | ✅ |
| Plugin ID global uniqueness | ✅ | ✅ (build-time) | ✅ |
| Duplicate ID = hard error | ✅ | ✅ | ✅ |
| Lexicographic ordering within level | ✅ | ✅ | ✅ |
| Fallback scan when index invalid | ✅ (prod: fail) | N/A (assembly guarantees) | ✅ (prod: fail) |

### Lock/Integrity Invariants

| Invariant | A | B | C |
|-----------|---|---|---|
| framework.lock.yaml whole-framework integrity | ✅ | ✅ | ✅ |
| Per-module integrity verification | ❌ | ✅ | ✅ (in extended index) |
| Revision pinning (commit SHA) | ✅ | ✅ | ✅ |
| Content drift detection per module | ❌ | ✅ | ✅ |

---

## 5. Migration and Rollback Design (Deliverable 4)

### Recommended Phased Approach (for Option C)

**Phase 1: Index-First Hardening** (prerequisite for all options)

- Make module-index.yaml authoritative in production mode.
- Add CI completeness validation (bidirectional: index ↔ filesystem).
- Add schema validation for module-index.yaml.
- Rollback: revert to fallback scan mode (1 config flag).

**Phase 2: Metadata Enrichment**

- Bump module-index.yaml to schema_version: 2.
- Add `version`, `integrity`, `depends_on_class` per module.
- Add `generate-module-index.py` script for auto-generation.
- Update framework.lock.yaml generation to include per-module hashes.
- Rollback: strip extended fields, revert to schema_version: 1.

**Phase 3: Verification Integration**

- Add per-module integrity verification in discover stage.
- Add module dependency validation.
- Integrate with framework lock verification pipeline.
- Rollback: disable per-module verification (flag-gated).

**Phase 4 (conditional): Module-Pack Evolution**

- Gate: >20 active modules OR measurable build time degradation.
- Migrate extended index entries to full module-pack.yaml.
- Add assembly pipeline.
- This is Option B, triggered only by evidence.

### Rollback Triggers (Objective)

| Trigger | Measurement | Threshold |
|---------|-------------|-----------|
| AI edit loop regression | Avg edits to complete standard task | >25% increase |
| Build time regression | Full compile+generate time | >30% increase |
| Discovery failures | CI failure rate in discovery stage | Any increase |
| Developer friction | Manual steps per module change | >2 additional steps |

---

## 6. Verification Matrix (Deliverable 5)

### Contract Tests

| Test | Exists | Phase |
|------|--------|-------|
| module-index.yaml format validation | ✅ test_manifest_discovery.py | Phase 1 |
| Index entries point to valid files | ✅ test_manifest_discovery.py | Phase 1 |
| Fallback scan matches index results | ✅ test_manifest_discovery.py | Phase 1 |
| Plugin ID uniqueness across manifests | ✅ test_manifest.py | Existing |
| Plugin level boundaries | ✅ test_plugin_level_boundaries.py | Existing |
| Index completeness (no orphan plugins.yaml) | ❌ **NEW** | Phase 1 |
| Schema_version validation | ❌ **NEW** | Phase 1 |
| Per-module integrity verification | ❌ **NEW** | Phase 2 |
| Module dependency resolution | ❌ **NEW** | Phase 2 |
| Extended index backward compatibility | ❌ **NEW** | Phase 2 |

### Distribution Boundary Tests

| Test | Exists | Phase |
|------|--------|-------|
| module-index.yaml included in distribution | ✅ test_framework_distribution_boundary.py | Existing |
| All module plugins included | ✅ (implicit via discovery tests) | Phase 1: explicit |
| Module templates included | Partial | Phase 1: explicit |
| Per-module integrity matches distribution | ❌ **NEW** | Phase 2 |

### Standalone Artifact Rehearsal Tests

| Test | Exists | Phase |
|------|--------|-------|
| Artifact self-sufficiency (discovery works standalone) | ❌ **NEW** | Phase 2 |
| Lock verification against artifact content | Partial (lock tests exist) | Phase 2: extend |
| Monorepo → standalone parity | ❌ **NEW** | Phase 3 |

---

## 7. Recommendation

### Target Model: Option C (Hybrid with Metadata Lock Extensions)

**Rationale:**

1. **Scale fit**: 6 modules / 69 plugins is far below the threshold where Option B's
   build assembly overhead is justified. Option C provides per-module metadata at minimal cost.

2. **AI productivity preserved**: Directory layout unchanged. One file (module-index.yaml)
   gets richer. No new navigation patterns for agents.

3. **ADR 0081 compliance**: Single framework artifact contract preserved trivially —
   no assembly step changes the packaging model.

4. **Evolutionary safety**: Option C is a natural stepping stone. If module count grows
   beyond ~25-30 or build times degrade, evolving to Option B requires only:
   - Extract extended index entries → module-pack.yaml per module.
   - Add assembly step.
   The metadata from Phase 2 directly maps to module-pack manifests.

5. **Per-module integrity**: The main benefit of Option B (module-level change detection
   and integrity) is achievable in Option C via extended module-index.yaml without
   the build complexity.

6. **Rollback simplicity**: Every phase is independently reversible via schema_version
   downgrade or feature flags. No structural rollback needed.

### Key Risk: Metadata Drift

The primary risk of Option C over B is that metadata in module-index.yaml could drift
from actual module contents without a build-time enforcement step.

**Mitigation:**
- `generate-module-index.py` auto-generates from filesystem (CI-enforced).
- Pre-commit hook validates index ↔ filesystem consistency.
- Integrity hashes computed automatically, not manually maintained.

---

## References

- ADR 0063: Plugin microkernel contracts and 4-level boundary model
- ADR 0078: Object-module local plugin ownership and co-location
- ADR 0080: 6-stage lifecycle, phase model, contractual data bus
- ADR 0081: Framework runtime artifact and 1:N project distribution
- `topology-tools/plugin_manifest_discovery.py`: Discovery implementation
- `topology/module-index.yaml`: Current module registry
- `tests/plugin_contract/test_manifest_discovery.py`: Discovery contract tests
- `tests/plugin_contract/test_plugin_level_boundaries.py`: Boundary enforcement tests
- `tests/plugin_contract/test_framework_distribution_boundary.py`: Distribution tests
