#!/usr/bin/env python3
"""Integration tests for firewall addressability validator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_firewall_addressability"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _objects() -> dict:
    return {
        "obj.network.vlan.a": {
            "class_ref": "class.network.vlan",
            "properties": {"cidr": "10.0.30.0/24", "trust_zone_ref": "inst.zone.a"},
        },
        "obj.network.firewall_policy.a": {
            "class_ref": "class.network.firewall_policy",
            "properties": {
                "source_network_ref": "inst.vlan.a",
                "source_zone_ref": "inst.zone.a",
                "destination_zone_ref": "inst.zone.a",
            },
        },
    }


def _rows() -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.zone.a",
            "class_ref": "class.network.trust_zone",
            "object_ref": "obj.zone.a",
            "extensions": {},
        },
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.network.vlan.a",
            "extensions": {},
        },
        {
            "group": "network",
            "instance": "inst.fw.a",
            "class_ref": "class.network.firewall_policy",
            "object_ref": "obj.network.firewall_policy.a",
            "extensions": {},
        },
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


def test_network_firewall_addressability_validator_accepts_static_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_firewall_addressability_validator_warns_on_dhcp_network_ref():
    registry = _registry()
    ctx = _context()
    ctx.objects["obj.network.vlan.a"]["properties"]["cidr"] = "dhcp"  # type: ignore[index]
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7824" for diag in result.diagnostics)


def test_network_firewall_addressability_validator_warns_on_zone_without_static_networks():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows = [row for row in rows if row["instance"] != "inst.vlan.a"]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7824" for diag in result.diagnostics)


def test_network_firewall_addressability_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7823" for diag in result.diagnostics)


def test_network_firewall_addressability_validator_supports_top_level_payload():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows[1].pop("object_ref")  # type: ignore[index]
    rows[1]["cidr"] = "dhcp"  # type: ignore[index]
    rows[1]["trust_zone_ref"] = "inst.zone.a"  # type: ignore[index]
    rows[2].pop("object_ref")  # type: ignore[index]
    rows[2]["source_network_ref"] = "inst.vlan.a"  # type: ignore[index]
    rows[2]["source_zone_ref"] = "inst.zone.a"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7824" for diag in result.diagnostics)


def test_network_firewall_addressability_validator_warns_on_destination_zones_scope_edge():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows.append(
        {
            "group": "network",
            "instance": "inst.zone.b",
            "class_ref": "class.network.trust_zone",
            "layer": "L2",
            "extensions": {},
        }
    )
    rows[-2].pop("object_ref")  # type: ignore[index]
    rows[-2]["source_zone_ref"] = "inst.zone.a"  # type: ignore[index]
    rows[-2]["destination_zones_ref"] = ["inst.zone.a", "inst.zone.b"]  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7824" and "inst.zone.b" in diag.message for diag in result.diagnostics)


def test_network_firewall_addressability_validator_skips_untrusted_scope_entries():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows = [row for row in rows if row["instance"] in {"inst.zone.a", "inst.fw.a"}]
    rows[-1].pop("object_ref")  # type: ignore[index]
    rows[-1]["source_zone_ref"] = "untrusted"  # type: ignore[index]
    rows[-1]["destination_zone_ref"] = "untrusted"  # type: ignore[index]
    rows[-1]["destination_zones_ref"] = ["untrusted"]  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []
