#!/usr/bin/env python3
"""Integration tests for assemble/build stage plugins."""

from __future__ import annotations

import json
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_assemble_and_build_stage_plugins_produce_release_artifacts(tmp_path: Path):
    registry = _registry()
    repo_root = tmp_path
    generated_root = repo_root / "generated" / "home-lab"
    workspace_root = repo_root / ".work" / "native" / "home-lab"
    dist_root = repo_root / "dist" / "home-lab"
    sbom_root = dist_root / "sbom"

    source_file = generated_root / "docs" / "overview.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("hello\n", encoding="utf-8")

    artifact_manifest_path = generated_root / "artifact-manifest.json"
    artifact_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": "home-lab",
                "generated_at": "2026-03-26T00:00:00+00:00",
                "artifact_count": 1,
                "artifacts": [
                    {
                        "producer_plugin": "base.generator.docs",
                        "path": "generated/home-lab/docs/overview.md",
                        "sha256": "stub",
                        "size_bytes": 6,
                    }
                ],
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "repo_root": str(repo_root),
            "project_id": "home-lab",
            "workspace_root": str(workspace_root),
            "dist_root": str(dist_root),
        },
        workspace_root=str(workspace_root),
        dist_root=str(dist_root),
        release_tag="snapshot",
        signing_backend="none",
        sbom_output_dir=str(sbom_root),
    )

    ctx._set_execution_context("base.generator.artifact_manifest", set())
    try:
        ctx.publish("artifact_manifest_path", str(artifact_manifest_path))
    finally:
        ctx._clear_execution_context()

    assemble_results = registry.execute_stage(Stage.ASSEMBLE, ctx)
    assert [r.plugin_id for r in assemble_results] == [
        "base.assembler.workspace",
        "base.assembler.verify",
        "base.assembler.manifest",
    ]
    assert all(result.status == PluginStatus.SUCCESS for result in assemble_results)

    assembly_manifest = workspace_root / "assembly-manifest.json"
    assert assembly_manifest.exists()

    build_results = registry.execute_stage(Stage.BUILD, ctx)
    assert [r.plugin_id for r in build_results] == [
        "base.builder.bundle",
        "base.builder.sbom",
        "base.builder.release_manifest",
    ]
    assert all(result.status == PluginStatus.SUCCESS for result in build_results)

    bundle_path = dist_root / "home-lab-snapshot.zip"
    sbom_path = sbom_root / "sbom.json"
    release_manifest_path = dist_root / "release-manifest.json"
    assert bundle_path.exists()
    assert sbom_path.exists()
    assert release_manifest_path.exists()
