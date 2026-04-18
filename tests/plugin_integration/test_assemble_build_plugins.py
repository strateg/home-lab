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


def _seed_migrating_contract_publications(ctx: PluginContext, registry: PluginRegistry) -> None:
    """Populate required ADR0093 contract keys for migrating generators."""
    for plugin_id, spec in registry.specs.items():
        if getattr(spec, "kind", None).value != "generator":
            continue
        if getattr(spec, "migration_mode", "legacy") != "migrating":
            continue
        planned_path = f"generated/home-lab/contracts/{plugin_id}.json"
        ctx._published_data[plugin_id] = {  # noqa: SLF001 - test fixture setup
            "artifact_plan": {
                "schema_version": "1.0",
                "plugin_id": plugin_id,
                "artifact_family": f"test.{plugin_id}",
                "planned_outputs": [
                    {
                        "path": planned_path,
                        "renderer": "jinja2",
                        "required": True,
                        "reason": "base-family",
                    }
                ],
                "obsolete_candidates": [],
                "capabilities": [],
                "validation_profiles": [],
            },
            "artifact_generation_report": {
                "schema_version": "1.0",
                "plugin_id": plugin_id,
                "artifact_family": f"test.{plugin_id}",
                "generated": [planned_path],
                "skipped": [],
                "obsolete": [],
                "summary": {
                    "planned_count": 1,
                    "generated_count": 1,
                    "skipped_count": 0,
                    "obsolete_count": 0,
                },
            },
            "artifact_contract_files": [f"/tmp/{plugin_id}.artifact-plan.json"],
            "generated_dir": f"/tmp/generated/{plugin_id.replace('.', '_')}",
        }


def test_assemble_and_build_stage_plugins_produce_release_artifacts(tmp_path: Path):
    registry = _registry()
    release_manifest_spec = registry.specs["base.builder.release_manifest"]
    required_release_inputs = {
        ("base.builder.artifact_family_summary", "artifact_family_summary_path"),
        ("base.builder.generator_readiness_evidence", "generator_readiness_evidence_path"),
        ("base.builder.readiness_reports", "restore_readiness_report_path"),
        ("base.builder.readiness_reports", "rollback_events_report_path"),
        ("base.builder.soho_readiness_package", "operator_readiness_report_path"),
        ("base.builder.soho_readiness_package", "support_bundle_manifest_path"),
    }
    assert {
        (item["from_plugin"], item["key"])
        for item in release_manifest_spec.consumes
        if item.get("required") is True
    } >= required_release_inputs

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
            "plugin_registry": registry,
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
    _seed_migrating_contract_publications(ctx, registry)

    assemble_results = registry.execute_stage(Stage.ASSEMBLE, ctx)
    assert [r.plugin_id for r in assemble_results] == [
        "base.assembler.changed_scopes",
        "base.assembler.workspace",
        "base.assembler.artifact_contract_guard",
        "base.assembler.verify",
        "base.assembler.manifest",
        "base.assembler.deploy_bundle",
    ]
    assert all(result.status == PluginStatus.SUCCESS for result in assemble_results)
    assert isinstance(ctx.changed_input_scopes, list)
    assert "docs" in ctx.changed_input_scopes

    assembly_manifest = workspace_root / "assembly-manifest.json"
    assert assembly_manifest.exists()
    assembled_doc = workspace_root / "docs" / "overview.md"
    assert assembled_doc.exists()
    assert assembled_doc.read_text(encoding="utf-8") == "hello\n"
    assembly_payload = json.loads(assembly_manifest.read_text(encoding="utf-8"))
    assembly_files = assembly_payload.get("files", [])
    assert isinstance(assembly_files, list)
    assert any(isinstance(row, dict) and row.get("path") == "docs/overview.md" for row in assembly_files)
    deploy_bundle_result = next(
        result for result in assemble_results if result.plugin_id == "base.assembler.deploy_bundle"
    )
    deploy_bundle_id = str(deploy_bundle_result.output_data.get("deploy_bundle_id", ""))
    deploy_bundle_path = Path(str(deploy_bundle_result.output_data.get("deploy_bundle_path", "")))
    assert deploy_bundle_id.startswith("b-")
    assert deploy_bundle_path.exists()
    assert (deploy_bundle_path / "manifest.yaml").exists()
    assert (deploy_bundle_path / "metadata.yaml").exists()

    build_results = registry.execute_stage(Stage.BUILD, ctx)
    assert [r.plugin_id for r in build_results] == [
        "base.builder.bundle",
        "base.builder.sbom",
        "base.builder.artifact_family_summary",
        "base.builder.generator_readiness_evidence",
        "base.builder.readiness_reports",
        "base.builder.soho_readiness_package",
        "base.builder.release_manifest",
    ]
    assert all(result.status == PluginStatus.SUCCESS for result in build_results)

    bundle_path = dist_root / "home-lab-snapshot.zip"
    sbom_path = sbom_root / "sbom.json"
    artifact_family_summary_path = dist_root / "artifact-family-summary.json"
    generator_readiness_evidence_path = dist_root / "generator-readiness-evidence.json"
    restore_readiness_report_path = dist_root / "reports" / "restore-readiness.json"
    rollback_events_report_path = dist_root / "reports" / "rollback-events.json"
    operator_readiness_report_path = generated_root / "product" / "reports" / "operator-readiness.json"
    support_bundle_manifest_path = generated_root / "product" / "reports" / "support-bundle-manifest.json"
    release_manifest_path = dist_root / "release-manifest.json"
    assert bundle_path.exists()
    assert sbom_path.exists()
    assert artifact_family_summary_path.exists()
    assert generator_readiness_evidence_path.exists()
    assert restore_readiness_report_path.exists()
    assert rollback_events_report_path.exists()
    assert operator_readiness_report_path.exists()
    assert support_bundle_manifest_path.exists()
    assert release_manifest_path.exists()
    with zipfile.ZipFile(bundle_path, "r") as archive:
        assert sorted(archive.namelist()) == ["docs/overview.md"]

    release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
    artifact_family_summary = json.loads(artifact_family_summary_path.read_text(encoding="utf-8"))
    generator_readiness = json.loads(generator_readiness_evidence_path.read_text(encoding="utf-8"))
    restore_readiness = json.loads(restore_readiness_report_path.read_text(encoding="utf-8"))
    rollback_events = json.loads(rollback_events_report_path.read_text(encoding="utf-8"))
    assert release_manifest["bundle"]["path"] == str(bundle_path)
    assert release_manifest["assembly_manifest_path"] == str(assembly_manifest)
    assert release_manifest["artifact_family_summary_path"] == str(artifact_family_summary_path)
    assert release_manifest["generator_readiness_evidence_path"] == str(generator_readiness_evidence_path)
    assert release_manifest["restore_readiness_report_path"] == str(restore_readiness_report_path)
    assert release_manifest["rollback_events_report_path"] == str(rollback_events_report_path)
    assert release_manifest["operator_readiness_report_path"] == str(operator_readiness_report_path)
    assert release_manifest["support_bundle_manifest_path"] == str(support_bundle_manifest_path)
    assert artifact_family_summary["totals"]["plugins"] >= 1
    assert generator_readiness["readiness"]["status"] in {"green", "warning", "blocked"}
    assert "sunset_phase_breakdown" in generator_readiness
    assert "sunset_legacy_target_states" in generator_readiness
    assert restore_readiness["profile"] == "adr0091.restore-readiness.v1"
    assert "sunset_phase_breakdown" in restore_readiness["source_evidence"]
    assert "sunset_legacy_target_states" in restore_readiness["source_evidence"]
    assert rollback_events["profile"] == "adr0093.rollback-events.v1"


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
            "plugin_registry": registry,
        },
        workspace_root=str(workspace_root),
    )

    ctx._set_execution_context("base.generator.artifact_manifest", set())
    try:
        ctx.publish("artifact_manifest_path", str(artifact_manifest_path))
    finally:
        ctx._clear_execution_context()
    _seed_migrating_contract_publications(ctx, registry)

    results = registry.execute_stage(Stage.ASSEMBLE, ctx)
    by_id = {result.plugin_id: result for result in results}

    assert by_id["base.assembler.workspace"].status == PluginStatus.SUCCESS
    assert by_id["base.assembler.verify"].status == PluginStatus.FAILED
    assert any(diag.code == "E8103" for diag in by_id["base.assembler.verify"].diagnostics)
    assert by_id["base.assembler.manifest"].status == PluginStatus.SUCCESS
    assert by_id["base.assembler.changed_scopes"].status == PluginStatus.SUCCESS
    assert by_id["base.assembler.deploy_bundle"].status == PluginStatus.SKIPPED


def test_changed_input_scopes_are_empty_on_second_identical_run(tmp_path: Path):
    registry = _registry()
    repo_root = tmp_path
    generated_root = repo_root / "generated" / "home-lab"
    workspace_root = repo_root / ".work" / "native" / "home-lab"

    source_file = generated_root / "docs" / "overview.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("hello\n", encoding="utf-8")

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
                        "path": "generated/home-lab/docs/overview.md",
                        "sha256": "stable-sha",
                        "size_bytes": source_file.stat().st_size,
                    }
                ],
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    first_ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "repo_root": str(repo_root),
            "project_id": "home-lab",
            "workspace_root": str(workspace_root),
            "plugin_registry": registry,
        },
        workspace_root=str(workspace_root),
    )
    first_ctx._set_execution_context("base.generator.artifact_manifest", set())
    try:
        first_ctx.publish("artifact_manifest_path", str(artifact_manifest_path))
    finally:
        first_ctx._clear_execution_context()
    _seed_migrating_contract_publications(first_ctx, registry)
    first_results = registry.execute_stage(Stage.ASSEMBLE, first_ctx)
    assert all(result.status == PluginStatus.SUCCESS for result in first_results)
    assert isinstance(first_ctx.changed_input_scopes, list)
    assert "docs" in first_ctx.changed_input_scopes

    second_ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "repo_root": str(repo_root),
            "project_id": "home-lab",
            "workspace_root": str(workspace_root),
            "plugin_registry": registry,
        },
        workspace_root=str(workspace_root),
    )
    second_ctx._set_execution_context("base.generator.artifact_manifest", set())
    try:
        second_ctx.publish("artifact_manifest_path", str(artifact_manifest_path))
    finally:
        second_ctx._clear_execution_context()
    _seed_migrating_contract_publications(second_ctx, registry)
    second_results = registry.execute_stage(Stage.ASSEMBLE, second_ctx)
    assert all(result.status == PluginStatus.SUCCESS for result in second_results)
    assert second_ctx.changed_input_scopes == []
    first_bundle_result = next(result for result in first_results if result.plugin_id == "base.assembler.deploy_bundle")
    second_bundle_result = next(
        result for result in second_results if result.plugin_id == "base.assembler.deploy_bundle"
    )
    assert first_bundle_result.output_data.get("deploy_bundle_reused") is False
    assert second_bundle_result.output_data.get("deploy_bundle_reused") is True
    assert first_bundle_result.output_data.get("deploy_bundle_id") == second_bundle_result.output_data.get(
        "deploy_bundle_id"
    )


def test_assembly_manifest_requires_committed_artifact_manifest_path(tmp_path: Path) -> None:
    registry = _registry()
    spec = registry.specs["base.assembler.manifest"]
    consume = next(
        item
        for item in spec.consumes
        if item["from_plugin"] == "base.generator.artifact_manifest" and item["key"] == "artifact_manifest_path"
    )
    assert consume["required"] is True

    workspace_root = tmp_path / ".work" / "native" / "home-lab"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "repo_root": str(tmp_path),
            "project_id": "home-lab",
            "workspace_root": str(workspace_root),
            "plugin_registry": registry,
        },
        workspace_root=str(workspace_root),
    )

    ctx._set_execution_context("base.assembler.workspace", set())
    try:
        ctx.publish("assembled_files", [])
    finally:
        ctx._clear_execution_context()

    result = registry.execute_plugin("base.assembler.manifest", ctx, Stage.ASSEMBLE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_deploy_bundle_requires_committed_assembly_manifest_path(tmp_path: Path) -> None:
    registry = _registry()
    spec = registry.specs["base.assembler.deploy_bundle"]
    consume = next(
        item
        for item in spec.consumes
        if item["from_plugin"] == "base.assembler.manifest" and item["key"] == "assembly_manifest_path"
    )
    assert consume["required"] is True

    workspace_root = tmp_path / ".work" / "native" / "home-lab"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "repo_root": str(tmp_path),
            "project_id": "home-lab",
            "workspace_root": str(workspace_root),
            "plugin_registry": registry,
        },
        workspace_root=str(workspace_root),
    )

    ctx._set_execution_context("base.assembler.verify", set())
    try:
        ctx.publish("assemble_verified", True)
    finally:
        ctx._clear_execution_context()

    result = registry.execute_plugin("base.assembler.deploy_bundle", ctx, Stage.ASSEMBLE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_release_manifest_requires_committed_build_artifacts(tmp_path: Path) -> None:
    registry = _registry()
    workspace_root = tmp_path / ".work" / "native" / "home-lab"
    dist_root = tmp_path / "dist" / "home-lab"
    dist_root.mkdir(parents=True, exist_ok=True)

    bundle_path = dist_root / "home-lab-snapshot.zip"
    bundle_path.write_bytes(b"bundle")
    sbom_path = dist_root / "sbom.json"
    sbom_path.write_text("{}", encoding="utf-8")
    assembly_manifest_path = workspace_root / "assembly-manifest.json"
    assembly_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    assembly_manifest_path.write_text("{}", encoding="utf-8")

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "repo_root": str(tmp_path),
            "project_id": "home-lab",
            "workspace_root": str(workspace_root),
            "dist_root": str(dist_root),
            "plugin_registry": registry,
        },
        workspace_root=str(workspace_root),
        dist_root=str(dist_root),
        release_tag="snapshot",
        signing_backend="none",
    )

    for plugin_id, payload in {
        "base.builder.bundle": {
            "release_bundle_path": str(bundle_path),
            "release_bundle_sha256": "stub",
        },
        "base.builder.sbom": {"sbom_path": str(sbom_path)},
        "base.assembler.manifest": {"assembly_manifest_path": str(assembly_manifest_path)},
        "base.builder.generator_readiness_evidence": {
            "generator_readiness_evidence_path": str(dist_root / "generator-readiness-evidence.json")
        },
        "base.builder.readiness_reports": {
            "restore_readiness_report_path": str(dist_root / "reports" / "restore-readiness.json"),
            "rollback_events_report_path": str(dist_root / "reports" / "rollback-events.json"),
        },
        "base.builder.soho_readiness_package": {
            "operator_readiness_report_path": str(tmp_path / "generated" / "home-lab" / "product" / "reports" / "operator-readiness.json"),
            "support_bundle_manifest_path": str(tmp_path / "generated" / "home-lab" / "product" / "reports" / "support-bundle-manifest.json"),
        },
    }.items():
        ctx._set_execution_context(plugin_id, set())
        try:
            for key, value in payload.items():
                ctx.publish(key, value)
        finally:
            ctx._clear_execution_context()

    result = registry.execute_plugin("base.builder.release_manifest", ctx, Stage.BUILD)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)
