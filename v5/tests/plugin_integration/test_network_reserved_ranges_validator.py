#!/usr/bin/env python3
"""Integration tests for network reserved ranges validator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_reserved_ranges"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _objects() -> dict:
    return {
        "obj.network.vlan.a": {
            "class_ref": "class.network.vlan",
            "properties": {
                "cidr": "10.0.30.0/24",
                "reserved_ranges": [
                    {"start": "10.0.30.10", "end": "10.0.30.20", "purpose": "infra"},
                    {"start": "10.0.30.50", "end": "10.0.30.60", "purpose": "services"},
                ],
            },
        }
    }


def _rows() -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.network.vlan.a",
        }
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


def test_network_reserved_ranges_validator_accepts_valid_ranges():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_reserved_ranges_validator_rejects_outside_cidr():
    registry = _registry()
    ctx = _context()
    ctx.objects["obj.network.vlan.a"]["properties"]["reserved_ranges"] = [  # type: ignore[index]
        {"start": "10.0.31.10", "end": "10.0.31.20", "purpose": "bad"},
    ]
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7820" for diag in result.diagnostics)


def test_network_reserved_ranges_validator_rejects_overlaps():
    registry = _registry()
    ctx = _context()
    ctx.objects["obj.network.vlan.a"]["properties"]["reserved_ranges"] = [  # type: ignore[index]
        {"start": "10.0.30.10", "end": "10.0.30.30", "purpose": "a"},
        {"start": "10.0.30.20", "end": "10.0.30.40", "purpose": "b"},
    ]
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7820" for diag in result.diagnostics)


def test_network_reserved_ranges_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7819" for diag in result.diagnostics)


def test_network_reserved_ranges_validator_supports_extensions_payload():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows[0]["extensions"] = {  # type: ignore[index]
        "cidr": "10.0.30.0/24",
        "reserved_ranges": [
            {"start": "10.0.30.10", "end": "10.0.30.20", "purpose": "infra"},
            {"start": "10.0.30.15", "end": "10.0.30.25", "purpose": "overlap"},
        ],
    }
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7820" for diag in result.diagnostics)


def test_network_reserved_ranges_validator_supports_top_level_payload():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows[0]["cidr"] = "10.0.30.0/24"  # type: ignore[index]
    rows[0]["reserved_ranges"] = [  # type: ignore[index]
        {"start": "10.0.31.10", "end": "10.0.31.20", "purpose": "bad"},
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7820" for diag in result.diagnostics)


def test_network_reserved_ranges_validator_skips_dhcp_cidr():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows[0]["cidr"] = "dhcp"  # type: ignore[index]
    rows[0]["reserved_ranges"] = [  # type: ignore[index]
        {"start": "10.0.30.10", "end": "10.0.30.20", "purpose": "ignored"},
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []
