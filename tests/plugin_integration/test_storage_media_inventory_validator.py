#!/usr/bin/env python3
"""Integration tests for storage media inventory validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.storage_media_inventory"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


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


def test_storage_media_inventory_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7854" for diag in result.diagnostics)
