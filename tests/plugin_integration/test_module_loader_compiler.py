#!/usr/bin/env python3
"""Integration tests for module loader compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.module_loader"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


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
        "@class: class.router\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "@object: obj.router\n@extends: class.router\n@version: 1.0.0\n",
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


def test_module_loader_execute_stage_commits_authoritative_maps(tmp_path):
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
                {
                    "id": PLUGIN_ID,
                    "kind": "compiler",
                    "entry": f"{(V5_TOOLS / 'plugins/compilers/module_loader_compiler.py').as_posix()}:ModuleLoaderCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "phase": "init",
                "order": 30,
                "subinterpreter_compatible": True,
                "produces": [
                    {"key": "class_map", "scope": "pipeline_shared"},
                    {"key": "object_map", "scope": "pipeline_shared"},
                    {"key": "class_module_paths", "scope": "pipeline_shared"},
                    {"key": "object_module_paths", "scope": "pipeline_shared"},
                ],
            }
        ],
    }
    _write_manifest(manifest, payload)

    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text("@class: class.router\n@version: 1.0.0\n", encoding="utf-8")
    (object_dir / "obj.router.yaml").write_text(
        "@object: obj.router\n@extends: class.router\n@version: 1.0.0\n",
        encoding="utf-8",
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
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

    results = registry.execute_stage(Stage.COMPILE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.SUCCESS
    assert ctx.classes["class.router"]["class"] == "class.router"
    assert ctx.objects["obj.router"]["class_ref"] == "class.router"
    published = ctx.get_published_data()[PLUGIN_ID]
    assert "class_map" in published
    assert "object_map" in published


def test_module_loader_rejects_unsafe_class_and_object_ids(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router:bad\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "@object: obj.router?bad\n@extends: class.router\n@version: 1.0.0\n",
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


def test_module_loader_rejects_duplicate_yaml_keys(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router\n@class: class.router.dup\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "@object: obj.router\n@extends: class.router\n@version: 1.0.0\n",
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

    assert result.has_errors
    assert any(d.code == "E1003" and "duplicate key" in d.message for d in result.diagnostics)


def test_module_loader_accepts_canonical_semantic_keys(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router\n@version: 1.0.0\n@title: Router class\n@summary: Base router\n@description: Router semantic description\n@layer: L1\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "@object: obj.router\n@extends: class.router\n@version: 1.0.0\n",
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
    assert ctx.classes["class.router"]["class"] == "class.router"
    assert ctx.classes["class.router"]["version"] == "1.0.0"
    assert ctx.classes["class.router"]["title"] == "Router class"
    assert ctx.classes["class.router"]["summary"] == "Base router"
    assert ctx.classes["class.router"]["description"] == "Router semantic description"
    assert ctx.classes["class.router"]["layer"] == "L1"
    assert ctx.objects["obj.router"]["object"] == "obj.router"
    assert ctx.objects["obj.router"]["class_ref"] == "class.router"


def test_module_loader_rejects_semantic_key_collision(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router\nclass: class.router\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "@object: obj.router\n@extends: class.router\n@version: 1.0.0\n",
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
    assert result.has_errors
    assert any(d.code == "E8801" and "legacy semantic keys" in d.message for d in result.diagnostics)


def test_module_loader_rejects_extends_and_class_ref_mix(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "@object: obj.router\n@extends: class.router\nclass_ref: class.router\n@version: 1.0.0\n",
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
    assert result.has_errors
    assert any(d.code == "E8801" and "class_ref" in d.message for d in result.diagnostics)


def test_module_loader_rejects_metadata_collision(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router\n@title: Router class\ntitle: Router class duplicate\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.router.yaml").write_text(
        "@object: obj.router\n@extends: class.router\n@version: 1.0.0\n",
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
    assert result.has_errors
    assert any(d.code == "E8801" and "title" in d.message for d in result.diagnostics)


def test_module_loader_rejects_typed_extends_mismatch_for_object(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.base.yaml").write_text(
        "@object: obj.base\n@extends: class.router\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.child.yaml").write_text(
        "@object: obj.child\n@extends: obj.base\n@version: 1.0.0\n",
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
    assert result.has_errors
    assert any(d.code == "E8804" and "object inheritance requires class id" in d.message for d in result.diagnostics)


def test_module_loader_rejects_typed_extends_mismatch_for_class(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router\n@extends: obj.base\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.base.yaml").write_text(
        "@object: obj.base\n@extends: class.router\n@version: 1.0.0\n",
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
    assert result.has_errors
    assert any(d.code == "E8804" and "class inheritance requires class id" in d.message for d in result.diagnostics)


def test_module_loader_rejects_unknown_parent_class_target(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.child.yaml").write_text(
        "@class: class.child\n@extends: class.missing\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.child.yaml").write_text(
        "@object: obj.child\n@extends: class.child\n@version: 1.0.0\n",
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
    assert result.has_errors
    assert any(d.code == "E8804" and "does not exist in class registry" in d.message for d in result.diagnostics)


def test_module_loader_rejects_unknown_object_class_target(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.router.yaml").write_text(
        "@class: class.router\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.child.yaml").write_text(
        "@object: obj.child\n@extends: class.missing\n@version: 1.0.0\n",
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
    assert result.has_errors
    assert any(d.code == "E8804" and "does not exist in class registry" in d.message for d in result.diagnostics)


def test_module_loader_rejects_class_inheritance_cycle(tmp_path):
    registry = _registry()
    class_dir = tmp_path / "class-modules"
    object_dir = tmp_path / "object-modules"
    class_dir.mkdir()
    object_dir.mkdir()
    (class_dir / "class.a.yaml").write_text(
        "@class: class.a\n@extends: class.b\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (class_dir / "class.b.yaml").write_text(
        "@class: class.b\n@extends: class.a\n@version: 1.0.0\n",
        encoding="utf-8",
    )
    (object_dir / "obj.a.yaml").write_text(
        "@object: obj.a\n@extends: class.a\n@version: 1.0.0\n",
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
    assert result.has_errors
    assert any(d.code == "E8804" and "inheritance cycle detected" in d.message for d in result.diagnostics)
