#!/usr/bin/env python3
"""Integration tests for storage media inventory validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage
from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.storage_media_inventory"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_storage_media_inventory_validator_manifest_requires_normalized_rows() -> None:
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
                "storage_slots": [
                    {"id": "slot0", "bus": "sata", "mount": "replaceable"},
                    {"id": "slot1", "bus": "sata", "mount": "replaceable"},
                ]
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


def test_storage_media_inventory_validator_accepts_valid_attachments():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_storage_media_inventory_validator_rejects_duplicate_present_slot_claim():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows.append(
        {
            "group": "media_attachments",
            "instance": "attach-2",
            "layer": "L1",
            "class_ref": "class.storage.media_attachment",
            "extensions": {
                "device_ref": "device-a",
                "slot_ref": "slot0",
                "media_ref": "disk-ssd-1",
                "state": "present",
            },
        }
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7854" for diag in result.diagnostics)


def test_storage_media_inventory_validator_rejects_unknown_media_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["media_ref"] = "disk-missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7854" for diag in result.diagnostics)


def test_storage_media_inventory_validator_rejects_duplicate_media_registry_id():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows.insert(
        2,
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
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7854" for diag in result.diagnostics)


def test_storage_media_inventory_validator_rejects_present_media_claimed_by_multiple_slots():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows.append(
        {
            "group": "media_attachments",
            "instance": "attach-2",
            "layer": "L1",
            "class_ref": "class.storage.media_attachment",
            "extensions": {
                "device_ref": "device-a",
                "slot_ref": "slot1",
                "media_ref": "disk-ssd-1",
                "state": "present",
            },
        }
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7854" for diag in result.diagnostics)


def test_storage_media_inventory_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)

def test_storage_media_inventory_validator_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
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

