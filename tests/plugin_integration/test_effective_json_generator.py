#!/usr/bin/env python3
"""Integration tests for effective JSON generator plugin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.generator.effective_json"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_effective_json_generator_writes_compiled_file(tmp_path):
    registry = _registry()
    output_path = tmp_path / "artifacts" / "effective-topology.json"
    payload = {"version": "5.0.0", "model": "class-object-instance", "instances": {"devices": []}}

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=payload,
        output_dir=str(output_path.parent),
        compiled_file=str(output_path),
        config={"generation_owner_effective_json": "plugin"},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    assert output_path.exists()
    emitted = json.loads(output_path.read_text(encoding="utf-8"))
    assert emitted == payload


def test_effective_json_generator_skips_when_core_owner(tmp_path):
    registry = _registry()
    output_path = tmp_path / "artifacts" / "effective-topology.json"

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={"version": "5.0.0"},
        output_dir=str(output_path.parent),
        compiled_file=str(output_path),
        config={"generation_owner_effective_json": "core"},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    assert not output_path.exists()
