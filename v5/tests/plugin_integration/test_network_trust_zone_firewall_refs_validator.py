#!/usr/bin/env python3
"""Integration tests for trust-zone firewall refs validator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_trust_zone_firewall_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _objects() -> dict:
    return {
        "obj.network.trust_zone.a": {
            "class_ref": "class.network.trust_zone",
            "properties": {"default_firewall_policy_ref": "inst.fw.policy.a"},
        },
        "obj.network.firewall_policy.a": {
            "class_ref": "class.network.firewall_policy",
            "properties": {"name": "allow-core"},
        },
    }


def _rows() -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.zone.a",
            "class_ref": "class.network.trust_zone",
            "object_ref": "obj.network.trust_zone.a",
        },
        {
            "group": "network",
            "instance": "inst.fw.policy.a",
            "class_ref": "class.network.firewall_policy",
            "object_ref": "obj.network.firewall_policy.a",
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


def test_network_trust_zone_firewall_refs_validator_accepts_valid_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_trust_zone_firewall_refs_validator_rejects_missing_target():
    registry = _registry()
    ctx = _context()
    rows = [row for row in _rows() if row["instance"] != "inst.fw.policy.a"]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7822" for diag in result.diagnostics)


def test_network_trust_zone_firewall_refs_validator_rejects_wrong_target_class():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows[1]["class_ref"] = "class.network.vlan"
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7822" for diag in result.diagnostics)


def test_network_trust_zone_firewall_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7821" for diag in result.diagnostics)
