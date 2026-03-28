#!/usr/bin/env python3
"""Integration tests for storage L3 refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.storage_l3_refs"


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


def test_storage_l3_refs_validator_accepts_valid_volume_and_asset_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "storage", "instance": "inst.storage.pool.a", "class_ref": "class.storage.pool", "layer": "L3"},
            {
                "group": "storage",
                "instance": "inst.storage.volume.a",
                "class_ref": "class.storage.volume",
                "layer": "L3",
                "extensions": {"pool_ref": "inst.storage.pool.a"},
            },
            {
                "group": "storage",
                "instance": "inst.storage.asset.a",
                "class_ref": "class.storage.data_asset",
                "layer": "L3",
                "extensions": {"volume_ref": "inst.storage.volume.a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_storage_l3_refs_validator_rejects_unknown_pool_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "inst.storage.volume.a",
                "class_ref": "class.storage.volume",
                "layer": "L3",
                "extensions": {"pool_ref": "inst.storage.pool.missing"},
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7831" for diag in result.diagnostics)


def test_storage_l3_refs_validator_rejects_wrong_asset_volume_target_class():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "storage", "instance": "inst.storage.pool.a", "class_ref": "class.storage.pool", "layer": "L3"},
            {
                "group": "storage",
                "instance": "inst.storage.asset.a",
                "class_ref": "class.storage.data_asset",
                "layer": "L3",
                "extensions": {"volume_ref": "inst.storage.pool.a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7832" for diag in result.diagnostics)


def test_storage_l3_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7830" for diag in result.diagnostics)


def test_storage_l3_refs_validator_validates_filesystem_mount_chain():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "storage", "instance": "inst.storage.pool.a", "class_ref": "class.storage.pool", "layer": "L3"},
            {
                "group": "storage",
                "instance": "inst.storage.volume.a",
                "class_ref": "class.storage.volume",
                "layer": "L3",
                "extensions": {"pool_ref": "inst.storage.pool.a"},
            },
            {
                "group": "storage",
                "instance": "inst.storage.partition.a",
                "class_ref": "class.storage.partition",
                "layer": "L3",
            },
            {
                "group": "storage",
                "instance": "inst.storage.vg.a",
                "class_ref": "class.storage.volume_group",
                "layer": "L3",
                "extensions": {"pv_refs": ["inst.storage.partition.a"]},
            },
            {
                "group": "storage",
                "instance": "inst.storage.lv.a",
                "class_ref": "class.storage.logical_volume",
                "layer": "L3",
                "extensions": {"vg_ref": "inst.storage.vg.a"},
            },
            {
                "group": "storage",
                "instance": "inst.storage.fs.a",
                "class_ref": "class.storage.filesystem",
                "layer": "L3",
                "extensions": {"lv_ref": "inst.storage.lv.a"},
            },
            {
                "group": "storage",
                "instance": "inst.storage.mount.a",
                "class_ref": "class.storage.mount_point",
                "layer": "L3",
                "extensions": {"filesystem_ref": "inst.storage.fs.a"},
            },
            {
                "group": "storage",
                "instance": "inst.storage.endpoint.a",
                "class_ref": "class.storage.storage_endpoint",
                "layer": "L3",
                "extensions": {"mount_point_ref": "inst.storage.mount.a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_storage_l3_refs_validator_rejects_filesystem_with_both_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "inst.storage.partition.a",
                "class_ref": "class.storage.partition",
                "layer": "L3",
            },
            {
                "group": "storage",
                "instance": "inst.storage.lv.a",
                "class_ref": "class.storage.logical_volume",
                "layer": "L3",
            },
            {
                "group": "storage",
                "instance": "inst.storage.fs.a",
                "class_ref": "class.storage.filesystem",
                "layer": "L3",
                "extensions": {"lv_ref": "inst.storage.lv.a", "partition_ref": "inst.storage.partition.a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7863" for diag in result.diagnostics)


def test_storage_l3_refs_validator_rejects_volume_group_unknown_pv_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "inst.storage.vg.a",
                "class_ref": "class.storage.volume_group",
                "layer": "L3",
                "extensions": {"pv_refs": ["inst.storage.partition.missing"]},
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7861" for diag in result.diagnostics)


def test_storage_l3_refs_validator_accepts_valid_lvmthin_infer_from_chain():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "media_attachments",
                "instance": "attach.a",
                "class_ref": "class.storage.media_attachment",
                "layer": "L1",
            },
            {
                "group": "storage",
                "instance": "part.a",
                "class_ref": "class.storage.partition",
                "layer": "L3",
                "extensions": {"media_attachment_ref": "attach.a"},
            },
            {
                "group": "storage",
                "instance": "vg.a",
                "class_ref": "class.storage.volume_group",
                "layer": "L3",
                "extensions": {"name": "vg-local", "pv_refs": ["part.a"]},
            },
            {
                "group": "storage",
                "instance": "lv.a",
                "class_ref": "class.storage.logical_volume",
                "layer": "L3",
                "extensions": {"name": "thinpool", "vg_ref": "vg.a"},
            },
            {
                "group": "storage",
                "instance": "endpoint.a",
                "class_ref": "class.storage.storage_endpoint",
                "layer": "L3",
                "extensions": {
                    "type": "lvmthin",
                    "infer_from": {
                        "media_attachment_ref": "attach.a",
                        "vg_name": "vg-local",
                        "lv_name": "thinpool",
                    },
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_storage_l3_refs_validator_rejects_lvmthin_without_required_infer_from_fields():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "endpoint.a",
                "class_ref": "class.storage.storage_endpoint",
                "layer": "L3",
                "extensions": {
                    "type": "lvmthin",
                    "infer_from": {"vg_name": "vg-local"},
                },
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7866" for diag in result.diagnostics)


def test_storage_l3_refs_validator_rejects_critical_data_asset_without_backup_binding():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "asset.a",
                "class_ref": "class.storage.data_asset",
                "layer": "L3",
                "extensions": {"criticality": "critical", "category": "config"},
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7867" for diag in result.diagnostics)


def test_storage_l3_refs_validator_rejects_unknown_backup_policy_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "asset.a",
                "class_ref": "class.storage.data_asset",
                "layer": "L3",
                "extensions": {"backup_policy_refs": ["backup.missing"]},
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7867" for diag in result.diagnostics)


def test_storage_l3_refs_validator_warns_on_unknown_infer_from_vg_name():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "endpoint.a",
                "class_ref": "class.storage.storage_endpoint",
                "layer": "L3",
                "extensions": {
                    "infer_from": {
                        "media_attachment_ref": "attach.a",
                        "vg_name": "vg-missing",
                        "lv_name": "lv-missing",
                    }
                },
            },
            {
                "group": "media_attachments",
                "instance": "attach.a",
                "class_ref": "class.storage.media_attachment",
                "layer": "L1",
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7867" for diag in result.diagnostics)


def test_storage_l3_refs_validator_warns_when_infer_from_combines_with_lv_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "media_attachments",
                "instance": "attach.a",
                "class_ref": "class.storage.media_attachment",
                "layer": "L1",
            },
            {
                "group": "storage",
                "instance": "part.a",
                "class_ref": "class.storage.partition",
                "layer": "L3",
                "extensions": {"media_attachment_ref": "attach.a"},
            },
            {
                "group": "storage",
                "instance": "vg.a",
                "class_ref": "class.storage.volume_group",
                "layer": "L3",
                "extensions": {"name": "vg-local", "pv_refs": ["part.a"]},
            },
            {
                "group": "storage",
                "instance": "lv.a",
                "class_ref": "class.storage.logical_volume",
                "layer": "L3",
                "extensions": {"name": "thinpool", "vg_ref": "vg.a"},
            },
            {
                "group": "storage",
                "instance": "endpoint.a",
                "class_ref": "class.storage.storage_endpoint",
                "layer": "L3",
                "extensions": {
                    "type": "lvmthin",
                    "lv_ref": "lv.a",
                    "infer_from": {
                        "media_attachment_ref": "attach.a",
                        "vg_name": "vg-local",
                        "lv_name": "thinpool",
                    },
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7866" for diag in result.diagnostics)


def test_storage_l3_refs_validator_warns_when_infer_from_lv_name_mismatches_vg():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "media_attachments",
                "instance": "attach.a",
                "class_ref": "class.storage.media_attachment",
                "layer": "L1",
            },
            {
                "group": "storage",
                "instance": "part.a",
                "class_ref": "class.storage.partition",
                "layer": "L3",
                "extensions": {"media_attachment_ref": "attach.a"},
            },
            {
                "group": "storage",
                "instance": "vg.a",
                "class_ref": "class.storage.volume_group",
                "layer": "L3",
                "extensions": {"name": "vg-local", "pv_refs": ["part.a"]},
            },
            {
                "group": "storage",
                "instance": "vg.b",
                "class_ref": "class.storage.volume_group",
                "layer": "L3",
                "extensions": {"name": "vg-other"},
            },
            {
                "group": "storage",
                "instance": "lv.other",
                "class_ref": "class.storage.logical_volume",
                "layer": "L3",
                "extensions": {"name": "lv-other", "vg_ref": "vg.b"},
            },
            {
                "group": "storage",
                "instance": "endpoint.a",
                "class_ref": "class.storage.storage_endpoint",
                "layer": "L3",
                "extensions": {
                    "infer_from": {
                        "media_attachment_ref": "attach.a",
                        "vg_name": "vg-local",
                        "lv_name": "lv-other",
                    }
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7868" for diag in result.diagnostics)


def test_storage_l3_refs_validator_warns_on_unknown_backup_policy_alias():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "storage",
                "instance": "asset.a",
                "class_ref": "class.storage.data_asset",
                "layer": "L3",
                "extensions": {"backup_policy": "custom-policy"},
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7869" for diag in result.diagnostics)
