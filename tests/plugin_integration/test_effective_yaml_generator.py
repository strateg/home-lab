#!/usr/bin/env python3
"""Integration tests for effective YAML generator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.generator.effective_yaml"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_effective_yaml_generator_writes_file(tmp_path):
    registry = _registry()
    output_dir = tmp_path / "artifacts"

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={
            "version": "5.0.0",
            "model": "class-object-instance",
            "instances": {"devices": []},
        },
        output_dir=str(output_dir),
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    assert not result.has_errors
    artifact_path = output_dir / "effective-topology.yaml"
    assert artifact_path.exists()
    parsed = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))
    assert parsed["model"] == "class-object-instance"
    published = set(ctx.get_published_keys(PLUGIN_ID))
    assert "generated_files" in published
    assert "effective_yaml_path" in published
    generated_files = ctx.get_published_data()[PLUGIN_ID]["generated_files"]
    assert isinstance(generated_files, list)
    assert str(artifact_path) in generated_files
