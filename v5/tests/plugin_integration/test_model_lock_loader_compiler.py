#!/usr/bin/env python3
"""Integration tests for model lock loader compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.model_lock_loader"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_model_lock_loader_skips_when_core_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={"classes": {}, "objects": {}},
        config={"compilation_owner_model_lock_data": "core", "model_lock_loaded": True},
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data["model_lock_loaded"] is True


def test_model_lock_loader_plugin_owner_loads_file(tmp_path):
    registry = _registry()
    lock = tmp_path / "model.lock.yaml"
    lock.write_text("classes: {}\nobjects: {}\n", encoding="utf-8")
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_model_lock_data": "plugin", "model_lock_path": str(lock)},
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data["model_lock_loaded"] is True
    assert isinstance(ctx.model_lock, dict)
