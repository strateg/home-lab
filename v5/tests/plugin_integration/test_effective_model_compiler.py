#!/usr/bin/env python3
"""Integration tests for ADR0069 effective model compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.effective_model"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_effective_model_compiler_publishes_candidate():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={
            "class.router": {
                "class": "class.router",
                "version": "1.0.0",
                "required_capabilities": ["cap.net.interface.ethernet"],
            }
        },
        objects={
            "obj.router.test": {
                "object": "obj.router.test",
                "version": "1.0.0",
                "class_ref": "class.router",
                "enabled_capabilities": ["cap.net.interface.ethernet"],
            }
        },
        config={
            "normalized_rows": [
                {
                    "group": "l1_devices",
                    "instance": "rtr-1",
                    "layer": "L1",
                    "source_id": "rtr-1",
                    "class_ref": "class.router",
                    "object_ref": "obj.router.test",
                    "status": "modeled",
                    "notes": "",
                    "runtime": None,
                    "firmware_ref": None,
                    "os_refs": [],
                    "embedded_in": None,
                    "extensions": {
                        "length_m": 3,
                        "endpoint_a": {"device_ref": "left", "port": "eth0"},
                    },
                }
            ]
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "rtr-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router.test",
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors
    keys = ctx.get_published_keys(PLUGIN_ID)
    assert "effective_model_candidate" in keys
    assert isinstance(ctx.compiled_json, dict)
    assert "instances" in ctx.compiled_json
    assert "l1_devices" in ctx.compiled_json["instances"]
    first_row = ctx.compiled_json["instances"]["l1_devices"][0]
    assert first_row["instance_id"] == "rtr-1"
    assert first_row["instance_data"]["length_m"] == 3
    assert first_row["instance_data"]["endpoint_a"]["port"] == "eth0"
    assert ctx.compiled_json["compiled_model_version"] == "1.0"
    assert isinstance(ctx.compiled_json.get("compiled_at"), str)
    assert isinstance(ctx.compiled_json.get("compiler_pipeline_version"), str)
    assert isinstance(ctx.compiled_json.get("source_manifest_digest"), str)


def test_effective_model_compiler_reads_normalized_rows_by_key_not_plugin_id():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={"class.router": {"class": "class.router", "version": "1.0.0"}},
        objects={
            "obj.router.test": {
                "object": "obj.router.test",
                "version": "1.0.0",
                "class_ref": "class.router",
            }
        },
        config={},
        plugin_outputs={
            "custom.instance_rows_provider": {
                "normalized_rows": [
                    {
                        "group": "l1_devices",
                        "instance": "rtr-from-plugin-output",
                        "layer": "L1",
                        "source_id": "rtr-from-plugin-output",
                        "class_ref": "class.router",
                        "object_ref": "obj.router.test",
                        "status": "modeled",
                        "notes": "",
                        "runtime": None,
                        "firmware_ref": None,
                        "os_refs": [],
                        "embedded_in": None,
                        "extensions": {"category": "cat5e"},
                    }
                ]
            }
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "rtr-from-raw-bindings",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router.test",
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors
    rows = ctx.compiled_json["instances"]["l1_devices"]
    assert [row["instance_id"] for row in rows] == ["rtr-from-plugin-output"]
    assert rows[0]["instance_data"]["category"] == "cat5e"


def test_effective_model_compiler_reports_ambiguous_normalized_rows_output():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={"class.router": {"class": "class.router", "version": "1.0.0"}},
        objects={
            "obj.router.test": {
                "object": "obj.router.test",
                "version": "1.0.0",
                "class_ref": "class.router",
            }
        },
        config={},
        plugin_outputs={
            "plugin.a": {"normalized_rows": [{"instance": "a"}]},
            "plugin.b": {"normalized_rows": [{"instance": "b"}]},
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "rtr-fallback",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router.test",
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.FAILED
    assert result.has_errors
    assert any(diag.code == "E6901" for diag in result.diagnostics)
