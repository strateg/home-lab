#!/usr/bin/env python3
"""Integration tests for assemble/build stage plugins."""

from __future__ import annotations

import json
import sys
import zipfile
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
    assembled_doc = workspace_root / "docs" / "overview.md"
    assert assembled_doc.exists()
    assert assembled_doc.read_text(encoding="utf-8") == "hello\n"
    assembly_payload = json.loads(assembly_manifest.read_text(encoding="utf-8"))
    assembly_files = assembly_payload.get("files", [])
    assert isinstance(assembly_files, list)
    assert any(isinstance(row, dict) and row.get("path") == "docs/overview.md" for row in assembly_files)

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
    with zipfile.ZipFile(bundle_path, "r") as archive:
        assert sorted(archive.namelist()) == ["docs/overview.md"]

    release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
    assert release_manifest["bundle"]["path"] == str(bundle_path)
    assert release_manifest["assembly_manifest_path"] == str(assembly_manifest)


def test_assemble_verify_flags_secret_like_content(tmp_path: Path):
    registry = _registry()
    repo_root = tmp_path
    generated_root = repo_root / "generated" / "home-lab"
    workspace_root = repo_root / ".work" / "native" / "home-lab"

    leaked_file = generated_root / "configs" / "app.env"
    leaked_file.parent.mkdir(parents=True, exist_ok=True)
    leaked_file.write_text("api_key=AKIA1234567890ABCDEF\n", encoding="utf-8")

    artifact_manifest_path = generated_root / "artifact-manifest.json"
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
                        "path": "generated/home-lab/configs/app.env",
                        "sha256": "stub",
                        "size_bytes": leaked_file.stat().st_size,
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
        },
        workspace_root=str(workspace_root),
    )

    ctx._set_execution_context("base.generator.artifact_manifest", set())
    try:
        ctx.publish("artifact_manifest_path", str(artifact_manifest_path))
    finally:
        ctx._clear_execution_context()

    results = registry.execute_stage(Stage.ASSEMBLE, ctx)
    by_id = {result.plugin_id: result for result in results}

    assert by_id["base.assembler.workspace"].status == PluginStatus.SUCCESS
    assert by_id["base.assembler.verify"].status == PluginStatus.FAILED
    assert any(diag.code == "E8103" for diag in by_id["base.assembler.verify"].diagnostics)
    assert by_id["base.assembler.manifest"].status == PluginStatus.SUCCESS
