#!/usr/bin/env python3
"""Integration tests for network core refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_core_refs"


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


def _valid_rows() -> list[dict]:
    return [
        {"group": "devices", "instance": "rtr-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor", "layer": "L1"},
        {"group": "network", "instance": "inst.zone.a", "class_ref": "class.network.trust_zone", "layer": "L2"},
        {"group": "network", "instance": "inst.bridge.a", "class_ref": "class.network.bridge", "layer": "L2", "extensions": {"host_ref": "srv-a"}},
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
            "extensions": {
                "bridge_ref": "inst.bridge.a",
                "trust_zone_ref": "inst.zone.a",
                "managed_by_ref": "rtr-a",
            },
        },
    ]


def test_network_core_refs_validator_accepts_valid_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _valid_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_core_refs_validator_rejects_unknown_bridge_ref():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["extensions"]["bridge_ref"] = "inst.bridge.missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7833" for diag in result.diagnostics)


def test_network_core_refs_validator_rejects_wrong_managed_by_ref_class():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["extensions"]["managed_by_ref"] = "srv-a"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7835" for diag in result.diagnostics)


def test_network_core_refs_validator_rejects_bridge_host_ref_non_l1_target():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[3]["extensions"]["host_ref"] = "inst.zone.a"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7836" for diag in result.diagnostics)


def test_network_core_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7837" for diag in result.diagnostics)
