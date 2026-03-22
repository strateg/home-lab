#!/usr/bin/env python3
"""Integration tests for backup refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.backup_refs"


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


def _base_rows() -> list[dict]:
    return [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "lxc", "instance": "lxc-a", "class_ref": "class.compute.workload.container", "layer": "L4"},
        {"group": "storage", "instance": "asset-a", "class_ref": "class.storage.data_asset", "layer": "L3"},
        {"group": "storage", "instance": "pool-a", "class_ref": "class.storage.pool", "layer": "L3"},
        {
            "group": "operations",
            "instance": "backup-nightly",
            "class_ref": "class.operations.backup",
            "layer": "L7",
            "extensions": {
                "destination_ref": "pool-a",
                "targets": [
                    {"device_ref": "srv-a"},
                    {"lxc_ref": "lxc-a"},
                    {"data_asset_ref": "asset-a"},
                ],
            },
        },
    ]


def test_backup_refs_validator_accepts_valid_targets():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_backup_refs_validator_rejects_unknown_data_asset_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["targets"][2]["data_asset_ref"] = "asset-missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7858" for diag in result.diagnostics)


def test_backup_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7858" for diag in result.diagnostics)
