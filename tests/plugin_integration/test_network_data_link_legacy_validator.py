#!/usr/bin/env python3
"""Integration tests for legacy data-link semantics in network endpoint validator."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

NETWORK_PLUGIN_ID = "object.network.validator_json.ethernet_cable_endpoints"
NETWORK_PLUGIN_MANIFEST = REPO_ROOT / "topology" / "object-modules" / "network" / "plugins.yaml"


def _registry_for_network_validator() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(NETWORK_PLUGIN_MANIFEST)
    return registry


def _base_bindings() -> dict[str, Any]:
    return {
        "instance_bindings": {
            "devices": [
                {"instance": "srv-a", "class_ref": "class.router", "object_ref": "obj.device.router_a", "layer": "L1"},
                {"instance": "srv-b", "class_ref": "class.router", "object_ref": "obj.device.router_b", "layer": "L1"},
                {
                    "instance": "vps-a",
                    "class_ref": "class.compute.workload.vm",
                    "object_ref": "obj.device.cloud_vm",
                    "layer": "L1",
                },
            ],
            "data-channels": [
                {
                    "instance": "inst.chan.fiber.srv-a-to-srv-b",
                    "class_ref": "class.network.data_link",
                    "object_ref": "obj.network.fiber_channel",
                    "layer": "L2",
                    "endpoint_a": {"device_ref": "srv-a", "interface_ref": "sfp1"},
                    "endpoint_b": {"device_ref": "srv-b", "interface_ref": "sfp2"},
                    "medium": "fiber",
                }
            ],
        }
    }


def _base_objects() -> dict[str, Any]:
    return {
        "obj.device.router_a": {
            "class_ref": "class.router",
            "hardware_specs": {
                "interfaces": {
                    "ethernet": [{"name": "ether1"}],
                    "optical": [{"name": "sfp1"}],
                }
            },
        },
        "obj.device.router_b": {
            "class_ref": "class.router",
            "hardware_specs": {
                "interfaces": {
                    "ethernet": [{"name": "ether2"}],
                    "optical": [{"name": "sfp2"}],
                }
            },
        },
        "obj.device.cloud_vm": {
            "class_ref": "class.compute.workload.vm",
            "hardware_specs": {"interfaces": {"virtual": [{"name": "eth0"}]}},
        },
        "obj.network.fiber_channel": {
            "class_ref": "class.network.data_link",
            "properties": {"link_type": "fiber", "medium": "optical"},
        },
    }


def _new_context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test-real",
        model_lock={},
        classes={},
        objects=copy.deepcopy(_base_objects()),
        instance_bindings=copy.deepcopy(_base_bindings()),
    )


def _find_row(bindings: dict[str, Any], *, instance_id: str) -> dict[str, Any]:
    groups = bindings["instance_bindings"]
    for rows in groups.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("instance") == instance_id:
                return row
    raise AssertionError(f"Instance not found: {instance_id}")


def _run_network_validator(modify: Callable[[PluginContext], None] | None = None):
    registry = _registry_for_network_validator()
    ctx = _new_context()
    if modify:
        modify(ctx)
    return registry.execute_plugin(NETWORK_PLUGIN_ID, ctx, Stage.VALIDATE)


def test_legacy_data_link_semantics_accept_valid_fiber_row():
    result = _run_network_validator()
    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors


def test_legacy_data_link_semantics_reject_endpoint_without_device_or_external_ref():
    def _modify(ctx: PluginContext) -> None:
        channel = _find_row(ctx.instance_bindings, instance_id="inst.chan.fiber.srv-a-to-srv-b")
        channel["endpoint_a"] = {"interface_ref": "sfp1"}

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7309" for diag in result.diagnostics)


def test_legacy_data_link_semantics_reject_provider_instance_endpoint():
    def _modify(ctx: PluginContext) -> None:
        channel = _find_row(ctx.instance_bindings, instance_id="inst.chan.fiber.srv-a-to-srv-b")
        channel["endpoint_a"] = {"device_ref": "vps-a"}

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any("provider-instance" in diag.message for diag in result.diagnostics)


def test_legacy_data_link_semantics_reject_interface_owner_mismatch():
    def _modify(ctx: PluginContext) -> None:
        channel = _find_row(ctx.instance_bindings, instance_id="inst.chan.fiber.srv-a-to-srv-b")
        channel["endpoint_a"]["interface_ref"] = "sfp2"

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7309" for diag in result.diagnostics)


def test_legacy_data_link_semantics_reject_power_delivery_on_non_ethernet_link():
    def _modify(ctx: PluginContext) -> None:
        channel = _find_row(ctx.instance_bindings, instance_id="inst.chan.fiber.srv-a-to-srv-b")
        channel["power_delivery"] = {"mode": "poe"}

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7310" for diag in result.diagnostics)


def test_legacy_data_link_semantics_reject_non_poe_power_delivery_mode():
    def _modify(ctx: PluginContext) -> None:
        channel = _find_row(ctx.instance_bindings, instance_id="inst.chan.fiber.srv-a-to-srv-b")
        channel["medium"] = "ethernet"
        channel["power_delivery"] = {"mode": "af"}

    result = _run_network_validator(_modify)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7310" for diag in result.diagnostics)
