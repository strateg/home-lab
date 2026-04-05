#!/usr/bin/env python3
"""Integration tests for network IP overlap validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.network_ip_overlap"


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


def test_network_ip_overlap_validator_accepts_unique_ips():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"instance": "inst.router.a", "ip_address": "192.168.10.1/24"},
            {"instance": "inst.router.b", "ip_address": "192.168.10.2/24"},
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_ip_overlap_validator_reports_duplicate_ips():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"instance": "inst.router.a", "ip_address": "10.0.0.1/24"},
            {"instance": "inst.router.b", "management_ip": "10.0.0.1"},
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7816" for diag in result.diagnostics)


def test_network_ip_overlap_validator_reports_duplicate_network_ip_allocations_as_error():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "network",
                "instance": "vlan-a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "extensions": {
                    "ip_allocations": [
                        {"ip": "10.20.30.10/24", "device_ref": "srv-a"},
                        {"ip": "10.20.30.10/24", "vm_ref": "vm-a"},
                    ]
                },
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7817" for diag in result.diagnostics)


def test_network_ip_overlap_validator_reports_duplicate_network_ip_allocations_from_top_level_payload():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "network",
                "instance": "vlan-a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "ip_allocations": [
                    {"ip": "10.20.30.11/24", "device_ref": "srv-a"},
                    {"ip": "10.20.30.11/24", "lxc_ref": "lxc-a"},
                ],
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7817" for diag in result.diagnostics)


def test_network_ip_overlap_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7815" for diag in result.diagnostics)


def test_network_ip_overlap_validator_ignores_observed_runtime_ips():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "instance": "rtr-mikrotik-chateau",
                "extensions": {
                    "observed_runtime": {
                        "containers": {"bridge_ip": "172.18.0.1"},
                    }
                },
            },
            {
                "instance": "docker-nginx",
                "extensions": {
                    "network": {"gateway": "172.18.0.1"},
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(diag.code == "W7816" for diag in result.diagnostics)
