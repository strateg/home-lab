#!/usr/bin/env python3
"""Integration tests for artifact manifest generator plugin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Phase, PluginInputSnapshot, Stage, SubscriptionValue
from kernel.plugin_runner import run_plugin_once
from plugins.generators.artifact_manifest_generator import ArtifactManifestGenerator
from tests.helpers.plugin_execution import publish_for_test

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

    publish_for_test(ctx, "base.generator.docs", "generated_files", [str(docs_path)])
    publish_for_test(ctx, "base.generator.ansible_inventory", "generated_files", [str(inv_path)])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE, phase=Phase.FINALIZE)

    assert result.status == PluginStatus.SUCCESS
    manifest_path = project_root / "artifact-manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["artifact_count"] == 2
    assert [row["path"] for row in payload["artifacts"]] == sorted([row["path"] for row in payload["artifacts"]])
    assert result.output_data["artifact_manifest_path"] == str(manifest_path)
    assert result.output_data["compatibility_fallback_used"] == 0


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
            publish_for_test(ctx, plugin_id, "generated_files", [plugin_to_file[plugin_id]])
        result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE, phase=Phase.FINALIZE)
        assert result.status == PluginStatus.SUCCESS
        manifest_path = project_root / "artifact-manifest.json"
        assert manifest_path.exists()
        return manifest_path.read_text(encoding="utf-8")

    first = _run_with_order("base.generator.docs", "base.generator.ansible_inventory")
    second = _run_with_order("base.generator.ansible_inventory", "base.generator.docs")
    assert first == second


def test_artifact_manifest_generator_snapshot_path_skips_compatibility_only_producers(tmp_path: Path):
    artifacts_root = tmp_path / "generated"
    project_root = artifacts_root / "home-lab"

    docs_path = project_root / "docs" / "overview.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text("doc-content\n", encoding="utf-8")

    terraform_path = project_root / "terraform" / "proxmox" / "provider.tf"
    terraform_path.parent.mkdir(parents=True, exist_ok=True)
    terraform_path.write_text("# generated\n", encoding="utf-8")

    snapshot = PluginInputSnapshot(
        plugin_id=PLUGIN_ID,
        stage=Stage.GENERATE,
        phase=Phase.FINALIZE,
        topology_path="topology/topology.yaml",
        profile="test",
        config={
            "repo_root": str(tmp_path),
            "project_id": "home-lab",
            "generator_artifacts_root": str(artifacts_root),
            "compile_generated_at": "2026-03-26T00:00:00+00:00",
            "artifact_manifest_producers": ["base.generator.docs"],
            "artifact_manifest_compatibility_producers": ["object.proxmox.generator.terraform"],
        },
        subscriptions={
            ("base.generator.docs", "generated_files"): SubscriptionValue(
                from_plugin="base.generator.docs",
                key="generated_files",
                value=[str(docs_path)],
            )
        },
        allowed_dependencies=frozenset({"base.generator.docs"}),
        produced_key_scopes={
            "generated_files": "pipeline_shared",
            "artifact_manifest_path": "pipeline_shared",
            "artifact_manifest": "pipeline_shared",
        },
    )

    envelope = run_plugin_once(snapshot=snapshot, plugin=ArtifactManifestGenerator(PLUGIN_ID))

    assert envelope.result.status == PluginStatus.SUCCESS
    payload = json.loads((project_root / "artifact-manifest.json").read_text(encoding="utf-8"))
    assert [row["producer_plugin"] for row in payload["artifacts"]] == ["base.generator.docs"]
    assert any(diag.code == "I3902" for diag in envelope.result.diagnostics)


def test_artifact_manifest_generator_respects_explicit_producer_list(tmp_path: Path):
    registry = _registry()
    artifacts_root = tmp_path / "generated"
    project_root = artifacts_root / "home-lab"

    included_path = project_root / "terraform" / "proxmox" / "provider.tf"
    included_path.parent.mkdir(parents=True, exist_ok=True)
    included_path.write_text("# generated\n", encoding="utf-8")

    ignored_path = project_root / "docs" / "overview.md"
    ignored_path.parent.mkdir(parents=True, exist_ok=True)
    ignored_path.write_text("doc-content\n", encoding="utf-8")

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "repo_root": str(tmp_path),
            "project_id": "home-lab",
            "generator_artifacts_root": str(artifacts_root),
            "artifact_manifest_producers": ["object.proxmox.generator.terraform"],
        },
    )

    for plugin_id, artifact_path in (
        ("object.proxmox.generator.terraform", included_path),
        ("base.generator.docs", ignored_path),
    ):
        publish_for_test(ctx, plugin_id, "generated_files", [str(artifact_path)])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE, phase=Phase.FINALIZE)

    assert result.status == PluginStatus.SUCCESS
    payload = json.loads((project_root / "artifact-manifest.json").read_text(encoding="utf-8"))
    assert [row["producer_plugin"] for row in payload["artifacts"]] == ["object.proxmox.generator.terraform"]
    assert result.output_data["compatibility_fallback_used"] == 1
    assert any(diag.code == "I3903" for diag in result.diagnostics)
