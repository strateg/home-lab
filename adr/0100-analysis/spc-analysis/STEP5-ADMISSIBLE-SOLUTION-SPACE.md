# SPC STEP 5: ADMISSIBLE SOLUTION SPACE

**Analysis Task:** Mermaid diagram generation — dependency graph visualization, unification, algorithm improvements, fixes

**Created:** 2026-04-22

**Purpose:** Define WHAT can be solutions, WITHOUT choosing which solution to implement.

---

## Methodology

For each problem, enumerate:
1. **Admissible approaches** — What types of solutions are valid
2. **Constraint compliance** — Which constraints each approach satisfies
3. **Trade-offs** — Pros/cons of each approach
4. **Inadmissible approaches** — What CANNOT be solutions (and why)

**No implementation decisions are made in this step.**

---

## SOLUTION SPACE 1: ID Sanitization Issues (P1.1, P1.2, P1.3, P1.4)

### Problem Group: Scattered sanitization, inconsistent IDs, ADR 0005 violation

**Root Cause:** Sanitization logic duplicated across templates instead of centralized in projection.

### Approach S1.A: Add safe_id to All Projections

**Description:**
- Extend `build_docs_projection()` to add `safe_id` field to ALL entities
- Extend `service_dependencies` list items to include `safe_id` for both `service_id` and `depends_on`
- Templates use `{{ row.safe_id }}` instead of inline `replace()` filters

**Satisfies Constraints:**
- ✅ C1.8 (centralized helpers)
- ✅ C7.2 (same instance_id → same safe_id)
- ✅ C3.2 (projection determinism)
- ✅ C2.6 (generators use projection only)

**Trade-offs:**
- ✅ PRO: Single source of truth for sanitization
- ✅ PRO: Templates become simpler
- ✅ PRO: ADR 0005 compliant
- ❌ CON: Projection schema change (medium risk)
- ❌ CON: Must update all templates to use safe_id
- ❌ CON: Breaks template backward compatibility

**Effort:** Medium
**Risk:** Medium

---

### Approach S1.B: Create Jinja2 Filter Function

**Description:**
- Add custom Jinja2 filter `safe_id` in template environment
- Templates use `{{ row.service_id | safe_id }}`
- Centralized in one place (template engine setup)

**Satisfies Constraints:**
- ✅ C1.8 (centralized, but in template layer not projection)
- ⚠️ C7.2 (consistent IF all templates use filter)
- ❌ C2.6 (logic in template layer, not projection)

**Trade-offs:**
- ✅ PRO: No projection schema change
- ✅ PRO: Easy to implement
- ❌ CON: Sanitization logic in template layer, not projection
- ❌ CON: Templates MUST remember to use filter (not enforced)
- ❌ CON: Doesn't fully satisfy ADR 0005 (not a projection helper)

**Effort:** Small
**Risk:** Low

---

### Approach S1.C: Hybrid — safe_id in Projection + Filter as Fallback

**Description:**
- Add safe_id to projections (S1.A)
- Also provide safe_id filter for edge cases (S1.B)
- Templates prefer projection safe_id, use filter only for dynamic refs

**Satisfies Constraints:**
- ✅ C1.8 (centralized in projection)
- ✅ C7.2 (safe_id field enforces consistency)
- ✅ C2.6 (projection-first approach)

**Trade-offs:**
- ✅ PRO: Best of both worlds
- ✅ PRO: Gradual migration path
- ❌ CON: More complex (two mechanisms)
- ❌ CON: Higher implementation effort

**Effort:** Medium-Large
**Risk:** Medium

---

### Inadmissible Approach: Keep Inline Sanitization

**Why Inadmissible:**
- ❌ Violates C1.8 (centralized helpers)
- ❌ Violates ADR 0005
- ❌ Does not fix P1.1, P1.2, P1.4

**Verdict:** NOT a solution.

---

## SOLUTION SPACE 2: Projection Architecture (P2.1, P2.2)

### Problem: Two projection paths, service_dependencies not in diagram_projection

### Approach S2.A: Unify Projections into Single Builder

**Description:**
- Merge `build_diagram_projection()` and `build_docs_projection()` into one
- New unified projection includes ALL fields: devices, services, service_dependencies, networks, etc.
- All with safe_id
- Both diagram_generator and docs_generator consume same projection

**Satisfies Constraints:**
- ✅ C1.7 (projection pattern)
- ✅ C2.6 (single projection interface)
- ✅ Enables REQ-NEW (all data in one place)

**Trade-offs:**
- ✅ PRO: Single source of truth
- ✅ PRO: Simplifies generator code
- ✅ PRO: Enables unified topology graph
- ❌ CON: Large projection schema (may be heavy for simple diagrams)
- ❌ CON: Breaking change for both generators
- ❌ CON: High implementation effort

**Effort:** Large
**Risk:** High

---

### Approach S2.B: Keep Separate, Add Projection Merger Utility

**Description:**
- Keep `build_diagram_projection()` and `build_docs_projection()` separate
- Create `merge_projections(diagram_proj, docs_proj)` utility
- Merged projection used by unified topology generator

**Satisfies Constraints:**
- ✅ C1.7 (projection pattern)
- ✅ Backward compatible (existing generators unchanged)
- ✅ Enables REQ-NEW (merged projection for new generator)

**Trade-offs:**
- ✅ PRO: No breaking changes
- ✅ PRO: Gradual migration path
- ✅ PRO: Lower risk
- ❌ CON: Merger adds complexity
- ❌ CON: Duplication (two projections + merger)
- ❌ CON: Merger must reconcile conflicting fields

**Effort:** Medium
**Risk:** Medium

---

### Approach S2.C: Extend Diagram Projection to Include Docs Data

**Description:**
- Add service_dependencies, domain projections (network, storage, etc.) to `build_diagram_projection()`
- Rename to `build_unified_projection()`
- Deprecate `build_docs_projection()` gradually

**Satisfies Constraints:**
- ✅ C1.7 (projection pattern)
- ✅ Enables REQ-NEW
- ⚠️ Backward compatibility depends on migration strategy

**Trade-offs:**
- ✅ PRO: Single projection direction
- ✅ PRO: Clear upgrade path
- ❌ CON: Breaking change for docs_generator
- ❌ CON: Large projection schema

**Effort:** Large
**Risk:** High

---

### Approach S2.D: Create New Unified Projection, Keep Old Ones

**Description:**
- Create `build_topology_projection()` — new unified builder
- Keep `build_diagram_projection()` and `build_docs_projection()` for backward compatibility
- New unified topology generator uses new projection
- Old generators unchanged

**Satisfies Constraints:**
- ✅ C1.7 (projection pattern)
- ✅ Backward compatible
- ✅ Enables REQ-NEW

**Trade-offs:**
- ✅ PRO: Zero breaking changes
- ✅ PRO: Clean separation
- ✅ PRO: Enables new features without breaking old
- ❌ CON: Three projection builders (complexity)
- ❌ CON: Potential duplication of logic

**Effort:** Large
**Risk:** Low (no breakage)

---

### Inadmissible Approach: Make Templates Access compiled_json Directly

**Why Inadmissible:**
- ❌ Violates C2.6 (generators must use projection only)
- ❌ Violates ADR 0079 (projection pattern)
- ❌ Creates tight coupling

**Verdict:** NOT a solution.

---

## SOLUTION SPACE 3: Missing Node Dependencies (P2.3, REQ-NEW)

### Problem: Only service dependencies extracted, need host/network/storage dependencies

### Approach S3.A: Extract All Dependency Types in Projection

**Description:**
- Extend projection to extract:
  - `host_dependencies`: from instance_data.host_ref
  - `network_dependencies`: from instance_data.managed_by_ref
  - `storage_dependencies`: from instance_data.volume_refs
  - `physical_links`: already exists
  - `service_dependencies`: already exists
- Unified dependency list schema:
  ```python
  {
      "source_id": "lxc-grafana",
      "target_id": "srv-gamayun",
      "dependency_type": "hosted_on",
      "layer": "L1"
  }
  ```

**Satisfies Constraints:**
- ✅ C8.1-C8.4 (dependency extraction pattern)
- ✅ Enables REQ-NEW

**Trade-offs:**
- ✅ PRO: Unified dependency model
- ✅ PRO: Enables unified topology graph
- ✅ PRO: Extensible (easy to add new dep types)
- ❌ CON: New projection schema fields
- ❌ CON: Must scan multiple instance types

**Effort:** Medium
**Risk:** Low (additive change)

---

### Approach S3.B: Domain-Specific Dependency Extractors

**Description:**
- Create separate dependency extractors for each domain:
  - `extract_host_dependencies(compiled_json)`
  - `extract_network_dependencies(compiled_json)`
  - `extract_storage_dependencies(compiled_json)`
- Projection calls all extractors and merges results

**Satisfies Constraints:**
- ✅ C8.1-C8.4
- ✅ Enables REQ-NEW
- ✅ Better separation of concerns

**Trade-offs:**
- ✅ PRO: Modular, easier to test
- ✅ PRO: Can be owned by domain experts
- ✅ PRO: Clear responsibility boundaries
- ❌ CON: More functions to maintain
- ❌ CON: Merger logic needed

**Effort:** Medium
**Risk:** Low

---

### Approach S3.C: Dependency as Plugin Stage

**Description:**
- Create new plugin family: `dependency_extractors`
- Plugins discover and extract dependencies from compiled_json
- Pipeline aggregates results
- Projection consumes aggregated dependencies

**Satisfies Constraints:**
- ✅ Plugin contract (ADR 0086)
- ✅ Extensible architecture
- ✅ Enables REQ-NEW

**Trade-offs:**
- ✅ PRO: Fully extensible (users can add custom dep types)
- ✅ PRO: Follows plugin architecture
- ❌ CON: Over-engineering for current need
- ❌ CON: High implementation effort
- ❌ CON: New plugin stage (complexity)

**Effort:** Large
**Risk:** Medium

---

### Inadmissible Approach: Hardcode Dependencies in Templates

**Why Inadmissible:**
- ❌ Violates C2.6 (use projection only)
- ❌ Violates ADR 0079 (projection pattern)
- ❌ Non-reusable

**Verdict:** NOT a solution.

---

## SOLUTION SPACE 4: Unified Topology Graph (REQ-NEW)

### Requirement: New diagram with all nodes + all dependencies + filtering

### Approach S4.A: New Generator Plugin

**Description:**
- Create `topology_graph_generator.py` plugin
- Consumes unified projection (from S2.A, S2.C, or S2.D)
- Renders `unified-topology.md.j2` template
- Template accepts filter parameters: `domain_filter`, `layer_filter`
- Mermaid graph conditionally includes/excludes nodes based on filters

**Satisfies Constraints:**
- ✅ C2.1-C2.6 (plugin contract)
- ✅ Enables filtering
- ✅ Additive (no breaking changes)

**Trade-offs:**
- ✅ PRO: Clean separation
- ✅ PRO: Plugin architecture
- ✅ PRO: Testable
- ❌ CON: Depends on S2.x (projection unification)

**Effort:** Medium (if projection exists)
**Risk:** Low

---

### Approach S4.B: Extend Diagram Generator

**Description:**
- Add unified topology template to existing `diagram_generator.py`
- Add filtering logic to projection builder
- Reuse existing plugin

**Satisfies Constraints:**
- ✅ C2.1-C2.6 (plugin contract)
- ✅ Reuses existing code

**Trade-offs:**
- ✅ PRO: No new plugin
- ✅ PRO: Simpler structure
- ❌ CON: diagram_generator becomes larger
- ❌ CON: Mixed responsibilities (diagrams + unified graph)

**Effort:** Medium
**Risk:** Low

---

### Approach S4.C: Parameterized Graph Template

**Description:**
- Create universal graph template: `graph-universal.md.j2`
- Template accepts parameters:
  - `node_types`: list of node types to include
  - `edge_types`: list of edge types to include
  - `layer_filter`: layers to show
- Generator passes parameters from config or CLI args

**Satisfies Constraints:**
- ✅ Extensible
- ✅ Reusable for multiple graph types

**Trade-offs:**
- ✅ PRO: One template for many use cases
- ✅ PRO: Very flexible
- ❌ CON: Complex template logic
- ❌ CON: Hard to debug

**Effort:** Medium-Large
**Risk:** Medium

---

### Approach S4.D: Multiple Specialized Templates with Shared Core

**Description:**
- Create graph core template: `_graph-core.md.j2` (partial/macro)
- Create specialized templates:
  - `unified-topology.md.j2` (all nodes + all edges)
  - `physical-deps.md.j2` (devices + host deps)
  - `service-deps.md.j2` (existing, enhanced)
  - `network-deps.md.j2` (VLANs + management)
- Each includes `_graph-core.md.j2` with specific parameters

**Satisfies Constraints:**
- ✅ DRY (shared core)
- ✅ Specialized outputs

**Trade-offs:**
- ✅ PRO: Template reuse
- ✅ PRO: Clear specialization
- ✅ PRO: Easy to add new graph types
- ❌ CON: More templates to maintain

**Effort:** Medium
**Risk:** Low

---

### Inadmissible Approach: JavaScript-Based Interactive Graph

**Why Inadmissible:**
- ❌ Violates C4.4 (output must be GitHub-flavored Markdown)
- ❌ Requires runtime JS (not static docs)
- ❌ Out of scope for Mermaid-based system

**Verdict:** NOT a solution (but could be future enhancement).

---

## SOLUTION SPACE 5: Testing Gaps (P2.5, P2.6)

### Problem: No tests for service_dependencies, no tests for ID sanitization consistency

### Approach S5.A: Add Contract Tests

**Description:**
- Add test in `test_projection_helpers.py`:
  - `test_docs_projection_includes_service_dependencies()`
  - `test_service_dependencies_schema()`
- Add test for ID sanitization:
  - `test_safe_id_consistency_across_templates()`
  - `test_safe_id_matches_projection()`

**Satisfies Constraints:**
- ✅ C9.1-C9.3 (test coverage)

**Trade-offs:**
- ✅ PRO: Prevents regression
- ✅ PRO: Documents contract
- ❌ CON: Requires test infrastructure setup

**Effort:** Small
**Risk:** None

---

### Approach S5.B: Snapshot Testing

**Description:**
- Use pytest snapshot testing
- Capture projection output once
- Fail if output changes

**Satisfies Constraints:**
- ✅ C9.3 (determinism)

**Trade-offs:**
- ✅ PRO: Auto-generates expected output
- ✅ PRO: Catches any change
- ❌ CON: Noisy (fails on valid changes too)
- ❌ CON: Requires manual snapshot update

**Effort:** Small
**Risk:** Low

---

### Approach S5.C: Property-Based Testing

**Description:**
- Use hypothesis library
- Generate random compiled_json fixtures
- Verify properties:
  - `_safe_id(x) == _safe_id(x)` (determinism)
  - `_safe_id(x)` contains only alphanumeric + `_`

**Satisfies Constraints:**
- ✅ C9.3 (determinism)
- ✅ C7.1 (safe ID format)

**Trade-offs:**
- ✅ PRO: Finds edge cases
- ✅ PRO: Mathematical rigor
- ❌ CON: Complex test setup
- ❌ CON: Slow test execution

**Effort:** Medium
**Risk:** Low

---

## SOLUTION SPACE 6: Documentation Gaps (P4.1, P4.2)

### Approach S6.A: Add Template Header Comments

**Description:**
- Add Jinja2 comment block at top of each template:
  ```jinja2
  {#
  Template: service-dependencies.md.j2
  Consumes: build_docs_projection()
  Required fields:
    - service_dependencies: list[dict]
      - service_id: str
      - depends_on: str
  #}
  ```

**Satisfies:** Documentation need
**Effort:** Small
**Risk:** None

---

### Approach S6.B: Generate Schema Docs from Code

**Description:**
- Add JSON Schema or TypedDict to projection functions
- Auto-generate documentation from schema

**Satisfies:** Documentation + runtime validation
**Effort:** Medium
**Risk:** Low

---

## SOLUTION COMBINATIONS FOR REQ-NEW

To implement REQ-NEW (Unified Topology Graph), we need:

### Combination C1: Conservative Path
- **S1.A** (safe_id in all projections)
- **S2.D** (new unified projection, keep old)
- **S3.B** (domain-specific dependency extractors)
- **S4.A** (new generator plugin)
- **S5.A** (contract tests)

**Total Effort:** Large
**Total Risk:** Low (no breaking changes)
**Pros:** Safe, backward compatible
**Cons:** More code to maintain

---

### Combination C2: Aggressive Refactor Path
- **S1.A** (safe_id everywhere)
- **S2.A** (unify projections into single builder)
- **S3.A** (extract all deps in projection)
- **S4.B** (extend diagram_generator)
- **S5.A** (tests)

**Total Effort:** Large
**Total Risk:** High (breaking changes)
**Pros:** Clean architecture, single source of truth
**Cons:** Breaking changes for both generators

---

### Combination C3: Hybrid Path
- **S1.C** (safe_id in projection + filter)
- **S2.B** (merger utility)
- **S3.B** (domain extractors)
- **S4.D** (specialized templates with shared core)
- **S5.A** (tests)

**Total Effort:** Large
**Total Risk:** Medium
**Pros:** Balance of safety and improvement
**Cons:** Some complexity

---

## Inadmissible Solution Patterns

**Pattern I1: Skip Projection Layer**
- Templates access compiled_json directly
- ❌ Violates ADR 0079, C2.6

**Pattern I2: Multiple Sanitization Functions**
- Different safe_id() implementations for different domains
- ❌ Violates C7.2

**Pattern I3: No Tests**
- Ship without regression tests
- ❌ Violates C9.1-C9.3

**Pattern I4: Break Existing Diagrams**
- Change existing templates without migration
- ❌ Violates C11.2 (backward compatibility)

---

## Constraint Compliance Matrix

| Solution | C1.8 | C2.6 | C7.2 | ADR 0005 | ADR 0079 | REQ-NEW |
|----------|------|------|------|----------|----------|---------|
| S1.A (safe_id in projection) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S1.B (Jinja2 filter) | ⚠️ | ❌ | ⚠️ | ❌ | ❌ | ❌ |
| S1.C (hybrid) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S2.A (unify projections) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S2.B (merger) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S2.D (new projection) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S3.A (extract all deps) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S3.B (domain extractors) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S4.A (new generator) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S4.D (shared core) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

**ADMISSIBLE SOLUTION SPACE COMPLETE** ✅

**Total Solution Approaches:** 19 across 6 problem areas
**Recommended Combinations:** 3 (Conservative, Aggressive, Hybrid)
**Inadmissible Patterns:** 4 (documented violations)

Ready for **STEP 6: MODEL REBUILD** (implementation)

**Recommendation for STEP 6:**
Use **Combination C1 (Conservative Path)** — safest, enables REQ-NEW without breaking existing code.

**GO STEP 6?**
