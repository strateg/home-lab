#!/usr/bin/env python3
"""Integration tests for L1 power.source_ref validator plugin (ADR0062)."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.power_source_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def test_power_source_validator_skips_when_core_is_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_power_source_refs": "core"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, [])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_power_source_validator_accepts_valid_l1_chain_and_outlets():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "ups-main",
            "layer": "L1",
            "class_ref": "class.power.ups",
            "object_ref": "obj.apc.backups.650va",
            "extensions": {},
        },
        {
            "group": "devices",
            "instance": "pdu-rack",
            "layer": "L1",
            "class_ref": "class.power.pdu",
            "object_ref": "obj.pdu.generic.managed",
            "extensions": {"power": {"source_ref": "ups-main"}},
        },
        {
            "group": "devices",
            "instance": "rtr-a",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.a",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A1"}},
        },
        {
            "group": "devices",
            "instance": "rtr-b",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.b",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A2"}},
        },
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(d.code.startswith("E78") for d in result.diagnostics)


def test_power_source_validator_rejects_unknown_target():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "rtr-a",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.a",
            "extensions": {"power": {"source_ref": "pdu-missing"}},
        }
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7801" for d in result.diagnostics)


def test_power_source_validator_rejects_source_layer_violation():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "pdu-rack",
            "layer": "L1",
            "class_ref": "class.power.pdu",
            "object_ref": "obj.pdu.generic.managed",
            "extensions": {},
        },
        {
            "group": "lxc",
            "instance": "lxc-app",
            "layer": "L4",
            "class_ref": "class.compute.workload.lxc",
            "object_ref": "obj.lxc.app",
            "extensions": {"power": {"source_ref": "pdu-rack"}},
        },
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7803" for d in result.diagnostics)


def test_power_source_validator_rejects_invalid_target_class():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "router-source",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.src",
            "extensions": {},
        },
        {
            "group": "devices",
            "instance": "router-target",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.dst",
            "extensions": {"power": {"source_ref": "router-source"}},
        },
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7802" for d in result.diagnostics)


def test_power_source_validator_rejects_reference_format_errors():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "rtr-a",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.a",
            "extensions": {"power": {"source_ref": []}},
        },
        {
            "group": "devices",
            "instance": "rtr-b",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.b",
            "extensions": {"power": {"source_ref": "ups-main", "outlet_ref": []}},
        },
        {
            "group": "devices",
            "instance": "ups-main",
            "layer": "L1",
            "class_ref": "class.power.ups",
            "object_ref": "obj.apc.backups.650va",
            "extensions": {},
        },
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7804" for d in result.diagnostics)


def test_power_source_validator_rejects_duplicate_outlet_occupancy():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "pdu-rack",
            "layer": "L1",
            "class_ref": "class.power.pdu",
            "object_ref": "obj.pdu.generic.managed",
            "extensions": {},
        },
        {
            "group": "devices",
            "instance": "rtr-a",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.a",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A1"}},
        },
        {
            "group": "devices",
            "instance": "rtr-b",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.b",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A1"}},
        },
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7805" for d in result.diagnostics)


def test_power_source_validator_rejects_cycles():
    registry = _registry()
    rows = [
        {
            "group": "devices",
            "instance": "pdu-a",
            "layer": "L1",
            "class_ref": "class.power.pdu",
            "object_ref": "obj.pdu.a",
            "extensions": {"power": {"source_ref": "ups-b"}},
        },
        {
            "group": "devices",
            "instance": "ups-b",
            "layer": "L1",
            "class_ref": "class.power.ups",
            "object_ref": "obj.ups.b",
            "extensions": {"power": {"source_ref": "pdu-a"}},
        },
    ]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7805" for d in result.diagnostics)
