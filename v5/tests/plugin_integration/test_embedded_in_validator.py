#!/usr/bin/env python3
"""Integration tests for embedded_in validator plugin ownership/cutover."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.embedded_in"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_embedded_in_validator_skips_when_core_is_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_embedded_in": "core"},
        objects={
            "obj.os.embedded": {"object": "obj.os.embedded", "properties": {"installation_model": "embedded"}},
        },
        instance_bindings={
            "instance_bindings": {
                "os": [
                    {
                        "instance": "inst.os.1",
                        "class_ref": "class.os",
                        "object_ref": "obj.os.embedded",
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_embedded_in_validator_matches_legacy_rules_when_plugin_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_embedded_in": "plugin"},
        objects={
            "obj.os.embedded": {
                "object": "obj.os.embedded",
                "class_ref": "class.os",
                "properties": {"installation_model": "embedded"},
            },
            "obj.os.installable": {
                "object": "obj.os.installable",
                "class_ref": "class.os",
                "properties": {"installation_model": "installable"},
            },
            "obj.firmware.a": {"object": "obj.firmware.a", "class_ref": "class.firmware"},
            "obj.firmware.b": {"object": "obj.firmware.b", "class_ref": "class.firmware"},
            "obj.device": {"object": "obj.device", "class_ref": "class.router"},
        },
        instance_bindings={
            "instance_bindings": {
                "firmware": [
                    {"instance": "inst.fw.a", "class_ref": "class.firmware", "object_ref": "obj.firmware.a"},
                    {"instance": "inst.fw.b", "class_ref": "class.firmware", "object_ref": "obj.firmware.b"},
                ],
                "os": [
                    {
                        "instance": "inst.os.missing",
                        "class_ref": "class.os",
                        "object_ref": "obj.os.embedded",
                    },
                    {
                        "instance": "inst.os.unknown-ref",
                        "class_ref": "class.os",
                        "object_ref": "obj.os.embedded",
                        "embedded_in": "inst.fw.unknown",
                    },
                    {
                        "instance": "inst.os.installable",
                        "class_ref": "class.os",
                        "object_ref": "obj.os.installable",
                        "embedded_in": "inst.fw.a",
                    },
                    {
                        "instance": "inst.os.wrong-class",
                        "class_ref": "class.os",
                        "object_ref": "obj.os.embedded",
                        "embedded_in": "inst.device.1",
                    },
                    {
                        "instance": "inst.os.mismatch",
                        "class_ref": "class.os",
                        "object_ref": "obj.os.embedded",
                        "embedded_in": "inst.fw.b",
                    },
                ],
                "devices": [
                    {
                        "instance": "inst.device.1",
                        "class_ref": "class.router",
                        "object_ref": "obj.device",
                        "firmware_ref": "inst.fw.a",
                        "os_refs": ["inst.os.mismatch"],
                    }
                ],
            }
        },
    )
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "firmware",
                "instance": "inst.fw.a",
                "class_ref": "class.firmware",
                "object_ref": "obj.firmware.a",
            },
            {
                "group": "firmware",
                "instance": "inst.fw.b",
                "class_ref": "class.firmware",
                "object_ref": "obj.firmware.b",
            },
            {
                "group": "os",
                "instance": "inst.os.missing",
                "class_ref": "class.os",
                "object_ref": "obj.os.embedded",
            },
            {
                "group": "os",
                "instance": "inst.os.unknown-ref",
                "class_ref": "class.os",
                "object_ref": "obj.os.embedded",
                "embedded_in": "inst.fw.unknown",
            },
            {
                "group": "os",
                "instance": "inst.os.installable",
                "class_ref": "class.os",
                "object_ref": "obj.os.installable",
                "embedded_in": "inst.fw.a",
            },
            {
                "group": "os",
                "instance": "inst.os.wrong-class",
                "class_ref": "class.os",
                "object_ref": "obj.os.embedded",
                "embedded_in": "inst.device.1",
            },
            {
                "group": "os",
                "instance": "inst.os.mismatch",
                "class_ref": "class.os",
                "object_ref": "obj.os.embedded",
                "embedded_in": "inst.fw.b",
            },
            {
                "group": "devices",
                "instance": "inst.device.1",
                "class_ref": "class.router",
                "object_ref": "obj.device",
                "firmware_ref": "inst.fw.a",
                "os_refs": ["inst.os.mismatch"],
            },
        ],
    )
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED

    codes = [d.code for d in result.diagnostics]
    assert "E3201" in codes
    assert "E2101" in codes
    assert "E2403" in codes

    resolve_diags = [d for d in result.diagnostics if d.code == "E2101"]
    assert resolve_diags
    assert all(d.stage == "resolve" for d in resolve_diags)


def test_embedded_in_validator_reads_rows_via_subscribe():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"validation_owner_embedded_in": "plugin"},
        objects={
            "obj.os.embedded": {
                "object": "obj.os.embedded",
                "class_ref": "class.os",
                "properties": {"installation_model": "embedded"},
            }
        },
        instance_bindings={"instance_bindings": {}},
    )

    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish(
        "normalized_rows",
        [
            {
                "group": "os",
                "instance": "inst.os.subscribed",
                "class_ref": "class.os",
                "object_ref": "obj.os.embedded",
                "embedded_in": None,
                "os_refs": [],
                "firmware_ref": None,
            }
        ],
    )
    ctx._clear_execution_context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E3201" for d in result.diagnostics)
