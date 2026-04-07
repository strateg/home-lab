#!/usr/bin/env python3
"""Integration checks for ADR0091 readiness reports builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.builders.release_builder import ReadinessReportsBuilder


def _readiness_evidence(*, status: str = "green") -> dict[str, object]:
    return {
        "schema_version": 1,
        "project_id": "home-lab",
        "generated_at": "2026-04-07T12:00:00+00:00",
        "readiness": {
            "status": status,
            "blocking_reasons": [],
            "warning_reasons": [],
        },
        "generator_migration_summary": {"legacy": 0, "migrating": 3, "migrated": 0, "rollback": 0},
        "generator_sunset_summary": {"warnings": 0, "errors": 0},
        "generator_rollback_summary": {"escalated": 0, "missing_started_at": 0},
        "artifact_family_summary_totals": {"plugins": 3},
    }


def test_readiness_reports_builder_emits_restore_readiness_report(tmp_path: Path) -> None:
    dist_root = tmp_path / "dist"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={"project_id": "home-lab"},
        dist_root=str(dist_root),
    )
    ctx._set_execution_context("base.builder.generator_readiness_evidence", set())  # noqa: SLF001 - test fixture setup
    try:
        ctx.publish("generator_readiness_evidence", _readiness_evidence(status="green"))
    finally:
        ctx._clear_execution_context()

    builder = ReadinessReportsBuilder("base.builder.readiness_reports")
    result = builder.execute(ctx, Stage.BUILD)

    assert result.status == PluginStatus.SUCCESS
    report_path = Path(result.output_data["restore_readiness_report_path"])
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["profile"] == "adr0091.restore-readiness.v1"
    assert payload["status"] == "green"
    assert any(check["check_id"] == "sunset-enforcement" for check in payload["checks"])


def test_readiness_reports_builder_fails_without_input_evidence(tmp_path: Path) -> None:
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={"project_id": "home-lab"},
        dist_root=str(tmp_path / "dist"),
    )
    builder = ReadinessReportsBuilder("base.builder.readiness_reports")

    result = builder.execute(ctx, Stage.BUILD)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8206" for diag in result.diagnostics)
