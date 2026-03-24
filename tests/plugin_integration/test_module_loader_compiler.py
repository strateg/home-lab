#!/usr/bin/env python3
"""Integration tests for module loader compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.module_loader"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_module_loader_skips_when_core_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_module_maps": "core"},
        classes={"class.router": {"class": "class.router"}},
        objects={"obj.router": {"object": "obj.router", "class_ref": "class.router"}},
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert "class_map" in (result.output_data or {})
    assert "object_map" in (result.output_data or {})


def test_module_loader_plugin_owner_loads_modules(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "class: class.router\nversion: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "object: obj.router\nclass_ref: class.router\nversion: 1.0.0\n",
        encoding="utf-8",
    )

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_module_maps": "plugin",
            "class_modules_root": str(class_dir),
            "object_modules_root": str(object_dir),
        },
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert "class.router" in ctx.classes
    assert "obj.router" in ctx.objects


def test_module_loader_rejects_unsafe_class_and_object_ids(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "class: class.router:bad\nversion: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "object: obj.router?bad\nclass_ref: class.router\nversion: 1.0.0\n",
        encoding="utf-8",
    )

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_module_maps": "plugin",
            "class_modules_root": str(class_dir),
            "object_modules_root": str(object_dir),
        },
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status in {PluginStatus.PARTIAL, PluginStatus.SUCCESS, PluginStatus.FAILED}
    assert result.has_errors
    errors = [d for d in result.diagnostics if d.code == "E3201" and d.severity == "error"]
    assert any("class id" in d.message and "filename-unsafe" in d.message for d in errors)
    assert any("object id" in d.message and "filename-unsafe" in d.message for d in errors)
