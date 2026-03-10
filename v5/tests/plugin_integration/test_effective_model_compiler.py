#!/usr/bin/env python3
"""Integration tests for ADR0069 effective model compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.effective_model"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_effective_model_compiler_publishes_candidate():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={
            "class.router": {
                "class": "class.router",
                "version": "1.0.0",
                "required_capabilities": ["cap.net.interface.ethernet"],
            }
        },
        objects={
            "obj.router.test": {
                "object": "obj.router.test",
                "version": "1.0.0",
                "class_ref": "class.router",
                "enabled_capabilities": ["cap.net.interface.ethernet"],
            }
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "rtr-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router.test",
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors
    keys = ctx.get_published_keys(PLUGIN_ID)
    assert "effective_model_candidate" in keys
    assert isinstance(ctx.compiled_json, dict)
    assert "instances" in ctx.compiled_json
    assert "l1_devices" in ctx.compiled_json["instances"]
