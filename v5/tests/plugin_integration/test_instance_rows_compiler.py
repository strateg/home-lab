#!/usr/bin/env python3
"""Integration tests for instance rows compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.instance_rows"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_instance_rows_compiler_skips_when_core_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "core"},
        instance_bindings={"instance_bindings": {}},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data == {"normalized_rows": []}


def test_instance_rows_compiler_plugin_owner_normalizes_rows():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_instance_rows": "plugin"},
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "dev-1",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "custom_flag": True,
                        "endpoint_a": {"device_ref": "a", "port": "eth0"},
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    assert not result.has_errors
    rows = result.output_data.get("normalized_rows")
    assert isinstance(rows, list)
    assert rows and rows[0]["instance"] == "dev-1"
    assert rows[0]["extensions"]["custom_flag"] is True
    assert rows[0]["extensions"]["endpoint_a"]["port"] == "eth0"
    assert "normalized_rows" in ctx.get_published_keys(PLUGIN_ID)


def test_sidecar_merge_passthrough_preserves_placeholders():
    """In passthrough mode, placeholders are preserved unchanged."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "passthrough",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "test-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "<TODO_SERIAL_NUMBER>",
                            "mac_eth0": "AA:BB:CC:DD:EE:FF",
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    rows = result.output_data.get("normalized_rows", [])
    assert rows and rows[0]["instance"] == "test-device"
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    # Placeholder should be preserved in passthrough mode
    assert hw_identity.get("serial_number") == "<TODO_SERIAL_NUMBER>"
    assert hw_identity.get("mac_eth0") == "AA:BB:CC:DD:EE:FF"


def test_sidecar_missing_inject_mode_no_error():
    """In inject mode without side-car file, placeholders remain (no error)."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "nonexistent-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "<TODO_SERIAL_NUMBER>",
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    # No error in inject mode when side-car is missing
    assert result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}
    assert not result.has_errors


def test_sidecar_missing_strict_mode_with_placeholders_emits_error():
    """In strict mode without side-car file, unresolved placeholders emit error."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "strict",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "nonexistent-strict-device",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "<TODO_SERIAL_NUMBER>",
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    # Strict mode should emit errors for unresolved placeholders
    error_codes = [d.code for d in result.diagnostics if d.severity == "error"]
    assert "E7210" in error_codes or "E7208" in error_codes


def test_placeholder_non_placeholders_preserved():
    """Non-placeholder values in hardware_identity should never be modified."""
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_instance_rows": "plugin",
            "secrets_mode": "inject",
            "secrets_root": "secrets",
            "repo_root": str(V5_TOOLS.parent.parent),
        },
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "preserve-test",
                        "layer": "L1",
                        "class_ref": "class.router",
                        "object_ref": "obj.router",
                        "hardware_identity": {
                            "serial_number": "<TODO_SERIAL_NUMBER>",
                            "mac_eth0": "AA:BB:CC:DD:EE:FF",  # NOT a placeholder
                            "location": "rack-1",  # NOT a placeholder
                        },
                    }
                ]
            }
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    rows = result.output_data.get("normalized_rows", [])
    hw_identity = rows[0]["extensions"].get("hardware_identity", {})
    # Non-placeholder values must be preserved exactly
    assert hw_identity.get("mac_eth0") == "AA:BB:CC:DD:EE:FF"
    assert hw_identity.get("location") == "rack-1"
