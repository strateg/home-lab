#!/usr/bin/env python3
"""Side-by-side parity checks for v4/v5 ip_allocation host_os_ref semantics."""

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
V5_PLUGIN_ID = "base.validator.network_ip_allocation_host_os_refs"


def _load_v4_network_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_network_checks_ip_alloc_host_os", V4_NETWORK_CHECKS)
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


def test_ip_allocation_requires_host_or_device_ref_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_ip_allocation_host_os_refs(
        topology={
            "L2_network": {"networks": [{"id": "vlan-a", "ip_allocations": [{"ip": "10.0.30.10"}]}]},
            "L4_platform": {"host_operating_systems": [{"id": "hos-a", "device_ref": "srv-a"}]},
        },
        ids={},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("either host_os_ref or device_ref is required" in message for message in v4_errors)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "hos-a", "class_ref": "class.os"},
            {
                "group": "network",
                "instance": "vlan-a",
                "class_ref": "class.network.vlan",
                "extensions": {"ip_allocations": [{"ip": "10.0.30.10"}]},
            },
        ],
    )
    result = registry.execute_plugin(V5_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7827" for diag in result.diagnostics)


def test_device_ref_without_host_os_ref_warns_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_ip_allocation_host_os_refs(
        topology={
            "L2_network": {
                "networks": [{"id": "vlan-a", "ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a"}]}]
            },
            "L4_platform": {"host_operating_systems": [{"id": "hos-a", "device_ref": "srv-a"}]},
        },
        ids={},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("device_ref 'srv-a'" in message for message in v4_warnings)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "hos-a", "class_ref": "class.os"},
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "os_refs": ["hos-a"]},
            {
                "group": "network",
                "instance": "vlan-a",
                "class_ref": "class.network.vlan",
                "ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a"}],
            },
        ],
    )
    result = registry.execute_plugin(V5_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7828" for diag in result.diagnostics)
