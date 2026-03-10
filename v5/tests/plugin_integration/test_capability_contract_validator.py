#!/usr/bin/env python3
"""Integration tests for capability contract validator plugin ownership/cutover."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.capability_contract"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_capability_contract_validator_skips_when_core_is_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_capability_contract": "core"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_capability_contract_validator_plugin_owner_detects_contract_errors():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_capability_contract": "plugin",
            "capability_catalog_ids": ["cap.net.a"],
            "capability_packs": {},
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

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    codes = [d.code for d in result.diagnostics]
    assert "E3201" in codes
