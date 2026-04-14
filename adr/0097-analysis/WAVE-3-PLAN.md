# ADR 0097 — Wave 3 Implementation Plan

**Date**: 2026-04-14
**Status**: Complete
**Wave**: Generator Migration
**Depends on**: Wave 2 (Complete)

---

## Objectives

Wave 3 migrates generators to subinterpreter execution:

1. Audit all generator dependencies for subinterpreter compatibility
2. Mark compatible generators with `subinterpreter_compatible: true`
3. Enable subinterpreters for generate stage
4. Benchmark file I/O parallelism improvement

**Goal**: All Jinja2-based generators execute in subinterpreters on Python 3.14+.

---

## Dependency Audit Results

### Generators Using PyYAML (NOT Compatible)

| Plugin ID | Reason |
|-----------|--------|
| `base.generator.effective_yaml` | Uses `yaml.dump()` for YAML output |
| `base.generator.docker_compose` | Uses `yaml.dump()` for docker-compose.yaml |

**Mitigation**: These generators will use `ThreadPoolExecutor` fallback until PyYAML subinterpreter compatibility is verified.

### Generators Compatible with Subinterpreters (10)

Generators using only:
- Standard library (json, pathlib, hashlib, etc.)
- Jinja2 (pure Python core with optional C speedups)
- Internal modules

**Base Generators (5):**
1. `base.generator.effective_json` - Pure JSON, no templates
2. `base.generator.docs` - Jinja2 markdown templates
3. `base.generator.diagrams` - Jinja2 mermaid templates
4. `base.generator.ansible_inventory` - Jinja2 YAML templates
5. `base.generator.artifact_manifest` - JSON aggregation

**Object-Scoped Generators (5):**
6. `object.proxmox.generator.terraform` - Jinja2 HCL templates
7. `object.proxmox.generator.bootstrap` - Jinja2 bootstrap templates
8. `object.mikrotik.generator.terraform` - Jinja2 HCL templates
9. `object.mikrotik.generator.bootstrap` - Jinja2 bootstrap templates
10. `object.orangepi.generator.bootstrap` - Jinja2 bootstrap templates

---

## Jinja2 Compatibility Notes

Jinja2 architecture:
- Core engine: Pure Python
- MarkupSafe: Optional C extension for escaping (falls back to Python)
- Template compilation: Pure Python

Expected behavior in subinterpreters:
- Template loading: Works (file I/O)
- Template rendering: Works (pure Python)
- MarkupSafe escaping: May use Python fallback

**Risk**: Low - Jinja2 is designed for embedding and has minimal C dependencies.

---

## Implementation Tasks

### T1: Update Base Plugin Manifest

**File**: `topology-tools/plugins/plugins.yaml`

Add `subinterpreter_compatible: true` to 5 compatible generators.
Add `subinterpreter_compatible: false` to 2 PyYAML generators.

### T2: Update Object-Scoped Manifests

**Files**:
- `topology/object-modules/proxmox/plugins.yaml`
- `topology/object-modules/mikrotik/plugins.yaml`
- `topology/object-modules/orangepi/plugins.yaml`

Add `subinterpreter_compatible: true` to all object-scoped generators.

### T3: Verify Parity Tests

Run parity tests with generators marked as compatible.

### T4: Documentation Update

1. Update ADR 0097 status
2. Document Wave 3 evidence

---

## Exit Criteria

| Criterion | Status |
|-----------|--------|
| 10 generators marked `subinterpreter_compatible: true` | PASS |
| 2 PyYAML generators marked `subinterpreter_compatible: false` | PASS |
| Parity tests pass | PASS |
| No regressions in validation pipeline | PASS |
| Documentation updated | PASS |

---

## Next Wave

After Wave 3 completion, proceed to **Wave 4: Lock Removal**:

1. Remove `_published_data_lock` (subinterpreter mode)
2. Simplify `PluginExecutionScope` to minimal form
3. Remove `contextvars` complexity
4. Update documentation

**Gate**: Codebase simplified; ThreadPoolExecutor fallback still works.

---

**Document Owner**: Infrastructure Team
**Last Updated**: 2026-04-14
