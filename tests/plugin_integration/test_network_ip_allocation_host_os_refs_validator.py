#!/usr/bin/env python3
"""Integration tests for network ip_allocation host_os_ref validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_ip_allocation_host_os_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
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


def test_network_ip_allocation_host_os_refs_validator_accepts_valid_host_os_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "os_refs": ["inst.os.a"]},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "extensions": {
                    "ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a", "host_os_ref": "inst.os.a"}]
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_ip_allocation_host_os_refs_validator_rejects_unknown_host_os_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "extensions": {
                    "ip_allocations": [
                        {"ip": "10.0.30.10", "device_ref": "srv-a", "host_os_ref": "inst.os.missing"},
                    ]
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7827" for diag in result.diagnostics)


def test_network_ip_allocation_host_os_refs_validator_warns_on_device_ref_without_host_os_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "extensions": {"ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a"}]},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7828" for diag in result.diagnostics)


def test_network_ip_allocation_host_os_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7827" for diag in result.diagnostics)


def test_network_ip_allocation_host_os_refs_validator_requires_host_or_device_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "extensions": {"ip_allocations": [{"ip": "10.0.30.10"}]},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7827" for diag in result.diagnostics)


def test_network_ip_allocation_host_os_refs_validator_supports_top_level_payload():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "os_refs": ["inst.os.a"]},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a"}],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7828" for diag in result.diagnostics)
