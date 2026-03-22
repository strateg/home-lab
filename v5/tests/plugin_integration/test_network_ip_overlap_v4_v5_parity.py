#!/usr/bin/env python3
"""Side-by-side parity checks for v4/v5 IP overlap semantics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry
from kernel.plugin_base import Stage

V4_GOVERNANCE_CHECKS = (
    Path(__file__).resolve().parents[3] / "v4" / "topology-tools" / "scripts" / "validators" / "checks" / "governance.py"
)
V5_PLUGIN_ID = "base.validator.network_ip_overlap"


def _load_v4_governance_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_governance_checks_ip_overlap", V4_GOVERNANCE_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 governance checks module from {V4_GOVERNANCE_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_duplicate_ip_inside_network_is_error_in_v4_and_v5():
    v4_module = _load_v4_governance_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_ip_overlaps(
        topology={
            "L2_network": {
                "networks": [
                    {
                        "id": "vlan-a",
                        "ip_allocations": [
                            {"ip": "10.20.30.10/24", "device_ref": "srv-a"},
                            {"ip": "10.20.30.10/24", "vm_ref": "vm-a"},
                        ],
                    }
                ]
            }
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("Duplicate IP in network 'vlan-a'" in message for message in v4_errors)

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
    result = registry.execute_plugin(V5_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7817" for diag in result.diagnostics)


def test_global_ip_overlap_is_warning_in_v4_and_v5():
    v4_module = _load_v4_governance_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_ip_overlaps(
        topology={
            "L2_network": {
                "networks": [
                    {"id": "vlan-a", "ip_allocations": [{"ip": "10.20.30.20/24", "device_ref": "srv-a"}]}
                ]
            },
            "L4_platform": {
                "vms": [{"id": "vm-a", "networks": [{"ip_config": {"address": "10.20.30.20/24"}}]}],
                "lxc": [],
            },
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("appears in" in message for message in v4_warnings)

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
                "extensions": {"ip_allocations": [{"ip": "10.20.30.20/24", "device_ref": "srv-a"}]},
            },
            {
                "group": "vms",
                "instance": "vm-a",
                "class_ref": "class.compute.cloud_vm",
                "layer": "L4",
                "extensions": {"networks": [{"ip_config": {"address": "10.20.30.20/24"}}]},
            },
        ],
    )
    result = registry.execute_plugin(V5_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7816" for diag in result.diagnostics)
