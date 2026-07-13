#!/usr/bin/env python3
"""PluginResult datatype tests (kernel/plugin_base).

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginResult, PluginStatus  # noqa: E402
from kernel.plugin_base import PluginDiagnostic  # noqa: E402


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
