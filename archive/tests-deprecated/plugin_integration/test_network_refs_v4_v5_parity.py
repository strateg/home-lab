#!/usr/bin/env python3
"""Side-by-side parity checks for v4/v5 network warning and error semantics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry
from kernel.plugin_base import Stage

V4_NETWORK_CHECKS = (
    Path(__file__).resolve().parents[3] / "v4" / "topology-tools" / "scripts" / "validators" / "checks" / "network.py"
)
V5_MTU_PLUGIN_ID = "base.validator.network_mtu_consistency"
V5_REACHABILITY_PLUGIN_ID = "base.validator.network_runtime_reachability"
V5_FIREWALL_ADDRESSABILITY_PLUGIN_ID = "base.validator.network_firewall_addressability"
V5_NETWORK_CORE_REFS_PLUGIN_ID = "base.validator.network_core_refs"


def _load_v4_network_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_network_checks", V4_NETWORK_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 network checks module from {V4_NETWORK_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_network_mtu_jumbo_conflict_is_error_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_mtu_consistency(
        topology={
            "L2_network": {
                "networks": [
                    {
                        "id": "net-a",
                        "mtu": 1500,
                        "jumbo_frames": True,
                    }
                ]
            }
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("jumbo_frames is true but mtu (1500) <= 1500" in message for message in v4_errors)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "extensions": {"mtu": 1500, "jumbo_frames": True},
            }
        ],
    )
    result = registry.execute_plugin(V5_MTU_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7840" for diag in result.diagnostics)


def test_runtime_target_unreachable_is_warning_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_runtime_network_reachability(
        topology={
            "L2_network": {
                "networks": [
                    {
                        "id": "net-a",
                        "ip_allocations": [],
                    }
                ]
            },
            "L4_platform": {"host_operating_systems": [], "lxc": [], "vms": []},
            "L5_application": {
                "services": [
                    {
                        "id": "svc-a",
                        "runtime": {
                            "type": "docker",
                            "target_ref": "srv-a",
                            "network_binding_ref": "net-a",
                        },
                    }
                ]
            },
        },
        ids={},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("runtime target 'srv-a' has no reachable ownership/attachment" in message for message in v4_warnings)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "extensions": {"ip_allocations": []},
            },
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "runtime": {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.a"},
            },
        ],
    )
    result = registry.execute_plugin(V5_REACHABILITY_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7844" for diag in result.diagnostics)


def test_runtime_reachability_ignores_mapped_host_os_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_runtime_network_reachability(
        topology={
            "L2_network": {
                "networks": [
                    {
                        "id": "net-a",
                        "ip_allocations": [{"host_os_ref": "hos-a"}],
                    }
                ]
            },
            "L4_platform": {
                "host_operating_systems": [{"id": "hos-a", "device_ref": "srv-a", "status": "mapped"}],
                "lxc": [],
                "vms": [],
            },
            "L5_application": {
                "services": [
                    {
                        "id": "svc-a",
                        "runtime": {
                            "type": "docker",
                            "target_ref": "srv-a",
                            "network_binding_ref": "net-a",
                        },
                    }
                ]
            },
        },
        ids={},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("has no reachable ownership/attachment" in message for message in v4_warnings)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": ["hos-a"]},
            {"group": "os", "instance": "hos-a", "class_ref": "class.os", "layer": "L1", "status": "mapped"},
            {
                "group": "network",
                "instance": "net-a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "extensions": {"ip_allocations": [{"host_os_ref": "hos-a"}]},
            },
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "runtime": {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "net-a"},
            },
        ],
    )
    result = registry.execute_plugin(V5_REACHABILITY_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7844" for diag in result.diagnostics)


def test_runtime_reachability_top_level_network_fields_match_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_runtime_network_reachability(
        topology={
            "L2_network": {
                "networks": [
                    {
                        "id": "net-a",
                        "ip_allocations": [{"device_ref": "srv-a"}],
                    }
                ]
            },
            "L4_platform": {
                "host_operating_systems": [],
                "lxc": [{"id": "lxc-a", "networks": [{"network_ref": "net-a"}]}],
                "vms": [],
            },
            "L5_application": {
                "services": [
                    {
                        "id": "svc-a",
                        "runtime": {
                            "type": "lxc",
                            "target_ref": "lxc-a",
                            "network_binding_ref": "net-a",
                        },
                    }
                ]
            },
        },
        ids={},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert v4_warnings == []

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
            {
                "group": "network",
                "instance": "net-a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "ip_allocations": [{"device_ref": "srv-a"}],
            },
            {
                "group": "lxc",
                "instance": "lxc-a",
                "class_ref": "class.compute.workload.container",
                "layer": "L4",
                "networks": [{"network_ref": "net-a"}],
            },
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "runtime": {"type": "lxc", "target_ref": "lxc-a", "network_binding_ref": "net-a"},
            },
        ],
    )
    result = registry.execute_plugin(V5_REACHABILITY_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.diagnostics == []


def test_firewall_addressability_dhcp_warning_is_emitted_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_firewall_policy_addressability(
        topology={
            "L2_network": {
                "networks": [{"id": "net-a", "cidr": "dhcp", "trust_zone_ref": "zone-a"}],
                "firewall_policies": [{"id": "fw-a", "source_network_ref": "net-a", "source_zone_ref": "zone-a"}],
            }
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("resolves to dynamic CIDR ('dhcp')" in message for message in v4_warnings)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "network",
                "instance": "zone-a",
                "class_ref": "class.network.trust_zone",
                "layer": "L2",
            },
            {
                "group": "network",
                "instance": "net-a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "cidr": "dhcp",
                "trust_zone_ref": "zone-a",
            },
            {
                "group": "network",
                "instance": "fw-a",
                "class_ref": "class.network.firewall_policy",
                "layer": "L2",
                "source_network_ref": "net-a",
                "source_zone_ref": "zone-a",
            },
        ],
    )
    result = registry.execute_plugin(V5_FIREWALL_ADDRESSABILITY_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7824" for diag in result.diagnostics)


def test_network_bridge_ref_missing_is_error_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_network_refs(
        topology={
            "L1_foundation": {"devices": [{"id": "rtr-a", "class": "network"}]},
            "L2_network": {
                "network_profiles": {},
                "trust_zones": {"zone-a": {}},
                "firewall_policies": [],
                "networks": [{"id": "net-a", "bridge_ref": "bridge-missing", "trust_zone_ref": "zone-a"}],
            },
        },
        ids={
            "bridges": set(),
            "trust_zones": {"zone-a"},
            "network_profiles": set(),
            "devices": {"rtr-a"},
            "interfaces": set(),
            "firewall_policies": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("bridge_ref 'bridge-missing' does not exist" in message for message in v4_errors)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "rtr-a", "class_ref": "class.router", "layer": "L1"},
            {"group": "network", "instance": "zone-a", "class_ref": "class.network.trust_zone", "layer": "L2"},
            {
                "group": "network",
                "instance": "net-a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "bridge_ref": "bridge-missing",
                "trust_zone_ref": "zone-a",
            },
        ],
    )
    result = registry.execute_plugin(V5_NETWORK_CORE_REFS_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7833" for diag in result.diagnostics)
