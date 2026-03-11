#!/usr/bin/env python3
"""Integration tests for reference validator plugin ownership/parity prep."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.references"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_reference_validator_skips_when_core_is_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "core"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_reference_validator_detects_missing_refs_when_plugin_owner():
    registry = _registry()
    rows = [
        {
            "group": "l1_devices",
            "instance": "inst.dev.1",
            "class_ref": "class.router",
            "object_ref": "obj.router",
            "firmware_ref": "inst.fw.unknown",
            "os_refs": ["inst.os.unknown"],
        }
    ]
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_references": "plugin",
            "normalized_rows": rows,
            "capability_catalog_ids": [],
        },
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E2101" and d.stage == "resolve" for d in result.diagnostics)


def test_reference_validator_enforces_required_software_policies():
    registry = _registry()
    rows = [
        {
            "group": "l1_devices",
            "instance": "inst.dev.2",
            "class_ref": "class.router",
            "object_ref": "obj.router",
            "firmware_ref": None,
            "os_refs": [],
        }
    ]
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_references": "plugin",
            "normalized_rows": rows,
            "capability_catalog_ids": [],
        },
        classes={
            "class.router": {
                "class": "class.router",
                "os_policy": "required",
                "firmware_policy": "required",
                "multi_boot": False,
            }
        },
        objects={"obj.router": {"object": "obj.router", "class_ref": "class.router"}},
        instance_bindings={"instance_bindings": {}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    policy_errors = [d for d in result.diagnostics if d.code == "E3201"]
    assert len(policy_errors) >= 2


def test_reference_validator_reads_rows_and_catalog_via_subscribe():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_references": "plugin"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "l1_devices",
                "instance": "inst.dev.subscribed",
                "class_ref": "class.router",
                "object_ref": "obj.router",
                "firmware_ref": "inst.fw.unknown",
                "os_refs": ["inst.os.unknown"],
            }
        ],
    )
    ctx._clear_execution_context()

    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E2101" and d.stage == "resolve" for d in result.diagnostics)
