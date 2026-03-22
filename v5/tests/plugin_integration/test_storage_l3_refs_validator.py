#!/usr/bin/env python3
"""Integration tests for storage L3 refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.storage_l3_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context() -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
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


def test_storage_l3_refs_validator_accepts_valid_volume_and_asset_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "storage", "instance": "inst.storage.pool.a", "class_ref": "class.storage.pool", "layer": "L3"},
            {
                "group": "storage",
                "instance": "inst.storage.volume.a",
                "class_ref": "class.storage.volume",
                "layer": "L3",
                "extensions": {"pool_ref": "inst.storage.pool.a"},
            },
            {
                "group": "storage",
                "instance": "inst.storage.asset.a",
                "class_ref": "class.storage.data_asset",
                "layer": "L3",
                "extensions": {"volume_ref": "inst.storage.volume.a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_storage_l3_refs_validator_rejects_unknown_pool_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "inst.storage.volume.a",
                "class_ref": "class.storage.volume",
                "layer": "L3",
                "extensions": {"pool_ref": "inst.storage.pool.missing"},
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7831" for diag in result.diagnostics)


def test_storage_l3_refs_validator_rejects_wrong_asset_volume_target_class():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "storage", "instance": "inst.storage.pool.a", "class_ref": "class.storage.pool", "layer": "L3"},
            {
                "group": "storage",
                "instance": "inst.storage.asset.a",
                "class_ref": "class.storage.data_asset",
                "layer": "L3",
                "extensions": {"volume_ref": "inst.storage.pool.a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7832" for diag in result.diagnostics)


def test_storage_l3_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7830" for diag in result.diagnostics)
