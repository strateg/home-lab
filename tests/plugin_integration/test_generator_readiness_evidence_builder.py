#!/usr/bin/env python3
"""Integration checks for ADR0093 generator readiness evidence builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.builders.release_builder import GeneratorReadinessEvidenceBuilder


def _publish(ctx: PluginContext, plugin_id: str, payload: dict) -> None:
    ctx._set_execution_context(plugin_id, set())  # noqa: SLF001 - test fixture setup
    try:
        for key, value in payload.items():
            ctx.publish(key, value)
    finally:
        ctx._clear_execution_context()


def _run_builder(builder: GeneratorReadinessEvidenceBuilder, ctx: PluginContext):
    ctx._set_execution_context(  # noqa: SLF001 - direct plugin execution helper
        builder.plugin_id,
        {
            "base.validator.generator_migration_status",
            "base.validator.generator_sunset",
            "base.validator.generator_rollback_escalation",
            "base.builder.artifact_family_summary",
        },
    )
    try:
        return builder.execute(ctx, Stage.BUILD)
    finally:
        ctx._clear_execution_context()  # noqa: SLF001 - direct plugin execution helper


def test_generator_readiness_evidence_builder_emits_green_when_no_signals(tmp_path: Path) -> None:
    dist_root = tmp_path / "dist"
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={"project_id": "home-lab"},
        dist_root=str(dist_root),
    )
    builder = GeneratorReadinessEvidenceBuilder("base.builder.generator_readiness_evidence")

    result = _run_builder(builder, ctx)

    assert result.status == PluginStatus.SUCCESS
    output_path = Path(result.output_data["generator_readiness_evidence_path"])
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["status"] == "green"
    assert payload["sunset_phase_breakdown"]["pre_sunset_legacy_targets"] == 0
    assert payload["sunset_phase_breakdown"]["grace_window_legacy_targets"] == 0
    assert payload["sunset_phase_breakdown"]["hard_error_legacy_targets"] == 0
    assert payload["sunset_legacy_target_states"] == []


def test_generator_readiness_evidence_builder_emits_blocked_on_sunset_error(tmp_path: Path) -> None:
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
        "base.validator.generator_migration_status",
        {"generator_migration_summary": {"legacy": 1, "migrating": 0, "migrated": 0, "rollback": 0}},
    )
    _publish(
        ctx,
        "base.validator.generator_sunset",
        {
            "generator_sunset_summary": {
                "warnings": 1,
                "errors": 1,
                "legacy_targets": 1,
                "pre_sunset_legacy_targets": 0,
                "grace_window_legacy_targets": 0,
                "legacy_target_states": [
                    {"plugin_id": "z.generator", "sunset_phase": "grace_window"},
                    {"plugin_id": "a.generator", "sunset_phase": "hard_error"},
                ],
            }
        },
    )
    _publish(
        ctx,
        "base.validator.generator_rollback_escalation",
        {"generator_rollback_summary": {"warnings": 0, "escalated": 0, "missing_started_at": 0}},
    )
    _publish(ctx, "base.builder.artifact_family_summary", {"artifact_family_summary": {"totals": {"plugins": 3}}})
    builder = GeneratorReadinessEvidenceBuilder("base.builder.generator_readiness_evidence")

    result = _run_builder(builder, ctx)

    assert result.status == PluginStatus.SUCCESS
    output_path = Path(result.output_data["generator_readiness_evidence_path"])
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["status"] == "blocked"
    assert payload["sunset_phase_breakdown"]["hard_error_legacy_targets"] == 1
    assert payload["sunset_legacy_target_states"] == [
        {"plugin_id": "a.generator", "sunset_phase": "hard_error"},
        {"plugin_id": "z.generator", "sunset_phase": "grace_window"},
    ]
    assert payload["artifact_family_summary_totals"]["plugins"] == 3


def test_generator_readiness_evidence_builder_derives_phase_counts_from_states(tmp_path: Path) -> None:
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
        "base.validator.generator_sunset",
        {
            "generator_sunset_summary": {
                "legacy_target_states": [
                    {"plugin_id": "b.generator", "sunset_phase": "pre_sunset"},
                    {"plugin_id": "c.generator", "sunset_phase": "grace_window"},
                    {"plugin_id": "a.generator", "sunset_phase": "hard_error"},
                ]
            }
        },
    )
    builder = GeneratorReadinessEvidenceBuilder("base.builder.generator_readiness_evidence")

    result = _run_builder(builder, ctx)

    assert result.status == PluginStatus.SUCCESS
    output_path = Path(result.output_data["generator_readiness_evidence_path"])
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["status"] == "blocked"
    assert payload["sunset_phase_breakdown"] == {
        "pre_sunset_legacy_targets": 1,
        "grace_window_legacy_targets": 1,
        "hard_error_legacy_targets": 1,
    }
