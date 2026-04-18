#!/usr/bin/env python3
"""Integration checks for ADR0091 SOHO readiness package builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.builders.soho_readiness_builder import SohoReadinessBuilder

_ADR0091_DOMAINS = {
    "greenfield-first-install",
    "brownfield-adoption",
    "router-replacement",
    "secret-rotation",
    "scheduled-update",
    "failed-update-rollback",
    "backup-and-restore",
    "operator-handover",
}


def _publish(ctx: PluginContext, plugin_id: str, payload: dict) -> None:
    ctx._set_execution_context(plugin_id, set())  # noqa: SLF001 - test fixture setup
    try:
        for key, value in payload.items():
            ctx.publish(key, value)
    finally:
        ctx._clear_execution_context()


def _run_builder(builder: SohoReadinessBuilder, ctx: PluginContext):
    ctx._set_execution_context("base.builder.soho_readiness_package", set())  # noqa: SLF001 - direct plugin execution helper
    try:
        return builder.execute(ctx, Stage.BUILD)
    finally:
        ctx._clear_execution_context()  # noqa: SLF001 - direct plugin execution helper


def test_soho_readiness_builder_emits_product_package_and_reports(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    generated_root = tmp_path / "generated"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "repo_root": str(repo_root),
            "project_id": "home-lab",
            "generator_artifacts_root": str(generated_root),
        },
    )

    _publish(
        ctx,
        "base.validator.soho_product_profile",
        {
            "product_profile_state": {
                "profile_id": "soho.standard.v1",
                "deployment_class": "managed-soho",
                "status": "green",
            }
        },
    )
    _publish(
        ctx,
        "base.builder.readiness_reports",
        {
            "restore_readiness_report": {
                "status": "green",
                "checks": [],
            }
        },
    )

    builder = SohoReadinessBuilder("base.builder.soho_readiness_package")
    result = _run_builder(builder, ctx)

    assert result.status == PluginStatus.SUCCESS
    reports_dir = generated_root / "home-lab" / "product" / "reports"
    handover_dir = generated_root / "home-lab" / "product" / "handover"
    assert reports_dir.exists()
    assert handover_dir.exists()

    operator_path = reports_dir / "operator-readiness.json"
    manifest_path = reports_dir / "support-bundle-manifest.json"
    assert operator_path.exists()
    assert manifest_path.exists()

    operator_payload = json.loads(operator_path.read_text(encoding="utf-8"))
    assert operator_payload["status"] == "green"
    assert _ADR0091_DOMAINS.issubset(set(operator_payload["evidence"].keys()))

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["artifacts"]["reports"]["support-bundle-manifest.json"]["present"] is True


def test_soho_readiness_builder_blocks_when_restore_evidence_missing(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    generated_root = tmp_path / "generated"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "repo_root": str(repo_root),
            "project_id": "home-lab",
            "generator_artifacts_root": str(generated_root),
        },
    )

    builder = SohoReadinessBuilder("base.builder.soho_readiness_package")
    result = _run_builder(builder, ctx)

    assert result.status == PluginStatus.FAILED
    codes = {diag.code for diag in result.diagnostics}
    assert "E7943" in codes
    assert "E7944" in codes


def test_soho_readiness_builder_handover_templates_are_sanitized(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    generated_root = tmp_path / "generated"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "repo_root": str(repo_root),
            "project_id": "home-lab",
            "generator_artifacts_root": str(generated_root),
        },
    )
    _publish(
        ctx,
        "base.builder.readiness_reports",
        {
            "restore_readiness_report": {
                "status": "green",
                "checks": [],
            }
        },
    )

    builder = SohoReadinessBuilder("base.builder.soho_readiness_package")
    result = _run_builder(builder, ctx)

    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    handover_dir = generated_root / "home-lab" / "product" / "handover"
    assert handover_dir.exists()

    forbidden_tokens = ("BEGIN PRIVATE KEY", "$ANSIBLE_VAULT", "age1", "sops")
    for path in handover_dir.glob("*"):
        content = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in content
