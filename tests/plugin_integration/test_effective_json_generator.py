#!/usr/bin/env python3
"""Integration tests for effective JSON generator plugin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.generator.effective_json"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


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
    published = set(ctx.get_published_keys(PLUGIN_ID))
    assert "generated_files" in published
    assert "effective_json_path" in published
    generated_files = ctx.get_published_data()[PLUGIN_ID]["generated_files"]
    assert isinstance(generated_files, list)
    assert str(output_path) in generated_files


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


def test_effective_json_execute_stage_commits_generated_file_payloads(tmp_path):
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": PLUGIN_ID,
                "kind": "generator",
                "entry": f"{(V5_TOOLS / 'plugins/generators/effective_json_generator.py').as_posix()}:EffectiveJsonGenerator",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "run",
                "order": 190,
                "subinterpreter_compatible": True,
                "produces": [
                    {"key": "generated_files", "scope": "pipeline_shared"},
                    {"key": "effective_json_path", "scope": "pipeline_shared"},
                ],
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    output_path = tmp_path / "artifacts" / "effective-topology.json"
    payload_model = {"version": "5.0.0", "model": "class-object-instance", "instances": {"devices": []}}
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=payload_model,
        output_dir=str(output_path.parent),
        compiled_file=str(output_path),
        config={"generation_owner_effective_json": "plugin"},
    )

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.SUCCESS
    assert output_path.exists()
    published = ctx.get_published_data()[PLUGIN_ID]
    assert published["effective_json_path"] == str(output_path)
    assert str(output_path) in published["generated_files"]


def test_effective_json_execute_stage_requires_compiled_json(tmp_path):
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": PLUGIN_ID,
                "kind": "generator",
                "entry": f"{(V5_TOOLS / 'plugins/generators/effective_json_generator.py').as_posix()}:EffectiveJsonGenerator",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "run",
                "order": 190,
                "subinterpreter_compatible": True,
                "produces": [
                    {"key": "generated_files", "scope": "pipeline_shared"},
                    {"key": "effective_json_path", "scope": "pipeline_shared"},
                ],
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    output_path = tmp_path / "artifacts" / "effective-topology.json"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        output_dir=str(output_path.parent),
        compiled_file=str(output_path),
        config={"generation_owner_effective_json": "plugin"},
    )

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E3001" for diag in results[0].diagnostics)
    assert not output_path.exists()
    assert PLUGIN_ID not in ctx.get_published_data()
