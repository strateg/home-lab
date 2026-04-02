# ADR 0086 — Contract Boundary Checks

This document defines the boundary model enforced after ADR0086.

## Runtime Policy

Runtime does **not** enforce legacy level-visibility ACL (global/class/object/instance).
Boundary safety is enforced by contract checks and discovery invariants.

## Enforced Checks

| Contract area | Enforcement | Primary tests |
|---|---|---|
| Kind-to-stage affinity (`discoverer/compile/...`) | Manifest validation contract | `tests/plugin_contract/test_plugin_level_boundaries.py::test_manifest_plugins_respect_kind_stage_affinity` |
| Stage order ranges | Manifest validation contract | `tests/plugin_contract/test_plugin_level_boundaries.py::test_manifest_plugins_respect_stage_order_ranges` |
| Dependency link integrity (`depends_on`) | Manifest graph contract | `tests/plugin_contract/test_plugin_level_boundaries.py::test_manifest_dependencies_reference_existing_plugins` |
| Discovery order (`framework -> class -> object -> project`) | Discovery contract | `tests/plugin_contract/test_manifest_discovery.py` |
| Project plugin root boundary (`project_plugins_root`) | Discovery boundary contract | `tests/plugin_contract/test_manifest_discovery.py::test_discovery_scans_only_project_plugins_root_not_project_instances` |
| Standalone placement/layout policy | Architecture contract | `tests/plugin_contract/test_plugin_layout_policy.py` |
| Object module isolation from peer object imports | Ownership contract | `tests/plugin_contract/test_plugin_level_boundaries.py::test_object_modules_do_not_cross_import_other_object_modules` |

## Validation Command Pack

```bat
python -m pytest tests\plugin_contract\test_plugin_level_boundaries.py -q
python -m pytest tests\plugin_contract\test_manifest_discovery.py -q
python -m pytest tests\plugin_contract\test_plugin_layout_policy.py -q
```

## Notes

- This contract model aligns ADR0086 D1/D7 with ADR0080 stage/phase data-bus governance.
- Class/object module placement remains an ownership convention and extension-point mechanism.
