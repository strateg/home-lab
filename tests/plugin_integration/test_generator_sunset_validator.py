#!/usr/bin/env python3
"""Integration checks for ADR0093 generator sunset validator."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from kernel.plugin_registry import PluginRegistry
from plugins.validators.generator_sunset_validator import GeneratorSunsetValidator


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    registry.load_manifest(Path("topology/object-modules/proxmox/plugins.yaml"))
    registry.load_manifest(Path("topology/object-modules/mikrotik/plugins.yaml"))
    registry.load_manifest(Path("topology/object-modules/orangepi/plugins.yaml"))
    return registry


def _ctx(registry: PluginRegistry, *, today: str, sunset: str, hard_error: str) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "plugin_registry": registry,
            "sunset_today": today,
            "sunset_schedule": {
                "object.proxmox.generator.terraform": {
                    "compatibility_sunset": sunset,
                    "hard_error_date": hard_error,
                },
                "object.mikrotik.generator.terraform": {
                    "compatibility_sunset": sunset,
                    "hard_error_date": hard_error,
                },
                "base.generator.ansible_inventory": {
                    "compatibility_sunset": sunset,
                    "hard_error_date": hard_error,
                },
            },
        },
    )


def _run_validator(validator: GeneratorSunsetValidator, ctx: PluginContext):
    ctx._set_execution_context(validator.plugin_id, set())  # noqa: SLF001 - direct plugin execution helper
    try:
        return validator.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_context()  # noqa: SLF001 - direct plugin execution helper


def test_generator_sunset_validator_succeeds_for_non_legacy_targets() -> None:
    registry = _registry()
    validator = GeneratorSunsetValidator("base.validator.generator_sunset")
    ctx = _ctx(registry, today="2026-04-07", sunset="2026-05-01", hard_error="2026-05-15")

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.SUCCESS
    summary = result.output_data["generator_sunset_summary"]
    assert summary["scheduled_targets"] == 3
    assert summary["legacy_targets"] == 0
    assert summary["pre_sunset_legacy_targets"] == 0
    assert summary["grace_window_legacy_targets"] == 0
    assert summary["legacy_target_states"] == []
    assert summary["errors"] == 0
    assert any(diag.code == "I9399" for diag in result.diagnostics)


def test_generator_sunset_validator_warns_for_legacy_target_before_sunset() -> None:
    registry = _registry()
    registry.specs["object.proxmox.generator.terraform"].migration_mode = "legacy"
    validator = GeneratorSunsetValidator("base.validator.generator_sunset")
    ctx = _ctx(registry, today="2026-04-10", sunset="2026-05-01", hard_error="2026-05-15")

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.PARTIAL
    summary = result.output_data["generator_sunset_summary"]
    assert summary["legacy_targets"] == 1
    assert summary["pre_sunset_legacy_targets"] == 1
    assert summary["grace_window_legacy_targets"] == 0
    assert len(summary["legacy_target_states"]) == 1
    assert summary["legacy_target_states"][0]["plugin_id"] == "object.proxmox.generator.terraform"
    assert summary["legacy_target_states"][0]["sunset_phase"] == "pre_sunset"
    assert summary["warnings"] == 1
    assert summary["errors"] == 0
    assert any(diag.code == "W9397" for diag in result.diagnostics)


def test_generator_sunset_validator_warns_for_legacy_target_in_grace_window() -> None:
    registry = _registry()
    registry.specs["object.proxmox.generator.terraform"].migration_mode = "legacy"
    validator = GeneratorSunsetValidator("base.validator.generator_sunset")
    ctx = _ctx(registry, today="2026-05-10", sunset="2026-05-01", hard_error="2026-05-15")

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.PARTIAL
    summary = result.output_data["generator_sunset_summary"]
    assert summary["legacy_targets"] == 1
    assert summary["pre_sunset_legacy_targets"] == 0
    assert summary["grace_window_legacy_targets"] == 1
    assert len(summary["legacy_target_states"]) == 1
    assert summary["legacy_target_states"][0]["plugin_id"] == "object.proxmox.generator.terraform"
    assert summary["legacy_target_states"][0]["sunset_phase"] == "grace_window"
    assert summary["warnings"] == 1
    assert summary["errors"] == 0
    assert any(diag.code == "W9397" for diag in result.diagnostics)


def test_generator_sunset_validator_fails_for_legacy_target_after_hard_error() -> None:
    registry = _registry()
    registry.specs["object.proxmox.generator.terraform"].migration_mode = "legacy"
    validator = GeneratorSunsetValidator("base.validator.generator_sunset")
    ctx = _ctx(registry, today="2026-05-16", sunset="2026-05-01", hard_error="2026-05-15")

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.FAILED
    summary = result.output_data["generator_sunset_summary"]
    assert summary["legacy_targets"] == 1
    assert summary["pre_sunset_legacy_targets"] == 0
    assert summary["grace_window_legacy_targets"] == 0
    assert len(summary["legacy_target_states"]) == 1
    assert summary["legacy_target_states"][0]["plugin_id"] == "object.proxmox.generator.terraform"
    assert summary["legacy_target_states"][0]["sunset_phase"] == "hard_error"
    assert summary["errors"] == 1
    assert any(diag.code == "E9399" for diag in result.diagnostics)


def test_generator_sunset_validator_loads_schedule_from_policy_file(tmp_path: Path) -> None:
    registry = _registry()
    validator = GeneratorSunsetValidator("base.validator.generator_sunset")
    policy_file = tmp_path / "generator-sunset-policy.yaml"
    policy_file.write_text(
        """
schema_version: 1
sunset_schedule:
  object.proxmox.generator.terraform:
    compatibility_sunset: "2026-05-01"
    hard_error_date: "2026-05-15"
""".strip() + "\n",
        encoding="utf-8",
    )
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "plugin_registry": registry,
            "repo_root": str(tmp_path),
            "sunset_today": "2026-04-07",
            "sunset_policy_path": "generator-sunset-policy.yaml",
        },
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.SUCCESS
    summary = result.output_data["generator_sunset_summary"]
    assert summary["scheduled_targets"] == 1
    assert summary["legacy_targets"] == 0
    assert summary["pre_sunset_legacy_targets"] == 0
    assert summary["grace_window_legacy_targets"] == 0
    assert summary["legacy_target_states"] == []


def test_generator_sunset_validator_fails_when_policy_file_is_missing(tmp_path: Path) -> None:
    registry = _registry()
    validator = GeneratorSunsetValidator("base.validator.generator_sunset")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "plugin_registry": registry,
            "repo_root": str(tmp_path),
            "sunset_today": "2026-04-07",
            "sunset_policy_path": "missing-policy.yaml",
        },
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9396" for diag in result.diagnostics)


def test_generator_sunset_validator_default_policy_includes_secondary_families() -> None:
    registry = _registry()
    validator = GeneratorSunsetValidator("base.validator.generator_sunset")
    repo_root = Path(__file__).resolve().parents[2]
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={
            "plugin_registry": registry,
            "repo_root": str(repo_root),
            "sunset_today": "2026-04-07",
            "sunset_policy_path": "topology-tools/data/generator-sunset-policy.yaml",
        },
    )

    result = _run_validator(validator, ctx)

    assert result.status == PluginStatus.SUCCESS
    summary = result.output_data["generator_sunset_summary"]
    assert summary["scheduled_targets"] == 6
    assert summary["legacy_targets"] == 0
    assert summary["pre_sunset_legacy_targets"] == 0
    assert summary["grace_window_legacy_targets"] == 0
    assert summary["legacy_target_states"] == []
    assert not any(diag.code == "W9397" for diag in result.diagnostics)


def test_generator_sunset_policy_targets_are_non_legacy() -> None:
    registry = _registry()
    policy_path = Path(__file__).resolve().parents[2] / "topology-tools" / "data" / "generator-sunset-policy.yaml"
    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    sunset_schedule = payload.get("sunset_schedule", {})
    assert isinstance(sunset_schedule, dict)

    target_ids = sorted(sunset_schedule.keys())
    assert target_ids
    for plugin_id in target_ids:
        spec = registry.specs.get(plugin_id)
        assert spec is not None, f"Policy target missing in registry: {plugin_id}"
        assert (
            str(getattr(spec, "migration_mode", "")).strip().lower() != "legacy"
        ), f"Policy target must not remain legacy: {plugin_id}"
