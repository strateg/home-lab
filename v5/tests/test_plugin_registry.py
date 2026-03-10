#!/usr/bin/env python3
"""Tests for v5 plugin registry (ADR 0063).

Tests cover:
- Manifest loading
- Plugin instantiation
- Execution order resolution
- Plugin execution with timeout
- Config validation
- Error handling with traceback
- Kernel info
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add v5/topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[1] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (
    KERNEL_API_VERSION,
    KERNEL_VERSION,
    PluginContext,
    PluginDataExchangeError,
    PluginKind,
    PluginManifest,
    PluginRegistry,
    PluginResult,
    PluginSpec,
    PluginStatus,
    ValidatorJsonPlugin,
)
from kernel.plugin_base import PluginDiagnostic, Stage


def test_manifest_loading():
    """Test loading plugin manifest from YAML."""
    manifest_path = V5_TOOLS / "plugins" / "plugins.yaml"
    manifest = PluginManifest.from_file(manifest_path)

    assert manifest.schema_version == 1
    assert len(manifest.plugins) >= 1

    # First plugin is now the compiler plugin
    compiler_plugin = manifest.plugins[0]
    assert compiler_plugin.id == "base.compiler.capabilities"
    assert compiler_plugin.kind == PluginKind.COMPILER
    assert Stage.COMPILE in compiler_plugin.stages
    assert compiler_plugin.timeout == 30

    # Find the reference validator plugin
    ref_plugin = next(p for p in manifest.plugins if p.id == "base.validator.references")
    assert ref_plugin.kind == PluginKind.VALIDATOR_JSON
    assert Stage.VALIDATE in ref_plugin.stages
    assert ref_plugin.config == {"strict_mode": False}
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
    assert plugin.api_version == "1.x"
    print("PASS: Plugin instantiation works")


def test_plugin_execution():
    """Test executing a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    # Create minimal context
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
                "l1_software_firmware": [],
                "l1_software_os": [],
                "l4_lxc": [],
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
                        "instance": "test-device",
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

    result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert len(result.diagnostics) >= 1
    assert result.has_errors
    print("PASS: Plugin detects invalid references")


def test_plugin_result_statuses():
    """Test PluginResult factory methods."""
    # Test success
    result = PluginResult.success("test.plugin", duration_ms=100.0)
    assert result.status == PluginStatus.SUCCESS
    assert result.duration_ms == 100.0

    # Test partial (warnings)
    result = PluginResult.partial("test.plugin")
    assert result.status == PluginStatus.PARTIAL

    # Test failed
    result = PluginResult.failed("test.plugin", error_traceback="traceback here")
    assert result.status == PluginStatus.FAILED
    assert result.error_traceback == "traceback here"

    # Test timeout
    result = PluginResult.timeout("test.plugin", duration_ms=30000.0)
    assert result.status == PluginStatus.TIMEOUT

    # Test skipped
    result = PluginResult.skipped("test.plugin", reason="dependency failed")
    assert result.status == PluginStatus.SKIPPED
    assert result.output_data == {"skip_reason": "dependency failed"}

    print("PASS: PluginResult statuses work")


def test_plugin_result_to_dict():
    """Test PluginResult serialization."""
    diag = PluginDiagnostic(
        code="E2101",
        severity="error",
        stage="validate",
        message="Test error",
        path="test:path",
        plugin_id="test.plugin",
    )
    result = PluginResult(
        plugin_id="test.plugin",
        api_version="1.x",
        status=PluginStatus.FAILED,
        duration_ms=50.0,
        diagnostics=[diag],
        error_traceback="test traceback",
    )

    d = result.to_dict()
    assert d["plugin_id"] == "test.plugin"
    assert d["api_version"] == "1.x"
    assert d["status"] == "FAILED"
    assert d["duration_ms"] == 50.0
    assert len(d["diagnostics"]) == 1
    assert d["error_traceback"] == "test traceback"
    print("PASS: PluginResult serialization works")


def test_registry_stats():
    """Test registry statistics."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    stats = registry.get_stats()
    assert stats["loaded"] >= 1
    assert "validator_json" in stats["by_kind"]
    print("PASS: Registry stats work")


def test_kernel_info():
    """Test kernel info retrieval."""
    info = PluginRegistry.get_kernel_info()
    assert info["version"] == KERNEL_VERSION
    assert info["plugin_api_version"] == KERNEL_API_VERSION
    assert "1.x" in info["supported_api_versions"]
    assert info["default_timeout"] == 30.0
    print("PASS: Kernel info works")


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


def test_execute_stage():
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


def test_timeout_does_not_block_pipeline():
    """Timeout should return promptly instead of waiting for plugin completion."""
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

    plugin = registry.load_plugin("base.validator.references")
    original_execute = plugin.execute

    def slow_execute(ctx: PluginContext, stage: Stage) -> PluginResult:
        time.sleep(2.0)
        return original_execute(ctx, stage)

    plugin.execute = slow_execute  # type: ignore[assignment]
    try:
        start = time.perf_counter()
        result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE, timeout=0.1)
        elapsed = time.perf_counter() - start
    finally:
        plugin.execute = original_execute  # type: ignore[assignment]

    assert result.status == PluginStatus.TIMEOUT
    assert elapsed < 1.0
    print("PASS: Timeout returns promptly")


def test_runtime_config_takes_precedence():
    """Runtime ctx.config values should override plugin defaults."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={"obj.test": {"object": "obj.test"}},
        instance_bindings={
            "instance_bindings": {
                "l1_devices": [
                    {
                        "instance": "test-device",
                        "class_ref": "class.router",
                        "object_ref": "obj.test",
                    }
                ]
            }
        },
        config={"strict_mode": True},
    )

    result = registry.execute_plugin("base.validator.model_lock", ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E3201" for d in result.diagnostics)
    assert ctx.config == {"strict_mode": True}
    print("PASS: Runtime config precedence works")


def test_publish_subscribe_basic():
    """Test basic publish/subscribe functionality."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Set execution context (simulating registry behavior)
    ctx._set_execution_context("plugin.producer", set())

    # Publish data
    ctx.publish("key1", {"data": "value1"})
    ctx.publish("key2", [1, 2, 3])

    ctx._clear_execution_context()

    # Set up consumer plugin with dependency
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})

    # Subscribe to data
    data1 = ctx.subscribe("plugin.producer", "key1")
    assert data1 == {"data": "value1"}

    data2 = ctx.subscribe("plugin.producer", "key2")
    assert data2 == [1, 2, 3]

    # Get published keys
    keys = ctx.get_published_keys("plugin.producer")
    assert set(keys) == {"key1", "key2"}

    ctx._clear_execution_context()
    print("PASS: Basic publish/subscribe works")


def test_publish_subscribe_dependency_check():
    """Test that subscribe enforces dependency declaration."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Producer publishes data
    ctx._set_execution_context("plugin.producer", set())
    ctx.publish("data", {"value": 42})
    ctx._clear_execution_context()

    # Consumer WITHOUT dependency should fail
    ctx._set_execution_context("plugin.consumer", set())  # Empty depends_on

    try:
        ctx.subscribe("plugin.producer", "data")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "not in depends_on list" in str(e)

    ctx._clear_execution_context()
    print("PASS: Subscribe dependency check works")


def test_publish_subscribe_missing_data():
    """Test subscribe error handling for missing data."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Consumer with valid dependency but producer hasn't published
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})

    try:
        ctx.subscribe("plugin.producer", "nonexistent")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "has not published any data" in str(e)

    ctx._clear_execution_context()

    # Producer publishes some data
    ctx._set_execution_context("plugin.producer", set())
    ctx.publish("existing_key", "value")
    ctx._clear_execution_context()

    # Consumer tries to get missing key
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})

    try:
        ctx.subscribe("plugin.producer", "nonexistent_key")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "has not published key" in str(e)

    ctx._clear_execution_context()
    print("PASS: Subscribe missing data error handling works")


def test_publish_without_context():
    """Test that publish fails without execution context."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # No execution context set
    try:
        ctx.publish("key", "value")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "no current plugin context" in str(e)

    print("PASS: Publish without context error works")


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
        test_plugin_result_statuses,
        test_plugin_result_to_dict,
        test_registry_stats,
        test_kernel_info,
        test_config_injection,
        test_execute_stage,
        test_timeout_does_not_block_pipeline,
        test_runtime_config_takes_precedence,
        # ADR 0065 inter-plugin data exchange tests
        test_publish_subscribe_basic,
        test_publish_subscribe_dependency_check,
        test_publish_subscribe_missing_data,
        test_publish_without_context,
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
