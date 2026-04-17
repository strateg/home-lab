#!/usr/bin/env python3
"""Integration tests for single active OS validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.single_active_os"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_single_active_os_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def test_single_active_os_validator_accepts_single_active_os_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os", "status": "active"},
            {"group": "os", "instance": "inst.os.b", "class_ref": "class.os", "status": "mapped"},
            {
                "group": "devices",
                "instance": "rtr-1",
                "class_ref": "class.router",
                "os_refs": ["inst.os.a", "inst.os.b"],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_single_active_os_validator_rejects_multiple_active_os_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os", "status": "active"},
            {"group": "os", "instance": "inst.os.b", "class_ref": "class.os", "status": "ACTIVE"},
            {
                "group": "devices",
                "instance": "rtr-1",
                "class_ref": "class.router",
                "os_refs": ["inst.os.a", "inst.os.b"],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7817" for diag in result.diagnostics)


def test_single_active_os_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_single_active_os_validator_ignores_legacy_inventory_without_os_rows():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "legacy-rtr",
                "class_ref": "class.router",
                "os_refs": ["inst.os.missing.a", "inst.os.missing.b"],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_single_active_os_validator_ignores_non_os_targets_in_os_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "firmware", "instance": "inst.fw.a", "class_ref": "class.firmware", "status": "active"},
            {"group": "firmware", "instance": "inst.fw.b", "class_ref": "class.firmware", "status": "active"},
            {
                "group": "devices",
                "instance": "legacy-rtr",
                "class_ref": "class.router",
                "os_refs": ["inst.fw.a", "inst.fw.b"],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_single_active_os_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/instance_rows_compiler.py').as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": "validator_json",
                "entry": f"{(V5_TOOLS / 'plugins/validators/single_active_os_validator.py').as_posix()}:SingleActiveOsValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 117,
                "depends_on": ["base.compiler.instance_rows"],
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True}
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)
