#!/usr/bin/env python3
"""Side-by-side parity checks for v4/v5 data-link endpoint semantics."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry
from kernel.plugin_base import Stage

V4_NETWORK_CHECKS = REPO_ROOT / "v4" / "topology-tools" / "scripts" / "validators" / "checks" / "network.py"
NETWORK_PLUGIN_ID = "object_network.validator_json.ethernet_cable_endpoints"
NETWORK_PLUGIN_MANIFEST = REPO_ROOT / "topology" / "object-modules" / "network" / "plugins.yaml"


def _load_v4_network_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_network_checks", V4_NETWORK_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 network checks module from {V4_NETWORK_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            "hardware_specs": {"interfaces": {"optical": [{"name": "sfp1"}]}},
        },
        "obj.device.router_b": {
            "class_ref": "class.router",
            "hardware_specs": {"interfaces": {"optical": [{"name": "sfp2"}]}},
        },
        "obj.network.fiber_channel": {
            "class_ref": "class.network.data_link",
            "properties": {"link_type": "fiber", "medium": "optical"},
        },
    }


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=copy.deepcopy(_base_objects()),
        instance_bindings=copy.deepcopy(_base_bindings()),
    )


def test_data_link_power_delivery_non_ethernet_is_error_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_data_links(
        topology={
            "L1_foundation": {
                "devices": [
                    {"id": "srv-a", "substrate": "baremetal-owned", "interfaces": [{"id": "sfp1"}]},
                    {"id": "srv-b", "substrate": "baremetal-owned", "interfaces": [{"id": "sfp2"}]},
                ],
                "data_links": [
                    {
                        "id": "link-fiber",
                        "endpoint_a": {"device_ref": "srv-a", "interface_ref": "sfp1"},
                        "endpoint_b": {"device_ref": "srv-b", "interface_ref": "sfp2"},
                        "medium": "fiber",
                        "power_delivery": {"mode": "poe"},
                    }
                ],
            }
        },
        ids={"devices": {"srv-a", "srv-b"}, "interfaces": {"sfp1", "sfp2"}},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("power_delivery is allowed only on medium 'ethernet'" in message for message in v4_errors)

    registry = _registry_for_network_validator()
    ctx = _context()
    channel = ctx.instance_bindings["instance_bindings"]["data-channels"][0]
    channel["power_delivery"] = {"mode": "poe"}
    result = registry.execute_plugin(NETWORK_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7310" for diag in result.diagnostics)


def test_data_link_endpoint_missing_device_or_external_is_error_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_data_links(
        topology={
            "L1_foundation": {
                "devices": [
                    {"id": "srv-a", "substrate": "baremetal-owned", "interfaces": [{"id": "sfp1"}]},
                    {"id": "srv-b", "substrate": "baremetal-owned", "interfaces": [{"id": "sfp2"}]},
                ],
                "data_links": [
                    {
                        "id": "link-fiber",
                        "endpoint_a": {"interface_ref": "sfp1"},
                        "endpoint_b": {"device_ref": "srv-b", "interface_ref": "sfp2"},
                        "medium": "fiber",
                    }
                ],
            }
        },
        ids={"devices": {"srv-a", "srv-b"}, "interfaces": {"sfp1", "sfp2"}},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("either device_ref or external_ref is required" in message for message in v4_errors)

    registry = _registry_for_network_validator()
    ctx = _context()
    channel = ctx.instance_bindings["instance_bindings"]["data-channels"][0]
    channel["endpoint_a"] = {"interface_ref": "sfp1"}
    result = registry.execute_plugin(NETWORK_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any("either device_ref or external_ref" in diag.message for diag in result.diagnostics)
