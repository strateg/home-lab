#!/usr/bin/env python3
"""Integration tests for IP derivation compiler plugin (ADR 0111)."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.compiler.ip_derivation"


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
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def _vlan_row() -> dict:
    return {
        "group": "network",
        "instance": "inst.vlan.a",
        "class_ref": "class.network.vlan",
        "cidr": "10.0.30.0/24",
    }


def _bridge_row() -> dict:
    return {
        "group": "network",
        "instance": "inst.bridge.b",
        "class_ref": "class.network.bridge",
        "cidr": "172.18.0.0/24",
    }


def test_ip_derivation_resolves_vlan_ref_host():
    registry = _registry()
    ctx = _context()
    workload = {
        "group": "lxc",
        "instance": "lxc-a",
        "class_ref": "class.compute.workload.lxc",
        "extensions": {"network": {"vlan_ref": "inst.vlan.a", "host": 10}},
    }
    _publish_rows(ctx, [_vlan_row(), workload])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []
    network = workload["extensions"]["network"]
    assert network["_resolved_ip"] == "10.0.30.10/24"
    assert network["_resolved_gateway"] == "10.0.30.1"


def test_ip_derivation_resolves_bridge_ref_host():
    registry = _registry()
    ctx = _context()
    workload = {
        "group": "routeros_container",
        "instance": "docker-x",
        "class_ref": "class.compute.workload.routeros_container",
        "extensions": {"network": {"bridge_ref": "inst.bridge.b", "host": 2}},
    }
    _publish_rows(ctx, [_bridge_row(), workload])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []
    network = workload["extensions"]["network"]
    assert network["_resolved_ip"] == "172.18.0.2/24"
    assert network["_resolved_gateway"] == "172.18.0.1"


def test_ip_derivation_prefers_vlan_ref_over_bridge_ref():
    registry = _registry()
    ctx = _context()
    workload = {
        "group": "docker",
        "instance": "docker-y",
        "class_ref": "class.compute.workload.docker",
        "extensions": {
            "network": {
                "vlan_ref": "inst.vlan.a",
                "bridge_ref": "inst.bridge.b",
                "host": 20,
            }
        },
    }
    _publish_rows(ctx, [_vlan_row(), _bridge_row(), workload])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    network = workload["extensions"]["network"]
    assert network["_resolved_ip"] == "10.0.30.20/24"


def test_ip_derivation_warns_on_hardcoded_ip():
    registry = _registry()
    ctx = _context()
    workload = {
        "group": "lxc",
        "instance": "lxc-legacy",
        "class_ref": "class.compute.workload.lxc",
        "extensions": {"network": {"ip": "10.0.30.99/24"}},
    }
    _publish_rows(ctx, [_vlan_row(), workload])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert any(diag.code == "W7864" for diag in result.diagnostics)


def test_ip_derivation_rejects_mixed_bridge_ref_and_ip():
    registry = _registry()
    ctx = _context()
    workload = {
        "group": "routeros_container",
        "instance": "docker-x",
        "class_ref": "class.compute.workload.routeros_container",
        "extensions": {"network": {"bridge_ref": "inst.bridge.b", "host": 2, "ip": "172.18.0.2/24"}},
    }
    _publish_rows(ctx, [_bridge_row(), workload])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert any(diag.code == "E7865" for diag in result.diagnostics)


def test_ip_derivation_detects_duplicate_host_within_bridge():
    registry = _registry()
    ctx = _context()
    workload_a = {
        "group": "routeros_container",
        "instance": "docker-x",
        "class_ref": "class.compute.workload.routeros_container",
        "extensions": {"network": {"bridge_ref": "inst.bridge.b", "host": 2}},
    }
    workload_b = {
        "group": "routeros_container",
        "instance": "docker-y",
        "class_ref": "class.compute.workload.routeros_container",
        "extensions": {"network": {"bridge_ref": "inst.bridge.b", "host": 2}},
    }
    _publish_rows(ctx, [_bridge_row(), workload_a, workload_b])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert any(diag.code == "E7861" for diag in result.diagnostics)


def test_ip_derivation_errors_on_unknown_bridge_ref():
    registry = _registry()
    ctx = _context()
    workload = {
        "group": "routeros_container",
        "instance": "docker-x",
        "class_ref": "class.compute.workload.routeros_container",
        "extensions": {"network": {"bridge_ref": "inst.bridge.missing", "host": 2}},
    }
    _publish_rows(ctx, [workload])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert any(diag.code == "E7866" for diag in result.diagnostics)
