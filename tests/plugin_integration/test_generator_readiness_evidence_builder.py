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

    result = builder.execute(ctx, Stage.BUILD)

    assert result.status == PluginStatus.SUCCESS
    output_path = Path(result.output_data["generator_readiness_evidence_path"])
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["status"] == "green"


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
    ctx._published_data = {  # noqa: SLF001 - test fixture setup
        "base.validator.generator_migration_status": {
            "generator_migration_summary": {"legacy": 1, "migrating": 0, "migrated": 0, "rollback": 0}
        },
        "base.validator.generator_sunset": {
            "generator_sunset_summary": {"warnings": 1, "errors": 1, "legacy_targets": 1}
        },
        "base.validator.generator_rollback_escalation": {
            "generator_rollback_summary": {"warnings": 0, "escalated": 0, "missing_started_at": 0}
        },
        "base.builder.artifact_family_summary": {"artifact_family_summary": {"totals": {"plugins": 3}}},
    }
    builder = GeneratorReadinessEvidenceBuilder("base.builder.generator_readiness_evidence")

    result = builder.execute(ctx, Stage.BUILD)

    assert result.status == PluginStatus.SUCCESS
    output_path = Path(result.output_data["generator_readiness_evidence_path"])
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["status"] == "blocked"
    assert payload["artifact_family_summary_totals"]["plugins"] == 3
