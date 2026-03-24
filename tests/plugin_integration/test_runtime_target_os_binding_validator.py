#!/usr/bin/env python3
"""Integration tests for runtime target OS binding validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.runtime_target_os_binding"


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


def test_runtime_target_os_binding_validator_accepts_target_with_os_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "os_refs": ["inst.os.a"]},
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service",
                "runtime": {"type": "docker", "target_ref": "srv-a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_runtime_target_os_binding_validator_warns_when_target_has_no_os_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "os_refs": []},
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service",
                "runtime": {"type": "baremetal", "target_ref": "srv-a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7826" for diag in result.diagnostics)


def test_runtime_target_os_binding_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7825" for diag in result.diagnostics)
