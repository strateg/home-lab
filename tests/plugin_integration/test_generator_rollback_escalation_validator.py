#!/usr/bin/env python3
"""Integration checks for ADR0093 rollback escalation validator."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from kernel.plugin_registry import PluginRegistry
from plugins.validators.generator_rollback_escalation_validator import (
    GeneratorRollbackEscalationValidator,
)


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    registry.load_manifest(Path("topology/object-modules/proxmox/plugins.yaml"))
    registry.load_manifest(Path("topology/object-modules/mikrotik/plugins.yaml"))
    return registry


def _run_validator(validator: GeneratorRollbackEscalationValidator, ctx: PluginContext):
    ctx._set_execution_context(validator.plugin_id, set())  # noqa: SLF001 - direct plugin execution helper
    try:
        return validator.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_context()  # noqa: SLF001 - direct plugin execution helper


def test_rollback_escalation_validator_succeeds_when_no_rollback_generators(tmp_path: Path) -> None:
    policy_file = tmp_path / "generator-rollback-policy.yaml"
    policy_file.write_text(
        "schema_version: 1\nmax_rollback_days: 7\ngenerators: {}\n",
        encoding="utf-8",
    )
    registry = _registry()
    validator = GeneratorRollbackEscalationValidator("base.validator.generator_rollback_escalation")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "plugin_registry": registry,
            "repo_root": str(tmp_path),
            "rollback_today": "2026-04-07",
            "rollback_policy_path": "generator-rollback-policy.yaml",
        },
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.SUCCESS
    summary = result.output_data["generator_rollback_summary"]
    assert summary["rollback_generators"] == 0
    assert summary["warnings"] == 0


def test_rollback_escalation_validator_warns_after_threshold(tmp_path: Path) -> None:
    policy_file = tmp_path / "generator-rollback-policy.yaml"
    policy_file.write_text(
        """
schema_version: 1
max_rollback_days: 7
generators:
  object.proxmox.generator.terraform:
    rollback_started_at: "2026-04-01"
""".strip() + "\n",
        encoding="utf-8",
    )
    registry = _registry()
    registry.specs["object.proxmox.generator.terraform"].migration_mode = "rollback"
    validator = GeneratorRollbackEscalationValidator("base.validator.generator_rollback_escalation")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "plugin_registry": registry,
            "repo_root": str(tmp_path),
            "rollback_today": "2026-04-10",
            "rollback_policy_path": "generator-rollback-policy.yaml",
        },
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W9403" for diag in result.diagnostics)


def test_rollback_escalation_validator_warns_when_started_at_missing(tmp_path: Path) -> None:
    policy_file = tmp_path / "generator-rollback-policy.yaml"
    policy_file.write_text(
        "schema_version: 1\nmax_rollback_days: 7\ngenerators: {}\n",
        encoding="utf-8",
    )
    registry = _registry()
    registry.specs["object.proxmox.generator.terraform"].migration_mode = "rollback"
    validator = GeneratorRollbackEscalationValidator("base.validator.generator_rollback_escalation")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "plugin_registry": registry,
            "repo_root": str(tmp_path),
            "rollback_today": "2026-04-07",
            "rollback_policy_path": "generator-rollback-policy.yaml",
        },
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W9402" for diag in result.diagnostics)


def test_rollback_escalation_validator_fails_when_policy_file_missing(tmp_path: Path) -> None:
    registry = _registry()
    validator = GeneratorRollbackEscalationValidator("base.validator.generator_rollback_escalation")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "plugin_registry": registry,
            "repo_root": str(tmp_path),
            "rollback_today": "2026-04-07",
            "rollback_policy_path": "missing-policy.yaml",
        },
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9400" for diag in result.diagnostics)
