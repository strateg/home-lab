#!/usr/bin/env python3
"""Integration tests for single active OS validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.single_active_os"


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


def test_single_active_os_validator_accepts_single_active_os_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os", "status": "active"},
            {"group": "os", "instance": "inst.os.b", "class_ref": "class.os", "status": "mapped"},
            {
                "group": "devices",
                "instance": "rtr-1",
                "class_ref": "class.router",
                "os_refs": ["inst.os.a", "inst.os.b"],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_single_active_os_validator_rejects_multiple_active_os_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os", "status": "active"},
            {"group": "os", "instance": "inst.os.b", "class_ref": "class.os", "status": "ACTIVE"},
            {
                "group": "devices",
                "instance": "rtr-1",
                "class_ref": "class.router",
                "os_refs": ["inst.os.a", "inst.os.b"],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7817" for diag in result.diagnostics)


def test_single_active_os_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7818" for diag in result.diagnostics)
