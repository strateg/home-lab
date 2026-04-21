#!/usr/bin/env python3
"""Integration tests for storage device taxonomy validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage
from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.storage_device_taxonomy"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_storage_device_taxonomy_validator_manifest_requires_normalized_rows() -> None:
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
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def _base_rows() -> list[dict]:
    return [
        {
            "group": "devices",
            "instance": "device-a",
            "layer": "L1",
            "class_ref": "class.compute.edge_node",
            "extensions": {
                "substrate": "baremetal-owned",
                "storage_slots": [
                    {"id": "slot0", "bus": "sata", "mount": "replaceable"},
                ],
            },
        },
        {
            "group": "media_registry",
            "instance": "disk-ssd-1",
            "layer": "L1",
            "class_ref": "class.storage.media",
            "extensions": {
                "media_type": "ssd",
                "supported_buses": ["sata"],
                "removable": False,
                "virtual": False,
            },
        },
        {
            "group": "media_attachments",
            "instance": "attach-1",
            "layer": "L1",
            "class_ref": "class.storage.media_attachment",
            "extensions": {
                "device_ref": "device-a",
                "slot_ref": "slot0",
                "media_ref": "disk-ssd-1",
                "state": "present",
            },
        },
    ]


def test_storage_device_taxonomy_validator_accepts_valid_inventory():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_storage_device_taxonomy_validator_rejects_duplicate_slot_id():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["extensions"]["storage_slots"] = [  # type: ignore[index]
        {"id": "slot0", "bus": "sata", "mount": "replaceable"},
        {"id": "slot0", "bus": "sata", "mount": "replaceable"},
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7852" for diag in result.diagnostics)


def test_storage_device_taxonomy_validator_rejects_mount_bus_incompatibility():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["extensions"]["storage_slots"] = [  # type: ignore[index]
        {"id": "slot0", "bus": "sata", "mount": "soldered"},
    ]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7852" for diag in result.diagnostics)


def test_storage_device_taxonomy_validator_warns_on_legacy_os_block_without_planned_state():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["extensions"]["os"] = {"supported_operating_systems": ["linux"]}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7853" for diag in result.diagnostics)


def test_storage_device_taxonomy_validator_warns_when_slots_have_no_attached_media():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()[:2]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7853" for diag in result.diagnostics)


def test_storage_device_taxonomy_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)

def test_storage_device_taxonomy_validator_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
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

