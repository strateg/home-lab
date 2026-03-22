#!/usr/bin/env python3
"""Integration tests for VM refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.vm_refs"


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
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "network", "instance": "tz-a", "class_ref": "class.network.trust_zone", "layer": "L2"},
        {"group": "network", "instance": "vlan-a", "class_ref": "class.network.vlan", "layer": "L2"},
        {"group": "os", "instance": "os-a", "class_ref": "class.os", "layer": "L1"},
        {"group": "storage", "instance": "endpoint-a", "class_ref": "class.storage.storage_endpoint", "layer": "L3"},
        {
            "group": "vms",
            "instance": "vm-a",
            "class_ref": "class.compute.cloud_vm",
            "layer": "L4",
            "extensions": {
                "device_ref": "srv-a",
                "trust_zone_ref": "tz-a",
                "host_os_ref": "os-a",
                "networks": [{"network_ref": "vlan-a"}],
                "storage": [{"storage_endpoint_ref": "endpoint-a"}],
            },
        },
    ]


def test_vm_refs_validator_accepts_valid_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_vm_refs_validator_rejects_unknown_trust_zone_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["trust_zone_ref"] = "tz-missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7872" for diag in result.diagnostics)


def test_vm_refs_validator_rejects_wrong_network_ref_target():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["networks"] = [{"network_ref": "srv-a"}]  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7875" for diag in result.diagnostics)


def test_vm_refs_validator_rejects_host_os_ref_outside_device_os_bindings():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["os_refs"] = ["os-b"]  # type: ignore[index]
    rows.insert(4, {"group": "os", "instance": "os-b", "class_ref": "class.os", "layer": "L1", "status": "active"})
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7873" for diag in result.diagnostics)


def test_vm_refs_validator_requires_host_os_ref_when_multiple_active_device_os_bindings():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["os_refs"] = ["os-a", "os-b"]  # type: ignore[index]
    rows.insert(4, {"group": "os", "instance": "os-b", "class_ref": "class.os", "layer": "L1", "status": "active"})
    rows[-1]["extensions"].pop("host_os_ref")  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7873" for diag in result.diagnostics)


def test_vm_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7870" for diag in result.diagnostics)
