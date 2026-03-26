#!/usr/bin/env python3
"""Integration tests for artifact manifest generator plugin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Phase, Stage

PLUGIN_ID = "base.generator.artifact_manifest"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_artifact_manifest_generator_emits_checksums(tmp_path: Path):
    registry = _registry()
    artifacts_root = tmp_path / "generated"
    project_root = artifacts_root / "home-lab"

    docs_path = project_root / "docs" / "overview.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text("doc-content\n", encoding="utf-8")

    inv_path = project_root / "ansible" / "inventory" / "production" / "hosts.yml"
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text("all:\n  hosts: {}\n", encoding="utf-8")

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "repo_root": str(tmp_path),
            "project_id": "home-lab",
            "generator_artifacts_root": str(artifacts_root),
            "compile_generated_at": "2026-03-26T00:00:00+00:00",
        },
    )

    ctx._set_execution_context("base.generator.docs", set())
    try:
        ctx.publish("generated_files", [str(docs_path)])
    finally:
        ctx._clear_execution_context()
    ctx._set_execution_context("base.generator.ansible_inventory", set())
    try:
        ctx.publish("generated_files", [str(inv_path)])
    finally:
        ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE, phase=Phase.FINALIZE)

    assert result.status == PluginStatus.SUCCESS
    manifest_path = project_root / "artifact-manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["artifact_count"] == 2
    assert [row["path"] for row in payload["artifacts"]] == sorted([row["path"] for row in payload["artifacts"]])
    produced = ctx.get_published_data()[PLUGIN_ID]
    assert produced["artifact_manifest_path"] == str(manifest_path)


def test_artifact_manifest_generator_is_deterministic_across_publish_order(tmp_path: Path):
    registry = _registry()
    artifacts_root = tmp_path / "generated"
    project_root = artifacts_root / "home-lab"

    docs_path = project_root / "docs" / "overview.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text("doc-content\n", encoding="utf-8")

    inv_path = project_root / "ansible" / "inventory" / "production" / "hosts.yml"
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text("all:\n  hosts: {}\n", encoding="utf-8")

    def _run_with_order(first_plugin: str, second_plugin: str) -> str:
        ctx = PluginContext(
            topology_path="topology/topology.yaml",
            profile="test",
            model_lock={},
            config={
                "repo_root": str(tmp_path),
                "project_id": "home-lab",
                "generator_artifacts_root": str(artifacts_root),
                "compile_generated_at": "2026-03-26T00:00:00+00:00",
            },
        )
        plugin_to_file = {
            "base.generator.docs": str(docs_path),
            "base.generator.ansible_inventory": str(inv_path),
        }
        for plugin_id in (first_plugin, second_plugin):
            ctx._set_execution_context(plugin_id, set())
            try:
                ctx.publish("generated_files", [plugin_to_file[plugin_id]])
            finally:
                ctx._clear_execution_context()
        result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE, phase=Phase.FINALIZE)
        assert result.status == PluginStatus.SUCCESS
        manifest_path = project_root / "artifact-manifest.json"
        assert manifest_path.exists()
        return manifest_path.read_text(encoding="utf-8")

    first = _run_with_order("base.generator.docs", "base.generator.ansible_inventory")
    second = _run_with_order("base.generator.ansible_inventory", "base.generator.docs")
    assert first == second
