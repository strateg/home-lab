#!/usr/bin/env python3
"""Side-by-side parity checks for v4/v5 network reserved_ranges semantics."""

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
V5_PLUGIN_ID = "base.validator.network_reserved_ranges"


def _load_v4_network_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_network_checks_reserved_ranges", V4_NETWORK_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 network checks module from {V4_NETWORK_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(*, objects: dict | None = None) -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=objects or {},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def test_reserved_range_outside_cidr_is_error_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_reserved_ranges(
        topology={
            "L2_network": {
                "networks": [
                    {
                        "id": "vlan-a",
                        "cidr": "10.0.30.0/24",
                        "reserved_ranges": [{"start": "10.0.31.10", "end": "10.0.31.20", "purpose": "bad"}],
                    }
                ]
            }
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("not within CIDR" in message for message in v4_errors)

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
                "cidr": "10.0.30.0/24",
                "reserved_ranges": [{"start": "10.0.31.10", "end": "10.0.31.20", "purpose": "bad"}],
            }
        ],
    )
    result = registry.execute_plugin(V5_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7820" for diag in result.diagnostics)


def test_reserved_ranges_are_ignored_for_dhcp_network_in_v4_and_v5():
    v4_module = _load_v4_network_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_reserved_ranges(
        topology={
            "L2_network": {
                "networks": [
                    {
                        "id": "vlan-a",
                        "cidr": "dhcp",
                        "reserved_ranges": [{"start": "10.0.30.10", "end": "10.0.30.20", "purpose": "ignored"}],
                    }
                ]
            }
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert v4_errors == []

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
                "cidr": "dhcp",
                "reserved_ranges": [{"start": "10.0.30.10", "end": "10.0.30.20", "purpose": "ignored"}],
            }
        ],
    )
    result = registry.execute_plugin(V5_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.diagnostics == []
