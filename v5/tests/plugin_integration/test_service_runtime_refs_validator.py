#!/usr/bin/env python3
"""Integration tests for service runtime refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.service_runtime_refs"


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
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "lxc", "instance": "lxc-a", "class_ref": "class.compute.workload.container", "layer": "L4"},
        {"group": "network", "instance": "inst.vlan.a", "class_ref": "class.network.vlan", "layer": "L2"},
        {
            "group": "services",
            "instance": "svc-a",
            "class_ref": "class.service.monitoring",
            "layer": "L5",
            "runtime": {"type": "lxc", "target_ref": "lxc-a", "network_binding_ref": "inst.vlan.a"},
        },
    ]


def test_service_runtime_refs_validator_accepts_valid_runtime_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _valid_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_service_runtime_refs_validator_rejects_unknown_target_ref():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["runtime"]["target_ref"] = "missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7841" for diag in result.diagnostics)


def test_service_runtime_refs_validator_rejects_wrong_runtime_target_type():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["runtime"]["type"] = "docker"  # type: ignore[index]
    rows[-1]["runtime"]["target_ref"] = "lxc-a"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7841" for diag in result.diagnostics)


def test_service_runtime_refs_validator_warns_on_unknown_runtime_type():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["runtime"]["type"] = "custom"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7842" for diag in result.diagnostics)


def test_service_runtime_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7841" for diag in result.diagnostics)
