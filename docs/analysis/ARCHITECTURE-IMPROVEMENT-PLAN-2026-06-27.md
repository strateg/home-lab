# Architecture Improvement Plan

**Date:** 2026-06-27
**Source:** Architecture Analysis `ARCHITECTURE-ANALYSIS-2026-06-27.md`
**Status:** Superseded by `ARCHITECTURE-IMPROVEMENT-PLAN-2026-07-07.md` (2026-07-07)
**Analyst:** Claude Code (claude-opus-4-5-20251101)

> Disposition (2026-07-07): Phases 1-3, P4.1 and P4.6 completed (evidence in the
> superseding plan, section 4); the "<200 LOC orchestrator" metric and P4.5 are
> retired; P4.2/P4.3/P4.7 carried over as H1.5/H2.5, P4.4 remains open (low
> priority).

---

## Approved Roadmap Overview

```
PHASE 1: COMPILER DECOMPOSITION (Critical) ....... HIGH PRIORITY
PHASE 2: CONFIGURATION SHARDING (Critical) ....... HIGH PRIORITY
PHASE 3: CAPABILITY-DRIVEN ARCH (Critical) ....... MEDIUM PRIORITY
PHASE 4: HOUSEKEEPING & GOVERNANCE ............... LOW PRIORITY
```

---

## Phase 1: Compiler Decomposition

**Priority:** Critical
**Effort Estimate:** 16-24 hours
**Dependencies:** None
**Risk:** Medium (requires careful refactoring)

### Objective

Decompose `compile-topology.py` (1828 LOC) into focused modules following SRP.

### Tasks

| ID | Task | Description | Verification |
|----|------|-------------|--------------|
| P1.1 | Extract AiSessionManager | Move AI advisory/assisted session logic | Unit tests pass |
| P1.2 | Extract FrameworkLockVerifier | Move framework lock verification | Unit tests pass |
| P1.3 | Extract PluginRegistryManager | Move plugin loading and registry | Unit tests pass |
| P1.4 | Extract DiagnosticsManager | Move diagnostics and reporting | Unit tests pass |
| P1.5 | Create CompilerOrchestrator | Thin orchestrator delegating to managers | Integration tests pass |
| P1.6 | Update imports | Update all import references | `task ci:local` passes |

### Target Structure

```
topology-tools/
├── compile-topology.py          # Entry point (~100 LOC)
├── compiler/
│   ├── __init__.py
│   ├── orchestrator.py          # CompilerOrchestrator (~200 LOC)
│   ├── ai_session_manager.py    # AI sessions (~300 LOC)
│   ├── framework_lock.py        # Lock verification (~150 LOC)
│   ├── plugin_registry.py       # Plugin management (~400 LOC)
│   ├── diagnostics.py           # Diagnostics (~300 LOC)
│   └── stage_runner.py          # Stage execution (~400 LOC)
```

### Implementation Steps

#### P1.1: Extract AiSessionManager

```python
# compiler/ai_session_manager.py
class AiSessionManager:
    """Manages AI advisory and assisted compilation sessions."""

    def __init__(self, config: CompilerConfig):
        self.config = config
        self.session_mode = None

    def start_advisory_session(self) -> AiAdvisorySession:
        """Start AI advisory mode for compilation guidance."""
        ...

    def start_assisted_session(self) -> AiAssistedSession:
        """Start AI assisted mode for automated fixes."""
        ...
```

#### P1.2: Extract FrameworkLockVerifier

```python
# compiler/framework_lock.py
class FrameworkLockVerifier:
    """Verifies framework lock file integrity."""

    def verify(self, lock_path: Path) -> VerificationResult:
        """Verify lock file matches framework state."""
        ...

    def update_lock(self, lock_path: Path) -> None:
        """Update lock file after successful compilation."""
        ...
```

#### P1.3: Extract PluginRegistryManager

```python
# compiler/plugin_registry.py
class PluginRegistryManager:
    """Manages plugin discovery, loading, and execution."""

    def load_plugins(self, manifest_path: Path) -> PluginRegistry:
        """Load plugins from manifest."""
        ...

    def resolve_dependencies(self, plugins: List[Plugin]) -> List[Plugin]:
        """Resolve plugin dependencies and ordering."""
        ...
```

### Validation

```bash
# After Phase 1 completion
pytest tests/unit/compiler/ -v
pytest tests/integration/ -v
task ci:local
```

---

## Phase 2: Configuration Sharding

**Priority:** Critical
**Effort Estimate:** 8-12 hours
**Dependencies:** None (can run parallel with Phase 1)
**Risk:** Low

### Objective

Shard `plugins.yaml` (2934 lines) into domain-specific manifests.

### Tasks

| ID | Task | Description | Verification |
|----|------|-------------|--------------|
| P2.1 | Create manifest structure | Create `plugins/manifests/` directory | Directory exists |
| P2.2 | Extract discoverers | Move discoverer plugins to separate file | YAML valid |
| P2.3 | Extract compilers | Move compiler plugins to separate file | YAML valid |
| P2.4 | Extract validators | Move validator plugins to separate file | YAML valid |
| P2.5 | Extract generators | Move generator plugins to separate file | YAML valid |
| P2.6 | Extract assemblers | Move assembler plugins to separate file | YAML valid |
| P2.7 | Extract builders | Move builder plugins to separate file | YAML valid |
| P2.8 | Create manifest loader | Update plugin loader for multi-file | All tests pass |
| P2.9 | Update plugins.yaml | Reference manifests, keep metadata | Backwards compatible |

### Target Structure

```
topology-tools/plugins/
├── plugins.yaml                  # Root manifest with includes (~100 lines)
├── manifests/
│   ├── discoverers.yaml         # Stage 1 plugins (~300 lines)
│   ├── compilers.yaml           # Stage 2 plugins (~500 lines)
│   ├── validators.yaml          # Stage 3 plugins (~600 lines)
│   ├── generators.yaml          # Stage 4 plugins (~800 lines)
│   ├── assemblers.yaml          # Stage 5 plugins (~400 lines)
│   └── builders.yaml            # Stage 6 plugins (~300 lines)
└── schemas/
    └── plugin-manifest.schema.yaml
```

### Root Manifest Format

```yaml
# plugins/plugins.yaml (after sharding)
version: "2.0"
schema_version: "1.0"

includes:
  - manifests/discoverers.yaml
  - manifests/compilers.yaml
  - manifests/validators.yaml
  - manifests/generators.yaml
  - manifests/assemblers.yaml
  - manifests/builders.yaml

global_settings:
  default_timeout: 30
  parallel_execution: true

metadata:
  last_updated: 2026-06-27
  total_plugins: 98
```

### Validation

```bash
# After Phase 2 completion
python -c "from topology_tools.plugins import load_plugins; load_plugins()"
pytest tests/unit/plugins/ -v
task ci:local
```

---

## Phase 3: Capability-Driven Architecture

**Priority:** Critical
**Effort Estimate:** 16-20 hours
**Dependencies:** Phase 1 recommended (not blocking)
**Risk:** Medium

### Objective

Implement ADR 0106: Replace hardcoded vendor checks with capability-based plugin selection.

### Tasks

| ID | Task | Description | Verification |
|----|------|-------------|--------------|
| P3.1 | Update ADR 0106 | Move from Proposed to Implementing | ADR status updated |
| P3.2 | Define plugin capabilities | Add capability requirements to plugins | Schema valid |
| P3.3 | Create CapabilityMatcher | Capability-based plugin selection | Unit tests pass |
| P3.4 | Remove vendor hardcoding | Replace string checks with capabilities | No vendor strings |
| P3.5 | Update object schemas | Add required capabilities to objects | Schema validation |
| P3.6 | Migration guide | Document migration for custom plugins | Docs exist |
| P3.7 | Promote ADR 0106 | Move to Implemented status | ADR status updated |

### Current vs Target

```python
# CURRENT (problematic) - topology-tools/plugins/router_selector.py
def select_router_plugin(object_ref: str) -> str:
    if "mikrotik" in object_ref.lower():
        return "mikrotik"
    elif "openwrt" in object_ref.lower():
        return "openwrt"
    elif "vyos" in object_ref.lower():
        return "vyos"
    raise ValueError(f"Unknown router type: {object_ref}")

# TARGET (capability-driven)
def select_router_plugin(obj: CompiledObject) -> str:
    capability_map = {
        "network.routing.routeros": "mikrotik",
        "network.routing.openwrt": "openwrt",
        "network.routing.vyos": "vyos",
    }
    for cap, plugin in capability_map.items():
        if obj.has_capability(cap):
            return plugin
    raise CapabilityMismatchError(obj, required_any=list(capability_map.keys()))
```

### Plugin Capability Schema

```yaml
# Example: generators/mikrotik.yaml
plugin:
  name: generator.mikrotik.routeros
  stage: generate

  required_capabilities:
    any_of:
      - network.routing.routeros
      - network.routing.routeros7

  provides_capabilities:
    - config.mikrotik.rsc

  excludes_capabilities:
    - config.readonly
```

### Validation

```bash
# After Phase 3 completion
grep -r "mikrotik.*in.*lower" topology-tools/  # Should return nothing
pytest tests/unit/plugins/test_capability_matcher.py -v
task ci:local
```

---

## Phase 4: Housekeeping & Governance

**Priority:** Low
**Effort Estimate:** 8-12 hours
**Dependencies:** None
**Risk:** Low

### Tasks

| ID | Task | Description | Verification |
|----|------|-------------|--------------|
| P4.1 | Update project status | Change `migration` to `operational` | project.yaml updated |
| P4.2 | Archive superseded ADRs | Move ADRs 0006-0025 to archive | Cleaner ADR folder |
| P4.3 | Generate layer-contract | Auto-generate from class metadata | Script exists |
| P4.4 | Capability lifecycle | Add deprecation/versioning policy | Policy documented |
| P4.5 | LXC object templates | Create parameterized template | Reduced duplication |
| P4.6 | DAG validator | Add extends/refs cycle detection | Validator exists |
| P4.7 | Complete pending ADRs | Review 0105, 0108, 0110 status | ADRs updated |

### P4.1: Update Project Status

```yaml
# projects/home-lab/project.yaml
# BEFORE
status: migration

# AFTER
status: operational
migration_completed: 2026-06-27
```

### P4.3: Layer Contract Generator

```bash
# Add to topology-tools/utils/
python generate-layer-contract.py \
  --classes topology/class-modules/ \
  --output topology/layer-contract.yaml
```

### P4.5: LXC Object Template

```yaml
# topology/object-modules/templates/lxc-debian12.template.yaml
@template: true
@base: obj.proxmox.lxc.debian12

parameters:
  - name: service_name
    required: true
  - name: vmid
    required: true
  - name: additional_capabilities
    default: []

template:
  @object: "obj.proxmox.lxc.debian12.{{service_name}}"
  @title: "Debian 12 LXC - {{service_name}}"
  @extends: obj.proxmox.lxc.debian12.base

  vmid: "{{vmid}}"
  capabilities: "{{['compute.container.lxc'] + additional_capabilities}}"
```

---

## Execution Schedule

### Parallel Execution (Recommended)

```
Week 1:
├── Phase 1 (P1.1-P1.3) ─────────────────────►
└── Phase 2 (P2.1-P2.5) ─────────────────────►

Week 2:
├── Phase 1 (P1.4-P1.6) ─────────────────────►
└── Phase 2 (P2.6-P2.9) ─────────────────────►

Week 3:
└── Phase 3 (P3.1-P3.7) ─────────────────────────────────────►

Week 4:
└── Phase 4 (P4.1-P4.7) ─────────────────────►
```

### Sequential Execution (Conservative)

```
Phase 1: Compiler Decomposition .................. 16-24 hours
Phase 2: Configuration Sharding .................. 8-12 hours
Phase 3: Capability-Driven Architecture .......... 16-20 hours
Phase 4: Housekeeping & Governance ............... 8-12 hours
─────────────────────────────────────────────────────────────
Total: 48-68 hours
```

---

## Validation Gates

| Gate | Trigger | Command | Success Criteria |
|------|---------|---------|------------------|
| Phase 1 | All P1.* done | `task ci:local` | All tests pass |
| Phase 2 | All P2.* done | `task ci:local` | Plugin loading works |
| Phase 3 | All P3.* done | `task ci:local` | No vendor strings |
| Phase 4 | All P4.* done | `task ci:local` | Full validation |

---

## Rollback Plan

### Phase 1 Rollback

```bash
# If compiler decomposition fails
git checkout main -- topology-tools/compile-topology.py
rm -rf topology-tools/compiler/
```

### Phase 2 Rollback

```bash
# If plugin sharding fails
git checkout main -- topology-tools/plugins/plugins.yaml
rm -rf topology-tools/plugins/manifests/
```

### Phase 3 Rollback

```bash
# If capability migration fails
git revert HEAD~N  # Where N = number of Phase 3 commits
# Update ADR 0106 back to Proposed
```

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Compiler LOC | 1828 | <200 (orchestrator) | `wc -l compile-topology.py` |
| plugins.yaml LOC | 2934 | <100 (root manifest) | `wc -l plugins/plugins.yaml` |
| Vendor hardcoding | ~15 instances | 0 | `grep -r "in.*lower"` |
| Project status | migration | operational | project.yaml |
| Pending ADRs | 4 | 0-1 | ADR register |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Regression in compiler | Medium | High | Comprehensive test coverage |
| Plugin loading breaks | Low | High | Incremental migration, backwards compat |
| Capability mapping incomplete | Medium | Medium | Thorough capability audit |
| Performance degradation | Low | Medium | Benchmark before/after |

---

## Checklist

### Phase 1: Compiler Decomposition

- [ ] P1.1: AiSessionManager extracted
- [ ] P1.2: FrameworkLockVerifier extracted
- [ ] P1.3: PluginRegistryManager extracted
- [ ] P1.4: DiagnosticsManager extracted
- [ ] P1.5: CompilerOrchestrator created
- [ ] P1.6: All imports updated
- [ ] Phase 1 gate: `task ci:local` passes

### Phase 2: Configuration Sharding

- [ ] P2.1: Manifest directory created
- [ ] P2.2: Discoverers extracted
- [ ] P2.3: Compilers extracted
- [ ] P2.4: Validators extracted
- [ ] P2.5: Generators extracted
- [ ] P2.6: Assemblers extracted
- [ ] P2.7: Builders extracted
- [ ] P2.8: Manifest loader updated
- [ ] P2.9: Root manifest created
- [ ] Phase 2 gate: `task ci:local` passes

### Phase 3: Capability-Driven Architecture

- [ ] P3.1: ADR 0106 status → Implementing
- [ ] P3.2: Plugin capabilities defined
- [ ] P3.3: CapabilityMatcher created
- [ ] P3.4: Vendor hardcoding removed
- [ ] P3.5: Object schemas updated
- [ ] P3.6: Migration guide written
- [ ] P3.7: ADR 0106 status → Implemented
- [ ] Phase 3 gate: `task ci:local` passes

### Phase 4: Housekeeping & Governance

- [ ] P4.1: Project status updated
- [ ] P4.2: Superseded ADRs archived
- [ ] P4.3: Layer contract generator created
- [ ] P4.4: Capability lifecycle policy documented
- [ ] P4.5: LXC template created
- [ ] P4.6: DAG validator implemented
- [ ] P4.7: Pending ADRs reviewed
- [ ] Phase 4 gate: `task ci:local` passes

---

## References

- Analysis: `docs/analysis/ARCHITECTURE-ANALYSIS-2026-06-27.md`
- ADR 0063: Plugin Architecture
- ADR 0082: Module-Pack Composition
- ADR 0106: Capability-Driven Plugin Architecture
- Previous Plan: `docs/analysis/IMPLEMENTATION-PLAN-2026-04-22.md`

---

## Metadata

```yaml
plan_date: 2026-06-27
plan_status: proposed
total_effort_hours: 48-68
phases:
  - id: 1
    name: Compiler Decomposition
    priority: critical
    effort_hours: 16-24
    tasks: 6
  - id: 2
    name: Configuration Sharding
    priority: critical
    effort_hours: 8-12
    tasks: 9
  - id: 3
    name: Capability-Driven Architecture
    priority: critical
    effort_hours: 16-20
    tasks: 7
  - id: 4
    name: Housekeeping & Governance
    priority: low
    effort_hours: 8-12
    tasks: 7
```
