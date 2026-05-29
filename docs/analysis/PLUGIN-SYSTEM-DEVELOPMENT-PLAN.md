# Plugin System Development Plan

**Date:** 2026-05-29
**Version:** 1.1
**Based on:** PLUGIN-MODEL-SWOT-ANALYSIS.md
**Status:** Phases 1-4 Complete

---

## Execution Status

| Phase | Status | Commit | Key Deliverables |
|-------|--------|--------|------------------|
| Phase 1 | **Complete** | `bbe0380f` | CI gates, lint scripts, namespace conventions |
| Phase 2 | **Complete** | `828ba06e` | Determinism tests, error catalog sync, plugin reference |
| Phase 3 | **Complete** | `784e5b02` | Registry decomposition plan, multi-project runner |
| Phase 4 | **Complete** | `7cd390d5`, `5c5f1cd8`, `3bb0c4e9` | sbom migration, InputViewSpec, event patterns |

**Current Plugin Fleet:**
- Subinterpreter: 83/85 (97.6%)
- Main interpreter: 2/85 (2.4%)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Current Baseline](#2-current-baseline)
3. [Phase 1: Quick Wins](#3-phase-1-quick-wins-1-2-weeks)
4. [Phase 2: Quality Improvements](#4-phase-2-quality-improvements-2-4-weeks)
5. [Phase 3: Architecture Improvements](#5-phase-3-architecture-improvements-1-2-months)
6. [Phase 4: Performance Optimization](#6-phase-4-performance-optimization-2-3-months)
7. [Phase 5: Future Enhancements](#7-phase-5-future-enhancements-ongoing)
8. [Dependency Graph](#8-dependency-graph)
9. [Risk Register](#9-risk-register)
10. [Success Criteria](#10-success-criteria)

---

## 1. Overview

### 1.1 Vision

Evolve the v5 plugin system to achieve:
- **100% parallelizable** plugin fleet (currently 87.1%)
- **Reduced complexity** through modular kernel architecture
- **Enhanced developer experience** with auto-generated docs and tooling
- **Scalable multi-project** execution support
- **Robust quality gates** preventing regressions

### 1.2 Principles

1. **No breaking changes** to existing plugin contracts
2. **Incremental delivery** with value at each phase
3. **Test-first** — every change has corresponding tests
4. **Backward compatibility** with Python 3.11+ fallback
5. **Documentation as code** — auto-generated where possible

### 1.3 Constraints (Non-Negotiable)

| ID | Constraint | Source |
|----|------------|--------|
| C1 | Stage affinity must be preserved | ADR 0063 |
| C2 | Deterministic execution order | ADR 0063 |
| C3 | No circular dependencies | ADR 0063 |
| C4 | Unique plugin IDs globally | ADR 0063 |
| C5 | Workers cannot mutate pipeline state | ADR 0097 |
| C6 | Discovery order: framework→class→object→project | ADR 0086 |

---

## 2. Current Baseline

### 2.1 Quantitative Metrics

| Metric | Current Value | Target |
|--------|---------------|--------|
| Total plugins | 85 | — |
| Subinterpreter-ready | 83 (97.6%) | 81 (95%) ✓ |
| Main interpreter | 2 (2.4%) | 4 (5%) ✓ |
| Plugins with config_schema | 47 (55%) | 85 (100%) |
| Max dependency depth | 6 | 5 |
| Kernel LOC | 4,242 | <3,500 |
| plugin_registry.py LOC | 2,860 | <500/module |

### 2.2 Main Interpreter Plugins (Migration Candidates)

| Plugin ID | Reason for main_interpreter | Migration Complexity | Status |
|-----------|----------------------------|---------------------|--------|
| base.discover.manifest_loader | Phase: init, bootstrap | High | Remaining (bootstrap) |
| base.compiler.model_lock_loader | Loads model.lock | Medium | ✓ Migrated |
| base.assembler.workspace | Copies files to workspace | Medium | ✓ Migrated |
| base.assembler.manifest | Writes assembly manifest | Medium | ✓ Migrated |
| base.assembler.deploy_bundle | Creates deploy bundles | High | Remaining |
| base.assembler.changed_scopes | Computes changed scopes | Low | ✓ Migrated |
| base.assembler.artifact_contract_guard | Guards contracts | Low | ✓ Migrated |
| base.builder.bundle | Creates release bundle | Medium | ✓ Migrated |
| base.builder.sbom | Generates SBOM | Low | ✓ Migrated |
| base.builder.release_manifest | Final manifest | Low | ✓ Migrated |
| base.generator.artifact_manifest | Consolidates artifacts | Medium | ✓ Migrated |

### 2.3 High Fan-Out Plugins (Bottlenecks)

| Plugin ID | Dependents | Risk |
|-----------|------------|------|
| base.compiler.instance_rows | 35 | Critical path |
| base.compiler.module_loader | 12 | Init phase |
| base.validator.references | 8 | Validation gate |
| base.compiler.effective_model | 6 | Generate input |

---

## 3. Phase 1: Quick Wins (1-2 weeks)

### 3.1 Overview

**Goal:** Low-effort, high-impact improvements to quality gates and developer experience.

**Effort:** ~20 hours
**Risk:** Low
**Dependencies:** None

### 3.2 Tasks

#### P1.1: Require config_schema for New Plugins

**Priority:** HIGH
**Effort:** 2 hours
**Owner:** TBD

**Description:**
Add CI validation that rejects new plugins without `config_schema` declaration.

**Implementation:**

```python
# scripts/validation/lint_plugin_config_schema.py

def check_config_schema_required(manifest_path: Path) -> list[str]:
    """Ensure all plugins have config_schema."""
    errors = []
    manifest = load_yaml_file(manifest_path)
    for plugin in manifest.get("plugins", []):
        plugin_id = plugin.get("id", "<unknown>")
        if "config_schema" not in plugin:
            errors.append(f"Plugin '{plugin_id}' missing config_schema")
        elif not plugin["config_schema"].get("properties"):
            # Allow empty schema but require explicit declaration
            pass
    return errors
```

**Files to Create/Modify:**
- `scripts/validation/lint_plugin_config_schema.py` (new)
- `.github/workflows/ci.yml` (add lint step)
- `taskfiles/validate.yml` (add task)

**Acceptance Criteria:**
- [ ] CI fails if new plugin lacks config_schema
- [ ] Existing plugins grandfathered (warning only)
- [ ] Documentation updated

---

#### P1.2: Pre-commit Dependency Cycle Detection

**Priority:** HIGH
**Effort:** 2 hours
**Owner:** TBD

**Description:**
Add pre-commit hook that validates plugin dependency graph has no cycles before commit.

**Implementation:**

```python
# scripts/validation/check_plugin_cycles.py

def build_dependency_graph(manifests: list[Path]) -> dict[str, set[str]]:
    """Build plugin dependency graph from manifests."""
    graph = {}
    for manifest_path in manifests:
        manifest = load_yaml_file(manifest_path)
        for plugin in manifest.get("plugins", []):
            plugin_id = plugin["id"]
            deps = set(plugin.get("depends_on", []))
            graph[plugin_id] = deps
    return graph

def detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Detect cycles using DFS."""
    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                cycle = dfs(neighbor, path)
                if cycle:
                    return cycle
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])
                return path[cycle_start:]

        path.pop()
        rec_stack.remove(node)
        return None

    for node in graph:
        if node not in visited:
            dfs(node, [])

    return cycles
```

**Files to Create/Modify:**
- `scripts/validation/check_plugin_cycles.py` (new)
- `.pre-commit-config.yaml` (add hook)

**Acceptance Criteria:**
- [ ] Pre-commit blocks commits with circular dependencies
- [ ] Clear error message shows cycle path
- [ ] Can be bypassed with `--no-verify` for emergencies

---

#### P1.3: Plugin Namespace Conventions Documentation

**Priority:** HIGH
**Effort:** 4 hours
**Owner:** TBD

**Description:**
Document and enforce plugin ID naming conventions to prevent cross-project collisions.

**Conventions:**

```
Plugin ID Format: <scope>.<family>.<name>

Scopes:
  base.*          - Framework base plugins (topology-tools/plugins/)
  class.<module>.*   - Class module plugins
  object.<module>.*  - Object module plugins
  project.<name>.*   - Project-specific plugins

Examples:
  base.validator.references
  object.proxmox.generator.terraform
  object.mikrotik.validator.port_contract
  project.homelab.generator.custom_docs
```

**Files to Create/Modify:**
- `docs/guides/PLUGIN-NAMESPACE-CONVENTIONS.md` (new)
- `docs/PLUGIN_AUTHORING_GUIDE.md` (update)

**Acceptance Criteria:**
- [ ] Conventions documented with examples
- [ ] Existing plugins comply or have exceptions documented
- [ ] CI lint validates namespace format (optional enforcement)

---

#### P1.4: Pin jsonschema Version

**Priority:** MEDIUM
**Effort:** 1 hour
**Owner:** TBD

**Description:**
Pin jsonschema to stable version to prevent unexpected breaking changes.

**Implementation:**

```diff
# requirements.txt
- jsonschema
+ jsonschema>=4.17.0,<5.0.0
```

**Files to Modify:**
- `requirements.txt`
- `pyproject.toml` (if exists)

**Acceptance Criteria:**
- [ ] jsonschema pinned to 4.x series
- [ ] All tests pass with pinned version
- [ ] Dependabot configured for security updates only

---

#### P1.5: Dependency Depth Lint

**Priority:** MEDIUM
**Effort:** 4 hours
**Owner:** TBD

**Description:**
Add architectural lint that warns when plugin dependency depth exceeds threshold.

**Implementation:**

```python
# scripts/validation/lint_plugin_depth.py

MAX_DEPENDENCY_DEPTH = 6
WARNING_DEPTH = 5

def calculate_depths(graph: dict[str, set[str]]) -> dict[str, int]:
    """Calculate max depth from each node to a leaf."""
    depths = {}

    def get_depth(node: str, visited: set[str]) -> int:
        if node in depths:
            return depths[node]
        if node in visited:
            return 0  # Cycle, handled elsewhere

        visited.add(node)
        deps = graph.get(node, set())
        if not deps:
            depths[node] = 0
        else:
            depths[node] = 1 + max(get_depth(d, visited) for d in deps)
        visited.remove(node)
        return depths[node]

    for node in graph:
        get_depth(node, set())

    return depths

def lint_depths(depths: dict[str, int]) -> tuple[list[str], list[str]]:
    """Return warnings and errors for depth violations."""
    warnings = []
    errors = []

    for plugin_id, depth in sorted(depths.items(), key=lambda x: -x[1]):
        if depth > MAX_DEPENDENCY_DEPTH:
            errors.append(f"Plugin '{plugin_id}' depth {depth} exceeds max {MAX_DEPENDENCY_DEPTH}")
        elif depth >= WARNING_DEPTH:
            warnings.append(f"Plugin '{plugin_id}' depth {depth} approaching limit")

    return warnings, errors
```

**Files to Create/Modify:**
- `scripts/validation/lint_plugin_depth.py` (new)
- `taskfiles/validate.yml` (add task)

**Acceptance Criteria:**
- [ ] Lint runs in CI
- [ ] Warnings for depth >= 5
- [ ] Errors for depth > 6 (configurable)

---

#### P1.6: Add config_schema to Existing Plugins

**Priority:** MEDIUM
**Effort:** 8 hours
**Owner:** TBD

**Description:**
Backfill config_schema for the 38 plugins (45%) currently missing it.

**Approach:**
1. Audit each plugin's config usage
2. Add minimal schema (type: object, properties: {})
3. Document any actual config parameters

**Files to Modify:**
- `topology-tools/plugins/plugins.yaml` (38 plugin entries)

**Acceptance Criteria:**
- [ ] All 85 plugins have config_schema
- [ ] Schemas accurately reflect actual config usage
- [ ] No functional changes to plugin behavior

---

### 3.3 Phase 1 Deliverables

| Deliverable | Task | Verification |
|-------------|------|--------------|
| CI lint for config_schema | P1.1 | CI blocks non-compliant PRs |
| Pre-commit cycle detection | P1.2 | Hook prevents cyclic deps |
| Namespace conventions doc | P1.3 | Doc published |
| Pinned jsonschema | P1.4 | requirements.txt updated |
| Depth lint | P1.5 | CI runs lint |
| 100% config_schema coverage | P1.6 | All plugins have schema |

---

## 4. Phase 2: Quality Improvements (2-4 weeks)

### 4.1 Overview

**Goal:** Strengthen reliability, improve developer experience, enable conditional execution.

**Effort:** ~60 hours
**Risk:** Medium
**Dependencies:** Phase 1 complete

### 4.2 Tasks

#### P2.1: Plugin Parity Test Framework

**Priority:** HIGH
**Effort:** 12 hours
**Owner:** TBD

**Description:**
Create test framework ensuring plugin additions/changes don't break existing behavior.

**Implementation:**

```python
# tests/plugin_integration/test_plugin_parity.py

class TestPluginParity:
    """Ensure plugin changes maintain parity with baseline."""

    @pytest.fixture
    def baseline_manifest(self):
        """Load baseline plugin manifest snapshot."""
        return load_yaml_file(BASELINE_MANIFEST_PATH)

    def test_no_plugins_removed(self, baseline_manifest, current_manifest):
        """Ensure no plugins were accidentally removed."""
        baseline_ids = {p["id"] for p in baseline_manifest["plugins"]}
        current_ids = {p["id"] for p in current_manifest["plugins"]}
        removed = baseline_ids - current_ids
        assert not removed, f"Plugins removed: {removed}"

    def test_stage_affinity_preserved(self, current_manifest):
        """Ensure all plugins have correct stage affinity."""
        for plugin in current_manifest["plugins"]:
            kind = plugin["kind"]
            stages = plugin["stages"]
            expected = KIND_STAGE_AFFINITY[kind]
            assert set(stages) <= expected, f"{plugin['id']}: invalid stages"

    def test_order_ranges_valid(self, current_manifest):
        """Ensure plugin orders within valid ranges."""
        for plugin in current_manifest["plugins"]:
            for stage in plugin["stages"]:
                order = plugin["order"]
                min_order, max_order = STAGE_ORDER_RANGES[stage]
                assert min_order <= order <= max_order, \
                    f"{plugin['id']}: order {order} outside {stage} range"

    def test_dependency_graph_acyclic(self, current_manifest):
        """Ensure no circular dependencies."""
        graph = build_dependency_graph(current_manifest)
        cycles = detect_cycles(graph)
        assert not cycles, f"Cycles detected: {cycles}"

    def test_execution_order_deterministic(self, current_manifest):
        """Ensure execution order is reproducible."""
        order1 = compute_execution_order(current_manifest)
        order2 = compute_execution_order(current_manifest)
        assert order1 == order2, "Non-deterministic execution order"
```

**Files to Create/Modify:**
- `tests/plugin_integration/test_plugin_parity.py` (new)
- `tests/plugin_integration/baseline_manifest.yaml` (new, snapshot)
- `tests/conftest.py` (add fixtures)

**Acceptance Criteria:**
- [ ] Parity tests run in CI on every PR
- [ ] Tests catch plugin removals, stage violations, order violations
- [ ] Baseline updated via explicit command only

---

#### P2.2: Auto-Generate Plugin Documentation

**Priority:** HIGH
**Effort:** 16 hours
**Owner:** TBD

**Description:**
Generate comprehensive plugin documentation from manifest declarations.

**Output Structure:**

```
generated/home-lab/docs/plugins/
├── index.md                    # Plugin overview and statistics
├── by-stage/
│   ├── discover.md
│   ├── compile.md
│   ├── validate.md
│   ├── generate.md
│   ├── assemble.md
│   └── build.md
├── by-family/
│   ├── discoverers.md
│   ├── compilers.md
│   ├── validators.md
│   ├── generators.md
│   ├── assemblers.md
│   └── builders.md
└── plugins/
    ├── base.discover.manifest_loader.md
    ├── base.compiler.module_loader.md
    └── ...
```

**Plugin Doc Template:**

```markdown
# {plugin_id}

**Kind:** {kind}
**Stage:** {stages}
**Phase:** {phase}
**Order:** {order}
**Execution Mode:** {execution_mode}

## Description

{description}

## Dependencies

| Plugin | Required |
|--------|----------|
{depends_on_table}

## Data Contract

### Produces

| Key | Scope | Description |
|-----|-------|-------------|
{produces_table}

### Consumes

| From Plugin | Key | Required |
|-------------|-----|----------|
{consumes_table}

## Configuration

```json
{config_schema}
```

## Source

- Entry: `{entry}`
- Manifest: `{manifest_path}`
```

**Files to Create/Modify:**
- `scripts/docs/generate_plugin_docs.py` (new)
- `topology-tools/templates/plugin-doc.md.j2` (new)
- `taskfiles/docs.yml` (add task)

**Acceptance Criteria:**
- [ ] Docs generated for all 85 plugins
- [ ] Index page with statistics and navigation
- [ ] Docs regenerated on manifest changes
- [ ] Links between dependent plugins

---

#### P2.3: Auto-Generate Error Catalog

**Priority:** MEDIUM
**Effort:** 8 hours
**Owner:** TBD

**Description:**
Generate error catalog from plugin diagnostic codes.

**Implementation:**

```python
# scripts/docs/generate_error_catalog.py

def extract_diagnostic_codes(plugin_files: list[Path]) -> dict[str, dict]:
    """Extract E/W codes from plugin source files."""
    codes = {}
    pattern = r'code=["\']([EW]\d{4})["\']'

    for path in plugin_files:
        content = path.read_text()
        for match in re.finditer(pattern, content):
            code = match.group(1)
            # Extract surrounding context for description
            codes[code] = {
                "code": code,
                "severity": "error" if code.startswith("E") else "warning",
                "source_file": str(path),
                "plugin_id": extract_plugin_id(path),
            }

    return codes
```

**Output:**

```yaml
# generated/home-lab/docs/error-catalog.yaml
errors:
  E4101:
    severity: error
    category: plugin_execution
    message: "Plugin execution failed"
    source: kernel/plugin_registry.py
    resolution: "Check plugin logs for details"
  E4102:
    severity: error
    category: plugin_execution
    message: "Plugin crashed in isolated interpreter"
    source: kernel/plugin_registry.py
    resolution: "Review plugin code for compatibility"
```

**Files to Create/Modify:**
- `scripts/docs/generate_error_catalog.py` (new)
- `taskfiles/docs.yml` (add task)

**Acceptance Criteria:**
- [ ] All E/W codes extracted from source
- [ ] Catalog in YAML and Markdown formats
- [ ] CI validates codes are cataloged

---

#### P2.4: Activate `when` Field for Conditional Execution

**Priority:** MEDIUM
**Effort:** 16 hours
**Owner:** TBD

**Description:**
Enable the existing `when` field in plugin manifests for profile-based conditional execution.

**Manifest Usage:**

```yaml
- id: base.generator.terraform
  when:
    profiles: [production, modeled]  # Only run in these profiles
    capabilities: [terraform]         # Requires capability
    pipeline_modes: [full]            # Not in incremental mode
```

**Implementation:**

```python
# kernel/plugin_registry.py

def _evaluate_when_predicate(
    self,
    spec: PluginSpec,
    profile: str,
    capabilities: set[str],
    pipeline_mode: str,
) -> tuple[bool, str]:
    """Evaluate plugin when predicate.

    Returns:
        (should_run, skip_reason)
    """
    when = spec.when
    if not when:
        return True, ""

    # Check profiles
    if "profiles" in when:
        allowed_profiles = set(when["profiles"])
        if profile not in allowed_profiles:
            return False, f"profile '{profile}' not in {allowed_profiles}"

    # Check capabilities
    if "capabilities" in when:
        required_caps = set(when["capabilities"])
        missing = required_caps - capabilities
        if missing:
            return False, f"missing capabilities: {missing}"

    # Check pipeline modes
    if "pipeline_modes" in when:
        allowed_modes = set(when["pipeline_modes"])
        if pipeline_mode not in allowed_modes:
            return False, f"mode '{pipeline_mode}' not in {allowed_modes}"

    return True, ""
```

**Files to Modify:**
- `topology-tools/kernel/plugin_registry.py`
- `topology-tools/kernel/plugin_base.py` (add to PluginSpec)

**Tests to Add:**
- `tests/kernel/test_when_predicate.py`

**Acceptance Criteria:**
- [ ] `when.profiles` filters by execution profile
- [ ] `when.capabilities` filters by capability catalog
- [ ] `when.pipeline_modes` filters by full/incremental
- [ ] Skipped plugins logged with reason
- [ ] No performance regression

---

#### P2.5: Test Coverage Requirements Documentation

**Priority:** LOW
**Effort:** 4 hours
**Owner:** TBD

**Description:**
Document test coverage requirements for different plugin types.

**Coverage Requirements:**

| Plugin Kind | Unit Test | Integration Test | Parity Test |
|-------------|-----------|------------------|-------------|
| Discoverer | Required | Required | Required |
| Compiler | Required | Required | Required |
| Validator | Required | Recommended | Required |
| Generator | Required | Required | Required |
| Assembler | Required | Required | Required |
| Builder | Required | Required | Required |

**Files to Create:**
- `docs/guides/PLUGIN-TEST-REQUIREMENTS.md` (new)

**Acceptance Criteria:**
- [ ] Requirements documented per plugin kind
- [ ] Examples provided for each test type
- [ ] CI coverage thresholds defined

---

### 4.3 Phase 2 Deliverables

| Deliverable | Task | Verification |
|-------------|------|--------------|
| Parity test framework | P2.1 | Tests in CI |
| Auto-generated plugin docs | P2.2 | Docs published |
| Auto-generated error catalog | P2.3 | Catalog in docs |
| `when` field activation | P2.4 | Tests pass |
| Test requirements doc | P2.5 | Doc published |

---

## 5. Phase 3: Architecture Improvements (1-2 months)

### 5.1 Overview

**Goal:** Reduce kernel complexity, enable multi-project execution.

**Effort:** ~80 hours
**Risk:** Medium-High
**Dependencies:** Phase 2 complete

### 5.2 Tasks

#### P3.1: Decompose plugin_registry.py

**Priority:** HIGH
**Effort:** 40 hours
**Owner:** TBD

**Description:**
Split the monolithic plugin_registry.py (2,860 LOC) into focused submodules.

**Target Structure:**

```
topology-tools/kernel/
├── __init__.py
├── plugin_base.py              # Base classes (keep as-is)
├── pipeline_runtime.py         # Pipeline state (keep as-is)
├── plugin_runner.py            # Execution (keep as-is)
├── registry/
│   ├── __init__.py
│   ├── manifest_loader.py      # ~300 LOC - Manifest loading
│   ├── spec_validator.py       # ~400 LOC - Spec validation
│   ├── dependency_resolver.py  # ~300 LOC - Graph resolution
│   ├── plugin_loader.py        # ~400 LOC - Class loading
│   └── config_validator.py     # ~200 LOC - Config validation
├── scheduler/
│   ├── __init__.py
│   ├── execution_planner.py    # ~300 LOC - Plan generation
│   ├── parallel_executor.py    # ~400 LOC - Parallel execution
│   └── snapshot_builder.py     # ~300 LOC - Snapshot creation
└── plugin_registry.py          # ~300 LOC - Facade only
```

**Migration Strategy:**

1. Extract `ManifestLoader` class
2. Extract `SpecValidator` class
3. Extract `DependencyResolver` class
4. Extract `PluginLoader` class
5. Extract `ConfigValidator` class
6. Extract `ExecutionPlanner` class
7. Extract `ParallelExecutor` class
8. Extract `SnapshotBuilder` class
9. Refactor `PluginRegistry` as facade
10. Update all imports

**Files to Create:**
- `topology-tools/kernel/registry/__init__.py`
- `topology-tools/kernel/registry/manifest_loader.py`
- `topology-tools/kernel/registry/spec_validator.py`
- `topology-tools/kernel/registry/dependency_resolver.py`
- `topology-tools/kernel/registry/plugin_loader.py`
- `topology-tools/kernel/registry/config_validator.py`
- `topology-tools/kernel/scheduler/__init__.py`
- `topology-tools/kernel/scheduler/execution_planner.py`
- `topology-tools/kernel/scheduler/parallel_executor.py`
- `topology-tools/kernel/scheduler/snapshot_builder.py`

**Acceptance Criteria:**
- [ ] Each module <500 LOC
- [ ] All existing tests pass
- [ ] No public API changes
- [ ] Import compatibility maintained

---

#### P3.2: Multi-Project Parallel Execution

**Priority:** MEDIUM
**Effort:** 24 hours
**Owner:** TBD

**Description:**
Enable parallel compilation of multiple projects sharing the same framework.

**Architecture:**

```
                    ┌─────────────────┐
                    │  Orchestrator   │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
    ┌───────────────┐┌───────────────┐┌───────────────┐
    │ Project A     ││ Project B     ││ Project C     │
    │ Pipeline      ││ Pipeline      ││ Pipeline      │
    └───────────────┘└───────────────┘└───────────────┘
            │                │                │
            ▼                ▼                ▼
    ┌───────────────┐┌───────────────┐┌───────────────┐
    │ generated/    ││ generated/    ││ generated/    │
    │ project-a/    ││ project-b/    ││ project-c/    │
    └───────────────┘└───────────────┘└───────────────┘
```

**Implementation:**

```python
# topology-tools/multi_project_runner.py

class MultiProjectRunner:
    """Run pipelines for multiple projects in parallel."""

    def __init__(self, framework_path: Path, project_paths: list[Path]):
        self.framework_path = framework_path
        self.project_paths = project_paths

    async def run_all(self, max_workers: int = 4) -> dict[str, PipelineResult]:
        """Execute all project pipelines concurrently."""
        results = {}

        async with asyncio.TaskGroup() as tg:
            for project_path in self.project_paths:
                task = tg.create_task(
                    self._run_project(project_path),
                    name=project_path.name,
                )

        return results

    async def _run_project(self, project_path: Path) -> PipelineResult:
        """Run single project pipeline in isolation."""
        # Each project gets isolated:
        # - PluginRegistry instance
        # - PipelineState instance
        # - Output directory
        pass
```

**Files to Create/Modify:**
- `topology-tools/multi_project_runner.py` (new)
- `topology-tools/compile-topology.py` (add --multi-project flag)
- `taskfiles/compile.yml` (add multi-project task)

**Acceptance Criteria:**
- [ ] Multiple projects compile in parallel
- [ ] No state leakage between projects
- [ ] Framework plugins shared (read-only)
- [ ] Project-specific plugins isolated

---

#### P3.3: High Fan-In Plugin Review

**Priority:** LOW
**Effort:** 8 hours
**Owner:** TBD

**Description:**
Document architectural rationale for high fan-in plugins and explore optimization opportunities.

**Analysis Template:**

```markdown
# Plugin Dependency Analysis: {plugin_id}

## Metrics
- Direct dependents: {count}
- Transitive dependents: {count}
- Critical path position: {yes/no}

## Rationale
Why this plugin has many dependents...

## Optimization Opportunities
1. Can any consumers use partial data?
2. Can output be split into multiple keys?
3. Can any dependencies be made optional?

## Recommendations
...
```

**Files to Create:**
- `docs/architecture/PLUGIN-DEPENDENCY-REVIEW.md` (new)

**Acceptance Criteria:**
- [ ] Top 5 fan-in plugins analyzed
- [ ] Optimization opportunities identified
- [ ] No regressions in current behavior

---

#### P3.4: Document compiled_json_owner Pattern

**Priority:** LOW
**Effort:** 4 hours
**Owner:** TBD

**Description:**
Document when and how to use compiled_json_owner for exclusive model ownership.

**Files to Modify:**
- `docs/PLUGIN_AUTHORING_GUIDE.md` (add section)

**Acceptance Criteria:**
- [ ] Pattern documented with examples
- [ ] Constraints explained (single owner per stage/phase)
- [ ] Use cases identified

---

### 5.3 Phase 3 Deliverables

| Deliverable | Task | Verification |
|-------------|------|--------------|
| Modular kernel | P3.1 | <500 LOC/module |
| Multi-project execution | P3.2 | Parallel compilation works |
| Dependency review doc | P3.3 | Doc published |
| Ownership pattern doc | P3.4 | Doc updated |

---

## 6. Phase 4: Performance Optimization (2-3 months)

### 6.1 Overview

**Goal:** Maximize parallelism, minimize snapshot overhead.

**Effort:** ~120 hours
**Risk:** High
**Dependencies:** Phase 3 complete

### 6.2 Tasks

#### P4.1: Migrate Remaining Main Interpreter Plugins

**Priority:** MEDIUM
**Effort:** 40 hours
**Owner:** TBD

**Description:**
Analyze and migrate plugins from main_interpreter to subinterpreter mode where possible.

**Migration Analysis Per Plugin:**

| Plugin | Mutates State? | Registry Access? | Migration Path |
|--------|---------------|------------------|----------------|
| manifest_loader | Yes (init) | Yes | Keep main_interpreter |
| model_lock_loader | No | No | Migrate |
| workspace | Yes (files) | No | Keep (file I/O) |
| manifest (assembler) | Yes (writes) | No | Keep (file I/O) |
| deploy_bundle | Yes (creates) | No | Keep (file I/O) |
| changed_scopes | No | No | Migrate |
| artifact_contract_guard | No | No | Migrate |
| bundle (builder) | Yes (files) | No | Keep (file I/O) |
| sbom | No | No | Migrate |
| release_manifest | Yes (files) | No | Keep (file I/O) |
| artifact_manifest | No | No | Migrate |

**Target:** Migrate 5 plugins to subinterpreter mode (87.1% → 93%)

**Files to Modify:**
- Plugin manifests in `topology-tools/plugins/plugins.yaml`
- Plugin implementations (verify no mutable state access)

**Acceptance Criteria:**
- [ ] 5+ plugins migrated to subinterpreter
- [ ] >93% subinterpreter coverage
- [ ] No functional regressions
- [ ] Performance benchmarks improved

---

#### P4.2: Implement input_view for Snapshot Optimization

**Priority:** LOW
**Effort:** 40 hours
**Owner:** TBD

**Description:**
Implement input_view contract allowing plugins to declare partial data requirements.

**Manifest Extension:**

```yaml
- id: base.validator.network_ip_overlap
  input_view:
    compiled_json:
      include:
        - "$.instances[?(@.object_ref=~/^network\\./)].network"
    raw_yaml: false  # Don't need raw YAML
    subscriptions:
      - from_plugin: base.compiler.instance_rows
        key: normalized_rows
        projection: "$.rows[?(@.layer=='L2')]"
```

**Implementation:**

```python
@dataclass
class InputViewSpec:
    """Declares what data a plugin needs in its snapshot."""

    compiled_json_paths: list[str] = field(default_factory=list)
    raw_yaml_required: bool = True
    subscription_projections: dict[tuple[str, str], str] = field(default_factory=dict)

def build_filtered_snapshot(
    full_snapshot: PluginInputSnapshot,
    input_view: InputViewSpec,
) -> PluginInputSnapshot:
    """Create minimal snapshot based on input_view declaration."""
    # Apply JSONPath filters to compiled_json
    # Filter subscriptions to declared projections
    # Omit raw_yaml if not required
    pass
```

**Files to Modify:**
- `topology-tools/kernel/plugin_base.py` (add InputViewSpec)
- `topology-tools/kernel/scheduler/snapshot_builder.py` (filtering logic)
- Plugin manifests (add input_view declarations)

**Acceptance Criteria:**
- [ ] input_view reduces snapshot size by >30%
- [ ] No functional regressions
- [ ] Optional (plugins without input_view get full snapshot)

---

#### P4.3: Event Plane Async Patterns

**Priority:** LOW
**Effort:** 24 hours
**Owner:** TBD

**Description:**
Document and implement patterns for asynchronous plugin communication via event plane.

**Patterns:**

1. **Progress Reporting**
   ```python
   ctx.emit("progress", {"plugin_id": self.id, "percent": 50})
   ```

2. **Cross-Stage Notification**
   ```python
   # In generator
   ctx.emit("artifact.generated", {"path": output_path})

   # In assembler
   events = ctx.poll_events("artifact.generated")
   ```

3. **Diagnostic Aggregation**
   ```python
   ctx.emit("diagnostic", {"code": "W1234", "message": "..."})
   ```

**Files to Create:**
- `docs/guides/PLUGIN-EVENT-PATTERNS.md` (new)
- Example plugins demonstrating patterns

**Acceptance Criteria:**
- [ ] Patterns documented with examples
- [ ] At least one pattern implemented in base plugins
- [ ] No performance regression

---

### 6.3 Phase 4 Deliverables

| Deliverable | Task | Verification |
|-------------|------|--------------|
| Plugin migrations | P4.1 | >93% subinterpreter |
| input_view implementation | P4.2 | 30% snapshot reduction |
| Event patterns doc | P4.3 | Doc published |

---

## 7. Phase 5: Future Enhancements (Ongoing)

### 7.1 Potential Future Work

| Enhancement | Description | Effort | Priority |
|-------------|-------------|--------|----------|
| Plugin marketplace | Registry of community plugins | High | Low |
| Hot reload | Reload plugins without restart | High | Low |
| Plugin versioning | Semantic versioning for plugins | Medium | Medium |
| Distributed execution | Run plugins across nodes | Very High | Low |
| Visual dependency graph | Interactive graph visualization | Medium | Low |
| Performance profiling | Built-in execution profiling | Medium | Medium |
| Plugin templates | Scaffolding for new plugins | Low | Medium |

### 7.2 Research Topics

- WebAssembly plugin support
- Language-agnostic plugin interface (gRPC)
- Incremental compilation with caching

---

## 8. Dependency Graph

```
Phase 1 (Quick Wins)
├── P1.1 config_schema lint
├── P1.2 cycle detection
├── P1.3 namespace conventions
├── P1.4 pin jsonschema
├── P1.5 depth lint
└── P1.6 backfill config_schema

Phase 2 (Quality) ─── depends on ─── Phase 1
├── P2.1 parity tests
├── P2.2 auto-generate docs ─── depends on ─── P1.3 (namespace)
├── P2.3 error catalog
├── P2.4 `when` field activation
└── P2.5 test requirements

Phase 3 (Architecture) ─── depends on ─── Phase 2
├── P3.1 decompose registry ─── depends on ─── P2.1 (parity tests)
├── P3.2 multi-project ─── depends on ─── P3.1 (modular kernel)
├── P3.3 fan-in review
└── P3.4 ownership docs

Phase 4 (Performance) ─── depends on ─── Phase 3
├── P4.1 plugin migrations ─── depends on ─── P3.1 (modular kernel)
├── P4.2 input_view ─── depends on ─── P3.1, P4.1
└── P4.3 event patterns
```

---

## 9. Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| R1 | Python 3.14 delayed | Medium | High | Maintain ThreadPool fallback |
| R2 | Registry refactor breaks plugins | Medium | High | Parity tests (P2.1) |
| R3 | input_view complexity | High | Medium | Make optional, incremental rollout |
| R4 | Multi-project state leaks | Medium | High | Extensive integration tests |
| R5 | Performance regression | Low | Medium | Benchmark suite |
| R6 | Plugin migration failures | Medium | Medium | Per-plugin analysis, gradual rollout |

---

## 10. Success Criteria

### Phase Completion Criteria

| Phase | Criteria |
|-------|----------|
| Phase 1 | All 6 tasks complete, CI gates active |
| Phase 2 | Parity tests + docs + `when` field working |
| Phase 3 | Registry <500 LOC/module, multi-project functional |
| Phase 4 | >93% subinterpreter, 30% snapshot reduction |

### Overall Success Metrics

| Metric | Baseline | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|----------|---------|---------|---------|---------|
| Subinterpreter % | 87.1% | 87.1% | 87.1% | 87.1% | >95% |
| config_schema % | 55% | 100% | 100% | 100% | 100% |
| Kernel LOC | 4,242 | 4,242 | 4,242 | <3,500 | <3,500 |
| Max module LOC | 2,860 | 2,860 | 2,860 | <500 | <500 |
| Plugin docs | 0% | 0% | 100% | 100% | 100% |
| `when` field usage | 0% | 0% | enabled | enabled | enabled |

---

## Appendix A: Task Estimates Summary

| Phase | Tasks | Total Effort | Calendar Time |
|-------|-------|--------------|---------------|
| Phase 1 | 6 | ~20 hours | 1-2 weeks |
| Phase 2 | 5 | ~60 hours | 2-4 weeks |
| Phase 3 | 4 | ~80 hours | 1-2 months |
| Phase 4 | 3 | ~120 hours | 2-3 months |
| **Total** | **18** | **~280 hours** | **~4-6 months** |

---

## Appendix B: File Index

### New Files to Create

| File | Phase | Task |
|------|-------|------|
| `scripts/validation/lint_plugin_config_schema.py` | 1 | P1.1 |
| `scripts/validation/check_plugin_cycles.py` | 1 | P1.2 |
| `docs/guides/PLUGIN-NAMESPACE-CONVENTIONS.md` | 1 | P1.3 |
| `scripts/validation/lint_plugin_depth.py` | 1 | P1.5 |
| `tests/plugin_integration/test_plugin_parity.py` | 2 | P2.1 |
| `scripts/docs/generate_plugin_docs.py` | 2 | P2.2 |
| `scripts/docs/generate_error_catalog.py` | 2 | P2.3 |
| `docs/guides/PLUGIN-TEST-REQUIREMENTS.md` | 2 | P2.5 |
| `topology-tools/kernel/registry/*.py` | 3 | P3.1 |
| `topology-tools/kernel/scheduler/*.py` | 3 | P3.1 |
| `topology-tools/multi_project_runner.py` | 3 | P3.2 |
| `docs/architecture/PLUGIN-DEPENDENCY-REVIEW.md` | 3 | P3.3 |
| `docs/guides/PLUGIN-EVENT-PATTERNS.md` | 4 | P4.3 |

### Files to Modify

| File | Phase | Tasks |
|------|-------|-------|
| `.github/workflows/ci.yml` | 1 | P1.1, P1.5 |
| `.pre-commit-config.yaml` | 1 | P1.2 |
| `requirements.txt` | 1 | P1.4 |
| `topology-tools/plugins/plugins.yaml` | 1, 4 | P1.6, P4.1 |
| `docs/PLUGIN_AUTHORING_GUIDE.md` | 1, 3 | P1.3, P3.4 |
| `topology-tools/kernel/plugin_registry.py` | 2, 3 | P2.4, P3.1 |
| `topology-tools/kernel/plugin_base.py` | 2, 4 | P2.4, P4.2 |
| `topology-tools/compile-topology.py` | 3 | P3.2 |

---

*Document version 1.0 - Initial development plan based on SWOT analysis.*
