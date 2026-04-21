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

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test


def _publish(ctx: PluginContext, plugin_id: str, payload: dict) -> None:
    for key, value in payload.items():
        publish_for_test(ctx, plugin_id, key, value)


def _run_builder(builder: ReadinessReportsBuilder, ctx: PluginContext):
    return run_plugin_for_test(
        builder,
        ctx,
        Stage.BUILD,
        consumes_keys={"base.builder.generator_readiness_evidence"},
    )


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
        "generator_sunset_summary": {
            "warnings": 0,
            "errors": 0,
            "pre_sunset_legacy_targets": 0,
            "grace_window_legacy_targets": 0,
        },
        "sunset_phase_breakdown": {
            "pre_sunset_legacy_targets": 0,
            "grace_window_legacy_targets": 0,
            "hard_error_legacy_targets": 0,
        },
        "sunset_legacy_target_states": [],
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
    _publish(
        ctx,
        "base.builder.generator_readiness_evidence",
        {"generator_readiness_evidence": _readiness_evidence(status="green")},
    )

    builder = ReadinessReportsBuilder("base.builder.readiness_reports")
    result = _run_builder(builder, ctx)

    assert result.status == PluginStatus.SUCCESS
    report_path = Path(result.output_data["restore_readiness_report_path"])
    rollback_events_path = Path(result.output_data["rollback_events_report_path"])
    assert report_path.exists()
    assert rollback_events_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    rollback_payload = json.loads(rollback_events_path.read_text(encoding="utf-8"))
    assert payload["profile"] == "adr0091.restore-readiness.v1"
    assert payload["status"] == "green"
    sunset_check = next((check for check in payload["checks"] if check["check_id"] == "sunset-enforcement"), None)
    hard_error_phase_check = next(
        (check for check in payload["checks"] if check["check_id"] == "sunset-hard-error-phase"),
        None,
    )
    assert sunset_check is not None
    assert hard_error_phase_check is not None
    assert sunset_check["details"]["pre_sunset_legacy_targets"] == 0
    assert sunset_check["details"]["grace_window_legacy_targets"] == 0
    assert hard_error_phase_check["details"]["hard_error_legacy_targets"] == 0
    assert hard_error_phase_check["status"] == "pass"
    assert payload["source_evidence"]["sunset_phase_breakdown"]["hard_error_legacy_targets"] == 0
    assert payload["source_evidence"]["sunset_legacy_target_states"] == []
    assert rollback_payload["profile"] == "adr0093.rollback-events.v1"


def test_readiness_reports_builder_blocks_sunset_hard_error_phase_check(tmp_path: Path) -> None:
    dist_root = tmp_path / "dist"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={"project_id": "home-lab"},
        dist_root=str(dist_root),
    )
    evidence = _readiness_evidence(status="blocked")
    evidence["sunset_phase_breakdown"] = {
        "pre_sunset_legacy_targets": 0,
        "grace_window_legacy_targets": 0,
        "hard_error_legacy_targets": 2,
    }
    _publish(ctx, "base.builder.generator_readiness_evidence", {"generator_readiness_evidence": evidence})

    builder = ReadinessReportsBuilder("base.builder.readiness_reports")
    result = _run_builder(builder, ctx)

    assert result.status == PluginStatus.SUCCESS
    report_path = Path(result.output_data["restore_readiness_report_path"])
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    hard_error_phase_check = next(
        (check for check in payload["checks"] if check["check_id"] == "sunset-hard-error-phase"),
        None,
    )
    assert hard_error_phase_check is not None
    assert hard_error_phase_check["status"] == "blocked"
    assert hard_error_phase_check["details"]["hard_error_legacy_targets"] == 2


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

    result = _run_builder(builder, ctx)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8206" for diag in result.diagnostics)
