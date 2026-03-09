#!/usr/bin/env python3
"""Tests for v5 plugin registry (ADR 0063)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add v5/topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[1] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (
    PluginRegistry,
    PluginManifest,
    PluginSpec,
    PluginKind,
    PluginContext,
    PluginResult,
    ValidatorJsonPlugin,
)
from kernel.plugin_base import Stage


def test_manifest_loading():
    """Test loading plugin manifest from YAML."""
    manifest_path = V5_TOOLS / "plugins" / "plugins.yaml"
    manifest = PluginManifest.from_file(manifest_path)

    assert manifest.schema_version == 1
    assert len(manifest.plugins) >= 1

    ref_plugin = manifest.plugins[0]
    assert ref_plugin.id == "base.validator.references"
    assert ref_plugin.kind == PluginKind.VALIDATOR_JSON
    assert Stage.VALIDATE in ref_plugin.stages
    print("PASS: Manifest loading works")


def test_registry_load():
    """Test registry loading plugins."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    assert len(registry.specs) >= 1
    assert "base.validator.references" in registry.specs
    assert len(registry.get_load_errors()) == 0
    print("PASS: Registry loading works")


def test_execution_order():
    """Test plugin execution order resolution."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    order = registry.get_execution_order(Stage.VALIDATE)
    assert "base.validator.references" in order
    print("PASS: Execution order works")


def test_plugin_instantiation():
    """Test loading and instantiating a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    plugin = registry.load_plugin("base.validator.references")
    assert plugin.plugin_id == "base.validator.references"
    assert plugin.kind == PluginKind.VALIDATOR_JSON
    print("PASS: Plugin instantiation works")


def test_plugin_execution():
    """Test executing a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    plugin = registry.load_plugin("base.validator.references")

    # Create minimal context
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"id": "class.router"}},
        objects={"obj.test": {"id": "obj.test"}},
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "id": "test-device",
                        "class_ref": "class.router",
                        "object_ref": "obj.test",
                    }
                ],
                "l1_software_firmware": [],
                "l1_software_os": [],
                "l4_lxc": [],
            }
        },
    )

    result = plugin.execute(ctx, Stage.VALIDATE)
    assert isinstance(result, PluginResult)
    assert result.success  # No errors with valid refs
    print("PASS: Plugin execution works")


def test_plugin_detects_invalid_ref():
    """Test that plugin detects invalid references."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    plugin = registry.load_plugin("base.validator.references")

    # Create context with invalid class_ref
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},  # Empty - class.router doesn't exist
        objects={},
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "id": "test-device",
                        "class_ref": "class.nonexistent",
                        "object_ref": "obj.nonexistent",
                    }
                ],
                "l1_software_firmware": [],
                "l1_software_os": [],
                "l4_lxc": [],
            }
        },
    )

    result = plugin.execute(ctx, Stage.VALIDATE)
    assert not result.success  # Should fail with invalid refs
    assert len(result.diagnostics) >= 2  # At least class_ref and object_ref errors
    print("PASS: Plugin detects invalid references")


def test_registry_stats():
    """Test registry statistics."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    stats = registry.get_stats()
    assert stats["loaded"] >= 1
    assert "validator_json" in stats["by_kind"]
    print("PASS: Registry stats work")


if __name__ == "__main__":
    print("=" * 60)
    print("ADR 0063 Plugin Registry Tests")
    print("=" * 60)
    print()

    tests = [
        test_manifest_loading,
        test_registry_load,
        test_execution_order,
        test_plugin_instantiation,
        test_plugin_execution,
        test_plugin_detects_invalid_ref,
        test_registry_stats,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
