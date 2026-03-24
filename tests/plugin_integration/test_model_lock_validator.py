#!/usr/bin/env python3
"""Integration tests for model_lock validator plugin ownership/cutover."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.model_lock"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_model_lock_validator_skips_when_core_is_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_model_lock": "core"},
        classes={"class.router": {"version": "1.0.0"}},
        objects={"obj.router": {"version": "1.0.0"}},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {"instance": "r1", "class_ref": "class.router", "object_ref": "obj.router"},
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_model_lock_validator_plugin_owner_missing_lock_strict_mode():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_model_lock": "plugin",
            "strict_mode": True,
        },
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    ctx._set_execution_context("base.compiler.model_lock_loader", set())
    ctx.publish("model_lock_loaded", False)
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E3201" for d in result.diagnostics)
    assert any(d.path == "model.lock" for d in result.diagnostics)


def test_model_lock_validator_matches_legacy_rules_when_plugin_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_model_lock": "plugin",
            "strict_mode": False,
        },
        classes={
            "class.router": {"version": "1.0.0"},
            "class.unpinned": {"version": "0.1.0"},
        },
        objects={
            "obj.router": {"version": "2.0.0"},
            "obj.unpinned": {"version": "0.1.0"},
        },
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {"instance": "r1", "class_ref": "class.router", "object_ref": "obj.router"},
                    {"instance": "r2", "class_ref": "class.unpinned", "object_ref": "obj.unpinned"},
                ]
            }
        },
    )
    ctx._set_execution_context("base.compiler.model_lock_loader", set())
    ctx.publish("model_lock_loaded", True)
    ctx.publish(
        "lock_payload",
        {
            "classes": {
                "class.router": {"version": "1.1.0"},
            },
            "objects": {
                "obj.router": {"version": "2.1.0", "class_ref": "class.switch"},
            },
        },
    )
    ctx._clear_execution_context()
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {"group": "devices", "instance": "r1", "class_ref": "class.router", "object_ref": "obj.router"},
            {"group": "devices", "instance": "r2", "class_ref": "class.unpinned", "object_ref": "obj.unpinned"},
        ],
    )
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED

    codes = [d.code for d in result.diagnostics]
    assert "I2401" in codes
    assert "W2402" in codes
    assert "W2403" in codes
    assert "E2403" in codes
    # Both class and object version mismatches produce W3201
    assert codes.count("W3201") >= 2
    assert any(d.code == "I2401" and d.stage == "load" for d in result.diagnostics)


def test_model_lock_validator_reads_lock_and_rows_via_subscribe():
    registry = _registry()
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "validation_owner_model_lock": "plugin",
            "strict_mode": False,
        },
        classes={"class.router": {"version": "1.0.0"}},
        objects={"obj.router": {"version": "1.0.0"}},
        instance_bindings={"instance_bindings": {}},
    )

    ctx._set_execution_context("base.compiler.model_lock_loader", set())
    ctx.publish("model_lock_loaded", True)
    ctx.publish("lock_payload", {"classes": {}, "objects": {}})
    ctx._clear_execution_context()

    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "r1",
                "class_ref": "class.router",
                "object_ref": "obj.router",
            }
        ],
    )
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    codes = [d.code for d in result.diagnostics]
    assert "I2401" in codes
    assert "W2402" in codes
    assert "W2403" in codes
    assert "E2402" not in codes
