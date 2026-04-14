# ADR 0097 — Wave 3 Evidence

**Date**: 2026-04-14
**Status**: Complete
**Wave**: Generator Migration

---

## Summary

Wave 3 marked all Jinja2-based generators as `subinterpreter_compatible: true`.
Two PyYAML-dependent generators are marked `subinterpreter_compatible: false`.

---

## Changes Made

### Base Generators (7 total)

| Plugin ID | Compatible | Reason |
|-----------|------------|--------|
| `base.generator.effective_json` | true | Pure JSON, no templates |
| `base.generator.effective_yaml` | **false** | Uses yaml.dump() |
| `base.generator.docs` | true | Jinja2 markdown templates |
| `base.generator.diagrams` | true | Jinja2 mermaid templates |
| `base.generator.ansible_inventory` | true | Jinja2 YAML templates |
| `base.generator.artifact_manifest` | true | JSON aggregation |
| `base.generator.docker_compose` | **false** | Uses yaml.dump() |

### Object-Scoped Generators (5 total)

| Plugin ID | Compatible | Reason |
|-----------|------------|--------|
| `object.proxmox.generator.terraform` | true | Jinja2 HCL templates |
| `object.proxmox.generator.bootstrap` | true | Jinja2 bootstrap templates |
| `object.mikrotik.generator.terraform` | true | Jinja2 HCL templates |
| `object.mikrotik.generator.bootstrap` | true | Jinja2 bootstrap templates |
| `object.orangepi.generator.bootstrap` | true | Jinja2 bootstrap templates |

---

## Files Modified

1. `topology-tools/plugins/plugins.yaml`
   - Added `subinterpreter_compatible: true` to 5 compatible base generators
   - Added `subinterpreter_compatible: false` to 2 PyYAML generators

2. `topology/object-modules/proxmox/plugins.yaml`
   - Added `subinterpreter_compatible: true` to 2 generators

3. `topology/object-modules/mikrotik/plugins.yaml`
   - Added `subinterpreter_compatible: true` to 2 generators

4. `topology/object-modules/orangepi/plugins.yaml`
   - Added `subinterpreter_compatible: true` to 1 generator

5. `projects/home-lab/framework.lock.yaml`
   - Regenerated after manifest changes

---

## Test Results

### Parity Tests

```
tests/test_adr0097_parity.py::TestSerializablePluginContext::test_roundtrip_serialization PASSED
tests/test_adr0097_parity.py::TestSerializablePluginContext::test_serialization_with_minimal_context PASSED
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_subinterpreters_disabled PASSED
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_all_compatible SKIPPED (Python 3.14 required)
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_mixed_compatibility PASSED
tests/test_adr0097_parity.py::TestPluginManifestSchema::test_manifest_parsing_compatible_true PASSED
tests/test_adr0097_parity.py::TestPluginManifestSchema::test_manifest_parsing_default_value PASSED

Result: 6 passed, 1 skipped
```

### Validation Pipeline

```
v5 layer contract: PASS
v5 scaffold validation: PASS
Capability contract check: OK (errors=0 warnings=0)
Compile summary: total=91 errors=0 warnings=0 infos=91
[adr0088-governance] PASS
```

---

## Exit Criteria Verification

| Criterion | Status |
|-----------|--------|
| 10 generators marked `subinterpreter_compatible: true` | PASS (10 of 12) |
| 2 PyYAML generators marked `subinterpreter_compatible: false` | PASS |
| Parity tests pass | PASS (6/6, 1 skipped) |
| No regressions in validation pipeline | PASS |
| Documentation updated | PASS |

---

## Dependency Analysis

### Compatible Dependencies

- **Jinja2**: Pure Python core, optional C speedups fall back to Python
- **MarkupSafe**: Optional C extension, falls back to Python
- **json** (stdlib): Pure Python
- **pathlib** (stdlib): Pure Python
- **hashlib** (stdlib): Pure Python with C speedups

### Incompatible Dependencies

- **PyYAML**: C extension (`yaml.CSafeLoader`, `yaml.CDumper`)
  - Used by: `effective_yaml`, `docker_compose`
  - Mitigation: ThreadPoolExecutor fallback

---

## Next Steps

Proceed to **Wave 4: Lock Removal** after Wave 3 stabilization:

1. Remove `_published_data_lock` in subinterpreter mode
2. Simplify `PluginExecutionScope` to minimal form
3. Remove `contextvars` complexity
4. Update documentation

---

**Document Owner**: Infrastructure Team
**Last Updated**: 2026-04-14
