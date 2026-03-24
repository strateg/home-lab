#!/usr/bin/env python3
"""Integration tests for network MTU consistency validator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_mtu_consistency"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _objects() -> dict:
    return {
        "obj.vlan.a": {"class_ref": "class.network.vlan", "properties": {"mtu": 9000, "jumbo_frames": True}},
    }


def _rows() -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
            "object_ref": "obj.vlan.a",
        }
    ]


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=copy.deepcopy(_objects()),
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def test_network_mtu_consistency_validator_accepts_valid_jumbo_mtu():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_mtu_consistency_validator_rejects_jumbo_with_small_mtu():
    registry = _registry()
    ctx = _context()
    ctx.objects["obj.vlan.a"]["properties"]["mtu"] = 1500  # type: ignore[index]
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7840" for diag in result.diagnostics)


def test_network_mtu_consistency_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7840" for diag in result.diagnostics)
