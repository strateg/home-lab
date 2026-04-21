#!/usr/bin/env python3
"""Integration tests for service dependency refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage
from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.service_dependency_refs"


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
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def _base_rows() -> list[dict]:
    return [
        {"group": "data-assets", "instance": "inst.asset.a", "class_ref": "class.storage.data_asset"},
        {"group": "services", "instance": "svc-a", "class_ref": "class.service.monitoring", "extensions": {}},
        {
            "group": "services",
            "instance": "svc-b",
            "class_ref": "class.service.alerting",
            "extensions": {
                "data_asset_refs": ["inst.asset.a"],
                "dependencies": [{"service_ref": "svc-a"}],
            },
        },
    ]


def test_service_dependency_refs_validator_accepts_valid_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_service_dependency_refs_validator_rejects_unknown_data_asset_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["data_asset_refs"] = ["inst.asset.missing"]  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7849" for diag in result.diagnostics)


def test_service_dependency_refs_validator_rejects_non_service_dependency_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["dependencies"] = [{"service_ref": "inst.asset.a"}]  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7850" for diag in result.diagnostics)


def test_service_dependency_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code in {"E7848", "E8003"} for diag in result.diagnostics)
