#!/usr/bin/env python3
"""Integration tests for foundation device taxonomy validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.foundation_device_taxonomy"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_foundation_device_taxonomy_validator_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def _valid_rows() -> list[dict]:
    return [
        {"group": "devices", "instance": "rtr-a", "layer": "L1", "class_ref": "class.router"},
        {"group": "devices", "instance": "srv-a", "layer": "L1", "class_ref": "class.compute.hypervisor"},
        {"group": "firmware", "instance": "fw-a", "layer": "L1", "class_ref": "class.firmware"},
        {"group": "os", "instance": "os-a", "layer": "L1", "class_ref": "class.os"},
        {"group": "physical-links", "instance": "link-a", "layer": "L1", "class_ref": "class.network.physical_link"},
        {"group": "power", "instance": "pdu-a", "layer": "L1", "class_ref": "class.power.pdu"},
    ]


def test_foundation_device_taxonomy_validator_accepts_valid_l1_group_taxonomy():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _valid_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_device_taxonomy_validator_rejects_mismatched_group_class():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[2]["class_ref"] = "class.os"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7851" for diag in result.diagnostics)


def test_foundation_device_taxonomy_validator_rejects_storage_class_in_l1_devices_group():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[0]["class_ref"] = "class.storage.media"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7851" for diag in result.diagnostics)


def test_foundation_device_taxonomy_validator_ignores_non_l1_storage_rows():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows.append({"group": "pools", "instance": "pool-a", "layer": "L3", "class_ref": "class.storage.pool"})
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_device_taxonomy_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)

def test_foundation_device_taxonomy_validator_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    spec = _registry().specs[PLUGIN_ID]
    rel_entry, class_name = spec.entry.split(":", 1)
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / "plugins/compilers/instance_rows_compiler.py").as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": spec.kind.value,
                "entry": f"{(V5_TOOLS / "plugins" / rel_entry).as_posix()}:{class_name}",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": spec.phase.value,
                "order": spec.order,
                "depends_on": list(spec.depends_on),
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True}
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)
    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)

