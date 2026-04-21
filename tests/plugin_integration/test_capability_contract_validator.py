#!/usr/bin/env python3
"""Integration tests for capability contract validator plugin ownership/cutover."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage
from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.capability_contract"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_capability_contract_validator_skips_when_core_is_owner():
    registry = _registry()
    spec = registry.specs[PLUGIN_ID]
    required_inputs = {
        ("base.compiler.capability_contract_loader", "catalog_ids"),
        ("base.compiler.capability_contract_loader", "packs_map"),
        ("base.compiler.module_loader", "class_module_paths"),
        ("base.compiler.module_loader", "object_module_paths"),
    }
    assert {
        (item["from_plugin"], item["key"])
        for item in spec.consumes
        if item.get("required") is True
    } >= required_inputs
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_capability_contract": "core"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "packs_map", {})
    publish_for_test(ctx, "base.compiler.module_loader", "class_module_paths", {})
    publish_for_test(ctx, "base.compiler.module_loader", "object_module_paths", {})

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_capability_contract_validator_plugin_owner_detects_contract_errors():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_capability_contract": "plugin",
            "require_new_model": False,
        },
        classes={
            "class.router": {
                "class": "class.router",
                "required_capabilities": ["cap.net.a"],
                "optional_capabilities": [],
                "capability_packs": [],
            }
        },
        objects={
            "obj.router.bad": {
                "object": "obj.router.bad",
                "class_ref": "class.router",
                "enabled_capabilities": ["cap.unknown"],
                "enabled_packs": [],
                "vendor_capabilities": ["not-vendor-format"],
            }
        },
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", ["cap.net.a"])
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "packs_map", {})
    publish_for_test(ctx, "base.compiler.module_loader", "class_module_paths", {})
    publish_for_test(ctx, "base.compiler.module_loader", "object_module_paths", {})

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    codes = [d.code for d in result.diagnostics]
    assert "E3201" in codes


def test_capability_contract_validator_reads_contract_data_via_subscribe():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_capability_contract": "plugin",
            "require_new_model": False,
        },
        classes={
            "class.router": {
                "class": "class.router",
                "required_capabilities": ["cap.net.a"],
                "optional_capabilities": [],
                "capability_packs": [],
            }
        },
        objects={
            "obj.router.bad": {
                "object": "obj.router.bad",
                "class_ref": "class.router",
                "enabled_capabilities": ["cap.unknown"],
                "enabled_packs": [],
                "vendor_capabilities": [],
            }
        },
        instance_bindings={"instance_bindings": {}},
    )

    # Seed published data exactly as compiler plugins do in compile stage.
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", ["cap.net.a"])
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "packs_map", {})
    publish_for_test(ctx, "base.compiler.module_loader", "class_module_paths", {})
    publish_for_test(ctx, "base.compiler.module_loader", "object_module_paths", {})

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.FAILED
    codes = [d.code for d in result.diagnostics]
    assert "E3201" in codes


def test_capability_contract_validator_execute_stage_requires_committed_loader_inputs(tmp_path: Path) -> None:
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_capability_contract": "plugin",
            "require_new_model": False,
        },
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)
