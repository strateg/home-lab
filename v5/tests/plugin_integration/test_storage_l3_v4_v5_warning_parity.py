#!/usr/bin/env python3
"""Side-by-side warning/error parity checks for v4 and v5 storage L3 semantics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.storage_l3_refs"
V4_STORAGE_CHECKS = Path(__file__).resolve().parents[3] / "v4" / "topology-tools" / "scripts" / "validators" / "checks" / "storage.py"


def _load_v4_storage_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_storage_checks", V4_STORAGE_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 storage checks module from {V4_STORAGE_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context() -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
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


def test_infer_from_vg_name_missing_is_warning_in_v4_and_v5():
    v4_module = _load_v4_storage_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_l3_storage_refs(
        topology={
            "L3_data": {
                "volume_groups": [{"id": "vg.other", "name": "vg-other"}],
                "logical_volumes": [{"id": "lv.other", "name": "lv-other"}],
                "storage_endpoints": [
                    {
                        "id": "endpoint.a",
                        "type": "lvmthin",
                        "infer_from": {
                            "media_attachment_ref": "attach.a",
                            "vg_name": "vg-missing",
                            "lv_name": "lv-missing",
                        },
                    }
                ],
            },
            "L7_operations": {"backup": {"policies": []}},
        },
        ids={"devices": set()},
        topology_path=None,
        storage_ctx={"media_by_id": {}, "media_attachments": [{"id": "attach.a"}]},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("infer_from.vg_name" in message for message in v4_warnings)

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
        ],
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "W7867" for diag in result.diagnostics)


def test_backup_policy_ref_missing_is_error_in_v4_and_v5():
    v4_module = _load_v4_storage_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_l3_storage_refs(
        topology={
            "L3_data": {
                "data_assets": [
                    {
                        "id": "asset.a",
                        "category": "database",
                        "engine": "postgresql",
                        "criticality": "critical",
                        "backup_policy_refs": ["backup.missing"],
                    }
                ],
            },
            "L7_operations": {"backup": {"policies": []}},
        },
        ids={"devices": set()},
        topology_path=None,
        storage_ctx={"media_by_id": {}, "media_attachments": []},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("backup_policy_ref 'backup.missing'" in message for message in v4_errors)

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
                "extensions": {
                    "category": "database",
                    "engine": "postgresql",
                    "criticality": "critical",
                    "backup_policy_refs": ["backup.missing"],
                },
            }
        ],
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7867" for diag in result.diagnostics)
