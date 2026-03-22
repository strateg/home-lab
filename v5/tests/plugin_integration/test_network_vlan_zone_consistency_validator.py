#!/usr/bin/env python3
"""Integration tests for VLAN/trust-zone consistency validator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_vlan_zone_consistency"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _objects() -> dict:
    return {
        "obj.network.vlan.a": {
            "class_ref": "class.network.vlan",
            "properties": {"vlan_id": 30, "trust_zone_ref": "inst.zone.a"},
        },
        "obj.network.zone.a": {
            "class_ref": "class.network.trust_zone",
            "properties": {"vlan_ids": [30, 40]},
        },
    }


def _rows() -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.zone.a",
            "class_ref": "class.network.trust_zone",
            "object_ref": "obj.network.zone.a",
        },
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.network.vlan.a",
        },
    ]


def _context() -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
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


def test_network_vlan_zone_consistency_validator_accepts_matching_vlan_id():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_vlan_zone_consistency_validator_warns_on_vlan_id_mismatch():
    registry = _registry()
    ctx = _context()
    ctx.objects["obj.network.zone.a"]["properties"]["vlan_ids"] = [40, 50]  # type: ignore[index]
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7830" for diag in result.diagnostics)


def test_network_vlan_zone_consistency_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7829" for diag in result.diagnostics)
