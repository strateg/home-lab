#!/usr/bin/env python3
"""Tests for plugin API dataclasses (ADR 0066 - Unit Tests).

Tests cover:
- PluginStatus enum values
- PluginResult factory methods and serialization
- PluginDiagnostic creation and serialization
- PluginContext publish/subscribe
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginDataExchangeError, PluginDiagnostic, PluginResult, PluginStatus
from kernel.plugin_base import Stage


def test_plugin_status_values():
    """Test PluginStatus enum has all required values."""
    assert PluginStatus.SUCCESS.value == "SUCCESS"
    assert PluginStatus.PARTIAL.value == "PARTIAL"
    assert PluginStatus.FAILED.value == "FAILED"
    assert PluginStatus.TIMEOUT.value == "TIMEOUT"
    assert PluginStatus.SKIPPED.value == "SKIPPED"
    print("PASS: PluginStatus values correct")


def test_plugin_result_success():
    """Test PluginResult.success() factory method."""
    result = PluginResult.success("test.plugin", duration_ms=100.0)
    assert result.status == PluginStatus.SUCCESS
    assert result.plugin_id == "test.plugin"
    assert result.duration_ms == 100.0
    assert result.diagnostics == []
    assert not result.has_errors
    assert not result.has_warnings
    print("PASS: PluginResult.success() works")


def test_plugin_result_partial():
    """Test PluginResult.partial() factory method."""
    result = PluginResult.partial("test.plugin")
    assert result.status == PluginStatus.PARTIAL
    print("PASS: PluginResult.partial() works")


def test_plugin_result_failed():
    """Test PluginResult.failed() factory method."""
    result = PluginResult.failed("test.plugin", error_traceback="traceback here")
    assert result.status == PluginStatus.FAILED
    assert result.error_traceback == "traceback here"
    print("PASS: PluginResult.failed() works")


def test_plugin_result_timeout():
    """Test PluginResult.timeout() factory method."""
    result = PluginResult.timeout("test.plugin", duration_ms=30000.0)
    assert result.status == PluginStatus.TIMEOUT
    assert result.duration_ms == 30000.0
    print("PASS: PluginResult.timeout() works")


def test_plugin_result_skipped():
    """Test PluginResult.skipped() factory method."""
    result = PluginResult.skipped("test.plugin", reason="dependency failed")
    assert result.status == PluginStatus.SKIPPED
    assert result.output_data == {"skip_reason": "dependency failed"}
    print("PASS: PluginResult.skipped() works")


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
    print("PASS: PluginResult.to_dict() works")


def test_plugin_diagnostic_to_dict():
    """Test PluginDiagnostic serialization."""
    diag = PluginDiagnostic(
        code="E2101",
        severity="error",
        stage="validate",
        message="Test message",
        path="test:path",
        plugin_id="test.plugin",
        hint="Test hint",
        source_file="test.yaml",
        source_line=10,
        source_column=5,
    )

    d = diag.to_dict()
    assert d["code"] == "E2101"
    assert d["severity"] == "error"
    assert d["message"] == "Test message"
    assert d["hint"] == "Test hint"
    assert d["source"]["file"] == "test.yaml"
    assert d["source"]["line"] == 10
    assert d["source"]["column"] == 5
    print("PASS: PluginDiagnostic.to_dict() works")


def test_plugin_context_publish_subscribe():
    """Test basic publish/subscribe functionality."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Set execution context (simulating registry behavior)
    ctx._set_execution_context("plugin.producer", set())
    ctx.publish("key1", {"data": "value1"})
    ctx.publish("key2", [1, 2, 3])
    ctx._clear_execution_context()

    # Set up consumer plugin with dependency
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})

    data1 = ctx.subscribe("plugin.producer", "key1")
    assert data1 == {"data": "value1"}

    data2 = ctx.subscribe("plugin.producer", "key2")
    assert data2 == [1, 2, 3]

    keys = ctx.get_published_keys("plugin.producer")
    assert set(keys) == {"key1", "key2"}

    ctx._clear_execution_context()
    print("PASS: publish/subscribe works")


def test_plugin_context_dependency_enforcement():
    """Test that subscribe enforces dependency declaration."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    ctx._set_execution_context("plugin.producer", set())
    ctx.publish("data", {"value": 42})
    ctx._clear_execution_context()

    # Consumer WITHOUT dependency should fail
    ctx._set_execution_context("plugin.consumer", set())

    try:
        ctx.subscribe("plugin.producer", "data")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "not in depends_on list" in str(e)

    ctx._clear_execution_context()
    print("PASS: dependency enforcement works")


if __name__ == "__main__":
    print("=" * 60)
    print("ADR 0066 Plugin API Unit Tests")
    print("=" * 60)
    print()

    tests = [
        test_plugin_status_values,
        test_plugin_result_success,
        test_plugin_result_partial,
        test_plugin_result_failed,
        test_plugin_result_timeout,
        test_plugin_result_skipped,
        test_plugin_result_to_dict,
        test_plugin_diagnostic_to_dict,
        test_plugin_context_publish_subscribe,
        test_plugin_context_dependency_enforcement,
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
