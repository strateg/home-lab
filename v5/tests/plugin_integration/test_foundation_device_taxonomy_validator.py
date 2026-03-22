#!/usr/bin/env python3
"""Integration tests for foundation device taxonomy validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.foundation_device_taxonomy"


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


def _valid_rows() -> list[dict]:
    return [
        {"group": "devices", "instance": "rtr-a", "layer": "L1", "class_ref": "class.router"},
        {"group": "devices", "instance": "srv-a", "layer": "L1", "class_ref": "class.compute.hypervisor"},
        {"group": "firmware", "instance": "fw-a", "layer": "L1", "class_ref": "class.firmware"},
        {"group": "os", "instance": "os-a", "layer": "L1", "class_ref": "class.os"},
        {"group": "physical-links", "instance": "link-a", "layer": "L1", "class_ref": "class.network.physical_link"},
        {"group": "power", "instance": "pdu-a", "layer": "L1", "class_ref": "class.power.pdu"},
    ]


def test_foundation_device_taxonomy_validator_accepts_valid_l1_group_taxonomy():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _valid_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_device_taxonomy_validator_rejects_mismatched_group_class():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[2]["class_ref"] = "class.os"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7851" for diag in result.diagnostics)


def test_foundation_device_taxonomy_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7851" for diag in result.diagnostics)
