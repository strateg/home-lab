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


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    registry.load_manifest(Path("topology/object-modules/proxmox/plugins.yaml"))
    registry.load_manifest(Path("topology/object-modules/mikrotik/plugins.yaml"))
    return registry


def _ctx(registry: PluginRegistry, *, enforce_migrating: bool = False) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json={},
        config={"plugin_registry": registry, "enforce_migrating": enforce_migrating},
    )


def _required_keys_payload(*, generated_dir: str | None = None) -> dict[str, object]:
    return {
        "artifact_plan": {"schema_version": "1.0"},
        "artifact_generation_report": {"schema_version": "1.0"},
        "artifact_contract_files": ["/tmp/artifact-plan.json"],
        "generated_dir": generated_dir or "/tmp/generated/default",
    }


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
        ctx._published_data[plugin_id] = _required_keys_payload(  # noqa: SLF001 - test fixture setup
            generated_dir=f"/tmp/generated/{plugin_id.replace('.', '_')}_{idx}"
        )

    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")
    result = plugin.execute(ctx, Stage.ASSEMBLE)

    assert result.status == PluginStatus.SUCCESS
    assert result.output_data is not None
    summary = result.output_data["artifact_contract_guard"]
    assert summary["migrating"] >= 3
    assert summary["checked"] >= 3
    assert summary["missing_contracts"] == []


def test_artifact_contract_assembler_warns_for_missing_migrating_contracts_by_default() -> None:
    registry = _registry()
    ctx = _ctx(registry, enforce_migrating=False)
    migrating = _migrating_generators(registry)
    assert migrating
    for plugin_id in migrating[1:]:
        ctx._published_data[plugin_id] = _required_keys_payload(  # noqa: SLF001 - test fixture setup
            generated_dir=f"/tmp/generated/{plugin_id.replace('.', '_')}"
        )

    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")
    result = plugin.execute(ctx, Stage.ASSEMBLE)

    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W9393" for diag in result.diagnostics)


def test_artifact_contract_assembler_errors_when_migrating_enforcement_is_enabled() -> None:
    registry = _registry()
    ctx = _ctx(registry, enforce_migrating=True)
    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")

    result = plugin.execute(ctx, Stage.ASSEMBLE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9394" for diag in result.diagnostics)


def test_artifact_contract_assembler_errors_for_missing_migrated_contracts() -> None:
    registry = _registry()
    migrating = _migrating_generators(registry)
    assert migrating
    registry.specs[migrating[0]].migration_mode = "migrated"
    ctx = _ctx(registry, enforce_migrating=False)

    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")
    result = plugin.execute(ctx, Stage.ASSEMBLE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9394" for diag in result.diagnostics)


def test_artifact_contract_assembler_detects_overlapping_generated_dir_prefixes() -> None:
    registry = _registry()
    ctx = _ctx(registry, enforce_migrating=False)
    migrating = _migrating_generators(registry)
    assert len(migrating) >= 2

    ctx._published_data[migrating[0]] = _required_keys_payload(  # noqa: SLF001 - test fixture setup
        generated_dir="/tmp/generated/shared"
    )
    ctx._published_data[migrating[1]] = _required_keys_payload(  # noqa: SLF001 - test fixture setup
        generated_dir="/tmp/generated/shared/nested"
    )
    for plugin_id in migrating[2:]:
        ctx._published_data[plugin_id] = _required_keys_payload(  # noqa: SLF001 - test fixture setup
            generated_dir=f"/tmp/generated/{plugin_id.replace('.', '_')}"
        )

    plugin = ArtifactContractAssembler("base.assembler.artifact_contract_guard")
    result = plugin.execute(ctx, Stage.ASSEMBLE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9391" for diag in result.diagnostics)
