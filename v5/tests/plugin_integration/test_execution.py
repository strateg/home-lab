#!/usr/bin/env python3
"""Tests for plugin execution flow (ADR 0066 - Integration Tests).

Tests cover:
- Execution order determinism
- Dependency resolution
- Stage execution
- Diagnostics aggregation
- Inter-plugin communication
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add v5/topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginResult, PluginStatus
from kernel.plugin_base import Stage


def test_execution_order():
    """Test plugin execution order resolution."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    order = registry.get_execution_order(Stage.VALIDATE)
    assert "base.validator.references" in order

    # Check depends_on ordering
    refs_idx = order.index("base.validator.references")
    if "base.validator.model_lock" in order:
        lock_idx = order.index("base.validator.model_lock")
        assert refs_idx < lock_idx, "references should run before model_lock"
    print("PASS: Execution order works")


def test_plugin_execution():
    """Test executing a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router", "firmware_policy": "allowed", "os_policy": "allowed"}},
        objects={"obj.test": {"object": "obj.test", "class_ref": "class.router"}},
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "test-device",
                        "class_ref": "class.router",
                        "object_ref": "obj.test",
                    }
                ],
            }
        },
    )

    result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert isinstance(result, PluginResult)
    assert result.status == PluginStatus.SUCCESS
    assert result.plugin_id == "base.validator.references"
    assert result.duration_ms > 0
    print("PASS: Plugin execution works")


def test_plugin_detects_invalid_ref():
    """Test that plugin detects invalid references."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

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
                        "instance": "test-device",
                        "class_ref": "class.nonexistent",
                        "object_ref": "obj.nonexistent",
                    }
                ],
            }
        },
    )

    result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert len(result.diagnostics) >= 1
    assert result.has_errors
    print("PASS: Plugin detects invalid references")


def test_stage_execution():
    """Test executing all plugins for a stage."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) >= 1
    assert all(isinstance(r, PluginResult) for r in results)
    print("PASS: Stage execution works")


def test_config_injection():
    """Test runtime config is restored after plugin execution."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"runtime_flag": True},
    )

    registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert ctx.config == {"runtime_flag": True}
    print("PASS: Runtime config restore works")


def test_registry_stats():
    """Test registry statistics."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    stats = registry.get_stats()
    assert stats["loaded"] >= 1
    assert "validator_json" in stats["by_kind"] or "compiler" in stats["by_kind"]
    print("PASS: Registry stats work")


def test_inter_plugin_communication():
    """Test publish/subscribe between plugins across stages."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={"obj.test": {"vendor": "test-vendor"}},
        instance_bindings={"instance_bindings": {}},
    )

    # Execute compile stage
    compile_results = registry.execute_stage(Stage.COMPILE, ctx)

    # Check compiler published data
    if "base.compiler.capabilities" in registry.specs:
        keys = ctx.get_published_keys("base.compiler.capabilities")
        assert "derived_capabilities" in keys
        assert "capability_stats" in keys
        print("PASS: Inter-plugin communication works")
    else:
        print("SKIP: Compiler plugin not loaded")


if __name__ == "__main__":
    print("=" * 60)
    print("ADR 0066 Plugin Integration Tests")
    print("=" * 60)
    print()

    tests = [
        test_execution_order,
        test_plugin_execution,
        test_plugin_detects_invalid_ref,
        test_stage_execution,
        test_config_injection,
        test_registry_stats,
        test_inter_plugin_communication,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            import traceback

            print(f"FAIL: {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
