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
    generated_files = result.output_data["generated_files"]
    assert isinstance(generated_files, list)
    assert str(artifact_path) in generated_files


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_effective_yaml_manifest_depends_on_effective_model() -> None:
    registry = _registry()

    assert registry.specs[PLUGIN_ID].depends_on == ["base.compiler.effective_model"]


def test_effective_yaml_execute_stage_commits_generated_file_payloads(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.effective_model",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/effective_model_compiler.py').as_posix()}:EffectiveModelCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 60,
            },
            {
                "id": PLUGIN_ID,
                "kind": "generator",
                "entry": f"{(V5_TOOLS / 'plugins/generators/effective_yaml_generator.py').as_posix()}:EffectiveYamlGenerator",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "run",
                "order": 200,
                "depends_on": ["base.compiler.effective_model"],
                "config": {"output_filename": "effective-topology.yaml"},
                "produces": [
                    {"key": "generated_files", "scope": "pipeline_shared"},
                    {"key": "effective_yaml_path", "scope": "pipeline_shared"},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    output_dir = tmp_path / "artifacts"
    artifact_path = output_dir / "effective-topology.yaml"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={"version": "5.0.0", "model": "class-object-instance", "instances": {"devices": []}},
        output_dir=str(output_dir),
    )

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.SUCCESS
    assert artifact_path.exists()
    published = ctx.get_published_data()[PLUGIN_ID]
    assert published["effective_yaml_path"] == str(artifact_path)
    assert str(artifact_path) in published["generated_files"]


def test_effective_yaml_execute_stage_requires_compiled_json(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.effective_model",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/effective_model_compiler.py').as_posix()}:EffectiveModelCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 60,
            },
            {
                "id": PLUGIN_ID,
                "kind": "generator",
                "entry": f"{(V5_TOOLS / 'plugins/generators/effective_yaml_generator.py').as_posix()}:EffectiveYamlGenerator",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "run",
                "order": 200,
                "depends_on": ["base.compiler.effective_model"],
                "produces": [
                    {"key": "generated_files", "scope": "pipeline_shared"},
                    {"key": "effective_yaml_path", "scope": "pipeline_shared"},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    artifact_path = tmp_path / "artifacts" / "effective-topology.yaml"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        output_dir=str(artifact_path.parent),
    )

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E3001" for diag in results[0].diagnostics)
    assert not artifact_path.exists()
    assert not ctx.get_published_keys(PLUGIN_ID)
