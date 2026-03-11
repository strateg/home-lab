#!/usr/bin/env python3
"""Integration tests for instance rows compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.instance_rows"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_instance_rows_compiler_skips_when_core_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "core"},
        instance_bindings={"instance_bindings": {}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data == {"normalized_rows": []}


def test_instance_rows_compiler_plugin_owner_normalizes_rows():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "plugin"},
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "dev-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "custom_flag": True,
                        "endpoint_a": {"device_ref": "a", "port": "eth0"},
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    assert not result.has_errors
    rows = result.output_data.get("normalized_rows")
    assert isinstance(rows, list)
    assert rows and rows[0]["instance"] == "dev-1"
    assert rows[0]["extensions"]["custom_flag"] is True
    assert rows[0]["extensions"]["endpoint_a"]["port"] == "eth0"
    assert "normalized_rows" in ctx.get_published_keys(PLUGIN_ID)
