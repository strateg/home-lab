#!/usr/bin/env python3
"""Integration checks for generator migration status validator."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from kernel.plugin_registry import PluginRegistry
from plugins.validators.generator_migration_status_validator import GeneratorMigrationStatusValidator


def test_generator_migration_status_validator_reports_summary() -> None:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    registry.load_manifest(Path("topology/object-modules/proxmox/plugins.yaml"))
    registry.load_manifest(Path("topology/object-modules/mikrotik/plugins.yaml"))

    validator = GeneratorMigrationStatusValidator("base.validator.generator_migration_status")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={"plugin_registry": registry},
    )

    result = validator.execute(ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.SUCCESS
    assert result.output_data is not None
    summary = result.output_data["generator_migration_summary"]
    assert summary["total_generators"] >= 1
    assert summary["migrating"] >= 3
    assert any(diag.code == "I9390" for diag in result.diagnostics)
