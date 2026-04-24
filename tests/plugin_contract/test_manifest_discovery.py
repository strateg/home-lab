#!/usr/bin/env python3
"""Contract tests for module-level plugin manifest discovery policy (ADR 0063)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Add topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugin_manifest_discovery import discover_plugin_manifest_paths, validate_module_index_consistency


def _write_manifest(path: Path, *, plugin_id: str) -> None:
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": plugin_id,
                "kind": "validator_json",
                "entry": "validators/reference_validator.py:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_module_index(
    path: Path,
    *,
    class_manifests: list[str],
    object_manifests: list[str],
) -> None:
    payload = {
        "schema_version": 1,
        "class_modules": [{"plugins_manifest": item} for item in class_manifests],
        "object_modules": [{"plugins_manifest": item} for item in object_manifests],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _assert_root_group_order(
    *, manifests: list[Path], class_root: Path, object_root: Path, project_plugins_root: Path | None
) -> None:
    """Ensure manifests are grouped in deterministic root order.

    Expected order after base manifest:
    1) class manifests
    2) object manifests
    3) project manifests (if root is provided)
    """
    labels: list[str] = []
    for path in manifests[1:]:
        resolved = path.resolve()
        if str(resolved).startswith(str(class_root.resolve())):
            labels.append("class")
            continue
        if str(resolved).startswith(str(object_root.resolve())):
            labels.append("object")
            continue
        if project_plugins_root is not None and str(resolved).startswith(str(project_plugins_root.resolve())):
            labels.append("project")
            continue
        labels.append("other")

    if "class" in labels and "object" in labels:
        assert labels.index("class") < labels.index("object")
    if project_plugins_root is not None and "object" in labels and "project" in labels:
        assert labels.index("object") < labels.index("project")
    assert "other" not in labels


def test_discover_plugin_manifests_order_is_deterministic(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    _write_manifest(base, plugin_id="base.validator.alpha")
    _write_manifest(class_root / "zeta" / "plugins.yaml", plugin_id="class.validator.zeta")
    _write_manifest(class_root / "alpha" / "plugins.yaml", plugin_id="class.validator.alpha")
    _write_manifest(object_root / "omega" / "plugins.yaml", plugin_id="object.validator.omega")
    _write_manifest(object_root / "beta" / "plugins.yaml", plugin_id="object.validator.beta")

    manifests = discover_plugin_manifest_paths(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
    )

    assert manifests == [
        base.resolve(),
        (class_root / "alpha" / "plugins.yaml").resolve(),
        (class_root / "zeta" / "plugins.yaml").resolve(),
        (object_root / "beta" / "plugins.yaml").resolve(),
        (object_root / "omega" / "plugins.yaml").resolve(),
    ]
    _assert_root_group_order(
        manifests=manifests,
        class_root=class_root,
        object_root=object_root,
        project_plugins_root=None,
    )


def test_discovery_keeps_base_manifest_first_even_if_missing(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    _write_manifest(class_root / "a" / "plugins.yaml", plugin_id="class.validator.a")
    _write_manifest(object_root / "b" / "plugins.yaml", plugin_id="object.validator.b")

    manifests = discover_plugin_manifest_paths(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
    )

    assert manifests[0] == base.resolve()
    assert manifests[1:] == [
        (class_root / "a" / "plugins.yaml").resolve(),
        (object_root / "b" / "plugins.yaml").resolve(),
    ]


def test_discovery_does_not_scan_instances_root(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    instances_root = tmp_path / "instances"

    _write_manifest(base, plugin_id="base.validator.alpha")
    _write_manifest(class_root / "a" / "plugins.yaml", plugin_id="class.validator.a")
    _write_manifest(object_root / "b" / "plugins.yaml", plugin_id="object.validator.b")
    _write_manifest(instances_root / "site-a" / "plugins.yaml", plugin_id="instance.validator.site_a")

    manifests = discover_plugin_manifest_paths(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
    )

    resolved = {path.resolve() for path in manifests}
    assert (instances_root / "site-a" / "plugins.yaml").resolve() not in resolved


def test_discovery_includes_project_plugins_after_object_manifests(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    project_plugins_root = tmp_path / "project-root" / "plugins"

    _write_manifest(base, plugin_id="base.validator.alpha")
    _write_manifest(class_root / "a" / "plugins.yaml", plugin_id="class.validator.a")
    _write_manifest(object_root / "b" / "plugins.yaml", plugin_id="object.validator.b")
    _write_manifest(project_plugins_root / "plugins.yaml", plugin_id="project.validator.root")
    _write_manifest(project_plugins_root / "zeta" / "plugins.yaml", plugin_id="project.validator.zeta")
    _write_manifest(project_plugins_root / "alpha" / "plugins.yaml", plugin_id="project.validator.alpha")

    manifests = discover_plugin_manifest_paths(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
        project_plugins_root=project_plugins_root,
    )

    assert manifests == [
        base.resolve(),
        (class_root / "a" / "plugins.yaml").resolve(),
        (object_root / "b" / "plugins.yaml").resolve(),
        (project_plugins_root / "alpha" / "plugins.yaml").resolve(),
        (project_plugins_root / "plugins.yaml").resolve(),
        (project_plugins_root / "zeta" / "plugins.yaml").resolve(),
    ]
    _assert_root_group_order(
        manifests=manifests,
        class_root=class_root,
        object_root=object_root,
        project_plugins_root=project_plugins_root,
    )


def test_discovery_scans_only_project_plugins_root_not_project_instances(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    project_root = tmp_path / "project-root"
    project_plugins_root = project_root / "plugins"
    instances_root = project_root / "topology" / "instances"

    _write_manifest(base, plugin_id="base.validator.alpha")
    _write_manifest(class_root / "a" / "plugins.yaml", plugin_id="class.validator.a")
    _write_manifest(object_root / "b" / "plugins.yaml", plugin_id="object.validator.b")
    _write_manifest(project_plugins_root / "plugins.yaml", plugin_id="project.validator.root")
    _write_manifest(instances_root / "site-a" / "plugins.yaml", plugin_id="instance.validator.site_a")

    manifests = discover_plugin_manifest_paths(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
        project_plugins_root=project_plugins_root,
    )

    resolved = {path.resolve() for path in manifests}
    assert (project_plugins_root / "plugins.yaml").resolve() in resolved
    assert (instances_root / "site-a" / "plugins.yaml").resolve() not in resolved


def test_discovery_uses_module_index_when_available(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    topology_root = tmp_path / "topology"
    class_root = topology_root / "class-modules"
    object_root = topology_root / "object-modules"
    module_index = topology_root / "module-index.yaml"

    _write_manifest(base, plugin_id="base.validator.alpha")
    _write_manifest(class_root / "a" / "plugins.yaml", plugin_id="class.validator.a")
    _write_manifest(class_root / "z" / "plugins.yaml", plugin_id="class.validator.z")
    _write_manifest(object_root / "b" / "plugins.yaml", plugin_id="object.validator.b")
    _write_manifest(object_root / "c" / "plugins.yaml", plugin_id="object.validator.c")

    _write_module_index(
        module_index,
        class_manifests=["class-modules/z/plugins.yaml"],
        object_manifests=["object-modules/b/plugins.yaml"],
    )

    manifests = discover_plugin_manifest_paths(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
        module_index_path=module_index,
    )

    assert manifests == [
        base.resolve(),
        (class_root / "z" / "plugins.yaml").resolve(),
        (object_root / "b" / "plugins.yaml").resolve(),
    ]


def test_discovery_falls_back_to_recursive_scan_when_module_index_invalid(tmp_path: Path) -> None:
    base = tmp_path / "plugins" / "plugins.yaml"
    topology_root = tmp_path / "topology"
    class_root = topology_root / "class-modules"
    object_root = topology_root / "object-modules"
    module_index = topology_root / "module-index.yaml"

    _write_manifest(base, plugin_id="base.validator.alpha")
    _write_manifest(class_root / "a" / "plugins.yaml", plugin_id="class.validator.a")
    _write_manifest(object_root / "b" / "plugins.yaml", plugin_id="object.validator.b")
    module_index.parent.mkdir(parents=True, exist_ok=True)
    module_index.write_text("schema_version: 1\nclass_modules: bad\n", encoding="utf-8")

    manifests = discover_plugin_manifest_paths(
        base_manifest_path=base,
        class_modules_root=class_root,
        object_modules_root=object_root,
        module_index_path=module_index,
    )

    assert manifests == [
        base.resolve(),
        (class_root / "a" / "plugins.yaml").resolve(),
        (object_root / "b" / "plugins.yaml").resolve(),
    ]


def test_module_index_consistency_reports_missing_index_entry(tmp_path: Path) -> None:
    topology_root = tmp_path / "topology"
    class_root = topology_root / "class-modules"
    object_root = topology_root / "object-modules"
    module_index = topology_root / "module-index.yaml"

    _write_manifest(class_root / "router" / "plugins.yaml", plugin_id="class.validator.router")
    _write_manifest(object_root / "mikrotik" / "plugins.yaml", plugin_id="object.validator.mikrotik")
    _write_module_index(
        module_index,
        class_manifests=[],
        object_manifests=["object-modules/mikrotik/plugins.yaml"],
    )

    errors = validate_module_index_consistency(
        module_index_path=module_index,
        class_modules_root=class_root,
        object_modules_root=object_root,
    )

    assert any("class_modules index missing manifest present on disk" in item for item in errors)


def test_module_index_consistency_reports_missing_index_file(tmp_path: Path) -> None:
    topology_root = tmp_path / "topology"
    class_root = topology_root / "class-modules"
    object_root = topology_root / "object-modules"
    missing_index = topology_root / "module-index.yaml"
    _write_manifest(object_root / "mikrotik" / "plugins.yaml", plugin_id="object.validator.mikrotik")

    errors = validate_module_index_consistency(
        module_index_path=missing_index,
        class_modules_root=class_root,
        object_modules_root=object_root,
    )

    assert any("module-index file is missing" in item for item in errors)


def test_module_index_consistency_reports_stale_entry(tmp_path: Path) -> None:
    topology_root = tmp_path / "topology"
    class_root = topology_root / "class-modules"
    object_root = topology_root / "object-modules"
    module_index = topology_root / "module-index.yaml"

    _write_manifest(object_root / "mikrotik" / "plugins.yaml", plugin_id="object.validator.mikrotik")
    _write_module_index(
        module_index,
        class_manifests=["class-modules/L1-foundation/router/plugins.yaml"],
        object_manifests=["object-modules/mikrotik/plugins.yaml"],
    )

    errors = validate_module_index_consistency(
        module_index_path=module_index,
        class_modules_root=class_root,
        object_modules_root=object_root,
    )

    assert any("class_modules[0] manifest path does not exist" in item for item in errors)


def test_module_index_consistency_passes_for_exact_match(tmp_path: Path) -> None:
    topology_root = tmp_path / "topology"
    class_root = topology_root / "class-modules"
    object_root = topology_root / "object-modules"
    module_index = topology_root / "module-index.yaml"

    _write_manifest(class_root / "router" / "plugins.yaml", plugin_id="class.validator.router")
    _write_manifest(object_root / "mikrotik" / "plugins.yaml", plugin_id="object.validator.mikrotik")
    _write_module_index(
        module_index,
        class_manifests=["class-modules/L1-foundation/router/plugins.yaml"],
        object_manifests=["object-modules/mikrotik/plugins.yaml"],
    )

    errors = validate_module_index_consistency(
        module_index_path=module_index,
        class_modules_root=class_root,
        object_modules_root=object_root,
    )

    assert errors == []
