#!/usr/bin/env python3
"""Integration tests for runtime network reachability validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_runtime_reachability"


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


def _base_rows() -> list[dict]:
    return [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": ["inst.os.a"]},
        {"group": "os", "instance": "inst.os.a", "class_ref": "class.os", "layer": "L1", "status": "active"},
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
            "extensions": {"ip_allocations": [{"device_ref": "srv-a", "host_os_ref": "inst.os.a"}]},
        },
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.container",
            "layer": "L4",
            "extensions": {"networks": [{"network_ref": "inst.vlan.a"}]},
        },
        {
            "group": "services",
            "instance": "svc-a",
            "class_ref": "class.service.monitoring",
            "layer": "L5",
            "runtime": {"type": "lxc", "target_ref": "lxc-a", "network_binding_ref": "inst.vlan.a"},
        },
    ]


def test_network_runtime_reachability_validator_accepts_lxc_with_network_attachment():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_warns_on_lxc_network_mismatch():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[3]["extensions"]["networks"][0]["network_ref"] = "inst.vlan.other"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7844" for diag in result.diagnostics)


def test_network_runtime_reachability_validator_warns_on_unreachable_docker_target():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-b", "network_binding_ref": "inst.vlan.a"}
    rows.append({"group": "devices", "instance": "srv-b", "class_ref": "class.router", "layer": "L1", "os_refs": []})
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7844" for diag in result.diagnostics)


def test_network_runtime_reachability_validator_accepts_reachable_docker_target():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.a"}
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7843" for diag in result.diagnostics)


def test_network_runtime_reachability_validator_supports_top_level_network_fields():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[2].pop("extensions")  # type: ignore[index]
    rows[2]["ip_allocations"] = [{"device_ref": "srv-a", "host_os_ref": "inst.os.a"}]  # type: ignore[index]
    rows[3].pop("extensions")  # type: ignore[index]
    rows[3]["networks"] = [{"network_ref": "inst.vlan.a"}]  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_treats_mapped_host_os_as_unreachable():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["status"] = "mapped"  # type: ignore[index]
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.a"}
    rows[2]["extensions"] = {"ip_allocations": [{"host_os_ref": "inst.os.a"}]}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7844" for diag in result.diagnostics)
