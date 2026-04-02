#!/usr/bin/env python3
"""Integration checks for module-level plugin manifest loading (ADR 0063)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_module_discovery", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest(path: Path, *, plugin_id: str, description: str = "") -> None:
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
                "description": description,
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _create_compiler(mod, tmp_path: Path):
    out_dir = mod.REPO_ROOT / "build" / "test-module-manifest-discovery" / tmp_path.name
    return mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=out_dir / "effective.json",
        diagnostics_json=out_dir / "diagnostics.json",
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )


def test_module_level_manifests_are_loaded(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    _write_manifest(class_root / "alpha" / "plugins.yaml", plugin_id="class.validator.alpha")
    _write_manifest(object_root / "beta" / "plugins.yaml", plugin_id="object.validator.beta")

    compiler._load_plugin_manifests(class_modules_root=class_root, object_modules_root=object_root)

    assert "class.validator.alpha" in compiler._plugin_registry.specs
    assert "object.validator.beta" in compiler._plugin_registry.specs
    assert any(d.code == "I4001" for d in compiler._diagnostics)


def test_duplicate_plugin_id_between_manifests_is_reported(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    _write_manifest(
        class_root / "first" / "plugins.yaml",
        plugin_id="shared.validator.duplicate",
        description="class-version",
    )
    _write_manifest(
        object_root / "second" / "plugins.yaml",
        plugin_id="shared.validator.duplicate",
        description="object-version",
    )

    compiler._load_plugin_manifests(class_modules_root=class_root, object_modules_root=object_root)

    spec = compiler._plugin_registry.specs["shared.validator.duplicate"]
    assert spec.description == "class-version"
    assert any(d.code == "E4001" for d in compiler._diagnostics)


def test_invalid_module_manifest_is_reported_without_crash(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    bad_manifest = class_root / "bad" / "plugins.yaml"
    bad_manifest.parent.mkdir(parents=True, exist_ok=True)
    bad_manifest.write_text("schema_version: 1\nplugins: [\n", encoding="utf-8")

    compiler._load_plugin_manifests(class_modules_root=class_root, object_modules_root=object_root)

    assert any(d.code == "E4001" for d in compiler._diagnostics)


def test_discover_init_plugin_loads_module_manifests(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    _write_manifest(class_root / "alpha" / "plugins.yaml", plugin_id="class.validator.alpha")
    _write_manifest(object_root / "beta" / "plugins.yaml", plugin_id="object.validator.beta")

    compiler._load_base_plugin_manifest()
    ctx = mod.PluginContext(
        topology_path="topology/topology.yaml",
        profile="production",
        model_lock={},
        config={
            "discover_load_module_manifests": lambda: compiler._load_module_plugin_manifests(
                class_modules_root=class_root,
                object_modules_root=object_root,
                emit_diagnostics=False,
            ),
            "discovered_plugin_manifests": [],
            "discovered_plugin_count": 0,
        },
    )

    compiler._execute_plugins(stage=mod.Stage.DISCOVER, ctx=ctx)

    assert "class.validator.alpha" in compiler._plugin_registry.specs
    assert "object.validator.beta" in compiler._plugin_registry.specs
    discovered = ctx.config.get("discovered_plugin_manifests", [])
    assert any(str(path).replace("\\", "/").endswith("class-modules/alpha/plugins.yaml") for path in discovered)


def test_module_manifest_loader_includes_project_plugins_root(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    project_plugins_root = tmp_path / "project-root" / "plugins"

    _write_manifest(class_root / "alpha" / "plugins.yaml", plugin_id="class.validator.alpha")
    _write_manifest(object_root / "beta" / "plugins.yaml", plugin_id="object.validator.beta")
    _write_manifest(project_plugins_root / "plugins.yaml", plugin_id="project.validator.root")

    summary = compiler._load_module_plugin_manifests(
        class_modules_root=class_root,
        object_modules_root=object_root,
        project_plugins_root=project_plugins_root,
        emit_diagnostics=False,
    )

    assert summary["status"] == "ok"
    assert "project.validator.root" in compiler._plugin_registry.specs
    discovered = summary.get("discovered_manifests", [])
    assert any(str(path).replace("\\", "/").endswith("project-root/plugins/plugins.yaml") for path in discovered)


def test_module_manifest_loader_keeps_framework_class_object_project_order(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    project_plugins_root = tmp_path / "project-root" / "plugins"

    _write_manifest(class_root / "zeta" / "plugins.yaml", plugin_id="class.validator.zeta")
    _write_manifest(class_root / "alpha" / "plugins.yaml", plugin_id="class.validator.alpha")
    _write_manifest(object_root / "omega" / "plugins.yaml", plugin_id="object.validator.omega")
    _write_manifest(object_root / "beta" / "plugins.yaml", plugin_id="object.validator.beta")
    _write_manifest(project_plugins_root / "plugins.yaml", plugin_id="project.validator.root")

    summary = compiler._load_module_plugin_manifests(
        class_modules_root=class_root,
        object_modules_root=object_root,
        project_plugins_root=project_plugins_root,
        emit_diagnostics=False,
    )

    discovered = [str(path).replace("\\", "/") for path in summary.get("discovered_manifests", [])]
    base_idx = next(i for i, path in enumerate(discovered) if path.endswith("topology-tools/plugins/plugins.yaml"))
    class_idx = next(i for i, path in enumerate(discovered) if path.endswith("class-modules/alpha/plugins.yaml"))
    object_idx = next(i for i, path in enumerate(discovered) if path.endswith("object-modules/beta/plugins.yaml"))
    project_idx = next(i for i, path in enumerate(discovered) if path.endswith("project-root/plugins/plugins.yaml"))

    assert base_idx < class_idx < object_idx < project_idx


def test_discover_boundary_allows_project_plugins_and_rejects_instances(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None
    compiler._load_base_plugin_manifest()

    ctx = mod.PluginContext(
        topology_path="topology/topology.yaml",
        profile="production",
        model_lock={},
        config={
            "project_plugins_root": "projects/home-lab/plugins",
            "discovered_plugin_manifests": [
                "projects/home-lab/plugins/plugins.yaml",
                "projects/home-lab/topology/instances/L1-foundation/power/plugins.yaml",
            ],
            "discovered_plugin_count": 0,
        },
    )

    result = compiler._plugin_registry.execute_plugin(
        "base.discover.boundary",
        ctx,
        mod.Stage.DISCOVER,
        phase=mod.Phase.PRE,
    )

    assert result.status == mod.PluginStatus.FAILED
    assert any("outside allowed boundary" in d.message for d in result.diagnostics)
    assert any(d.path.endswith("topology/instances/L1-foundation/power/plugins.yaml") for d in result.diagnostics)


def test_discover_boundary_rejects_project_manifests_outside_project_plugins_root(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None
    compiler._load_base_plugin_manifest()

    ctx = mod.PluginContext(
        topology_path="topology/topology.yaml",
        profile="production",
        model_lock={},
        config={
            "project_plugins_root": "projects/home-lab/plugins",
            "discovered_plugin_manifests": [
                "projects/home-lab/plugins/plugins.yaml",
                "projects/home-lab/plugins-extra/plugins.yaml",
            ],
            "discovered_plugin_count": 0,
        },
    )

    result = compiler._plugin_registry.execute_plugin(
        "base.discover.boundary",
        ctx,
        mod.Stage.DISCOVER,
        phase=mod.Phase.PRE,
    )

    assert result.status == mod.PluginStatus.FAILED
    assert any(d.path.endswith("projects/home-lab/plugins-extra/plugins.yaml") for d in result.diagnostics)
