#!/usr/bin/env python3
"""Integration checks for assemble-stage artifact contract guard."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from kernel.plugin_registry import PluginRegistry
from plugins.assemblers.artifact_contract_assembler import ArtifactContractAssembler
from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    registry.load_manifest(Path("topology/object-modules/proxmox/plugins.yaml"))
    registry.load_manifest(Path("topology/object-modules/mikrotik/plugins.yaml"))
    return registry


def _ctx(registry: PluginRegistry) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={"plugin_registry": registry},
    )


def _run_guard(plugin: ArtifactContractAssembler, ctx: PluginContext, registry: PluginRegistry):
    spec = registry.specs[plugin.plugin_id]
    ctx.config.update(spec.config)
    return run_plugin_for_test(plugin, ctx, Stage.ASSEMBLE, consumes_keys=set(spec.depends_on))


def _required_keys_payload(*, generated_dir: str | None = None) -> dict[str, object]:
    return {
        "artifact_plan": {"schema_version": "1.0"},
        "artifact_generation_report": {"schema_version": "1.0"},
        "artifact_contract_files": ["/tmp/artifact-plan.json"],
        "generated_dir": generated_dir or "/tmp/generated/default",
    }


def _publish(ctx: PluginContext, plugin_id: str, payload: dict[str, object]) -> None:
    for key, value in payload.items():
        publish_for_test(ctx, plugin_id, key, value)


def _migrating_generators(registry: PluginRegistry) -> list[str]:
    return sorted(
        plugin_id
        for plugin_id, spec in registry.specs.items()
        if getattr(spec, "kind", None).value == "generator" and getattr(spec, "migration_mode", "legacy") == "migrating"
    )


def test_artifact_contract_assembler_passes_when_migrating_generators_publish_contracts() -> None:
    registry = _registry()
    ctx = _ctx(registry)
    for idx, plugin_id in enumerate(_migrating_generators(registry)):
        _publish(
            ctx,
            plugin_id,
            _required_keys_payload(
                generated_dir=f"/tmp/generated/{plugin_id.replace('.', '_')}_{idx}"
            ),
        )

    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")
    result = _run_guard(plugin, ctx, registry)

    assert result.status == PluginStatus.SUCCESS
    assert result.output_data is not None
    summary = result.output_data["artifact_contract_guard"]
    assert summary["migrating"] >= 3
    assert summary["checked"] >= 3
    assert len(summary["checked_plugins"]) == summary["checked"]
    assert all(isinstance(item.get("artifact_plan"), dict) for item in summary["checked_plugins"])
    assert all(isinstance(item.get("artifact_generation_report"), dict) for item in summary["checked_plugins"])
    assert summary["missing_contracts"] == []
    assert any(diag.code == "I9397" for diag in result.diagnostics)
    assert not any(diag.code == "E9394" for diag in result.diagnostics)


def test_artifact_contract_assembler_errors_for_missing_migrating_contracts() -> None:
    registry = _registry()
    ctx = _ctx(registry)
    migrating = _migrating_generators(registry)
    assert migrating
    for plugin_id in migrating[1:]:
        _publish(
            ctx,
            plugin_id,
            _required_keys_payload(generated_dir=f"/tmp/generated/{plugin_id.replace('.', '_')}"),
        )

    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")
    result = _run_guard(plugin, ctx, registry)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9394" for diag in result.diagnostics)


def test_artifact_contract_assembler_errors_for_missing_migrated_contracts() -> None:
    registry = _registry()
    migrating = _migrating_generators(registry)
    assert migrating
    registry.specs[migrating[0]].migration_mode = "migrated"
    ctx = _ctx(registry)

    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")
    result = _run_guard(plugin, ctx, registry)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9394" for diag in result.diagnostics)


def test_artifact_contract_assembler_detects_overlapping_generated_dir_prefixes() -> None:
    registry = _registry()
    ctx = _ctx(registry)
    migrating = _migrating_generators(registry)
    assert len(migrating) >= 2

    _publish(ctx, migrating[0], _required_keys_payload(generated_dir="/tmp/generated/shared"))
    _publish(ctx, migrating[1], _required_keys_payload(generated_dir="/tmp/generated/shared/nested"))
    for plugin_id in migrating[2:]:
        _publish(
            ctx,
            plugin_id,
            _required_keys_payload(generated_dir=f"/tmp/generated/{plugin_id.replace('.', '_')}"),
        )

    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")
    result = _run_guard(plugin, ctx, registry)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9391" for diag in result.diagnostics)
