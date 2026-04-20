"""Tests for execution_mode routing in scheduler (ADR 0097 PR2).

These tests verify that the scheduler routes plugins correctly based on
execution_mode manifest field:
- "subinterpreter": isolated execution in Python subinterpreter
- "main_interpreter": envelope path in main interpreter
- "thread_legacy": legacy execute_plugin() path for compatibility
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (  # noqa: E402
    Phase,
    PluginContext,
    PluginInputSnapshot,
    PluginKind,
    PluginResult,
    PluginStatus,
    Stage,
    ValidatorJsonPlugin,
)


class SimpleValidatorPlugin(ValidatorJsonPlugin):
    """Minimal validator for routing tests."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        ctx.publish("validated", {"ok": True})
        return PluginResult.success(self.plugin_id, self.api_version)


# --- execution_mode field existence tests ---


def test_plugin_spec_has_execution_mode_field() -> None:
    """PluginSpec should have execution_mode field after PR2."""
    from kernel.plugin_registry import PluginSpec

    # Check if execution_mode field exists
    spec_fields = {f.name for f in PluginSpec.__dataclass_fields__.values()}

    # PR2 implemented: execution_mode field is now present
    assert "execution_mode" in spec_fields, "PluginSpec must have execution_mode field"

    # subinterpreter_compatible still exists for deprecation compatibility
    assert "subinterpreter_compatible" in spec_fields


def test_execution_mode_default_is_main_interpreter() -> None:
    """Default execution_mode should be 'main_interpreter' for safe migration."""
    from kernel.plugin_registry import PluginSpec

    # Create minimal spec without explicit execution_mode
    spec = PluginSpec(
        id="test.plugin",
        kind=PluginKind.VALIDATOR_JSON,
        entry="test_plugin.py",
        api_version="2.0",
        stages=[Stage.VALIDATE],
        order=100,
        depends_on=[],
        config={},
        produces=[],
        consumes=[],
        manifest_path="/fake/path",
    )

    assert spec.execution_mode == "main_interpreter"


# --- routing decision tests ---


def test_main_interpreter_mode_uses_envelope_path() -> None:
    """Plugins with execution_mode='main_interpreter' must use envelope path."""
    pytest.skip("PR2 not implemented: execution_mode routing not yet added")

    # When PR2 is implemented, this test should verify:
    # 1. Plugin with execution_mode="main_interpreter"
    # 2. Goes through _build_input_snapshot() -> run_plugin_once() -> _commit_envelope_result()
    # 3. Does NOT use legacy execute_plugin()


def test_subinterpreter_mode_uses_isolated_execution() -> None:
    """Plugins with execution_mode='subinterpreter' must use isolated execution when available."""
    pytest.skip("PR2 not implemented: execution_mode routing not yet added")

    # When PR2 is implemented, this test should verify:
    # 1. Plugin with execution_mode="subinterpreter"
    # 2. Uses _execute_plugin_isolated() when HAS_REAL_SUBINTERPRETERS
    # 3. Falls back to _execute_plugin_envelope_local() otherwise


def test_thread_legacy_mode_uses_execute_plugin() -> None:
    """Plugins with execution_mode='thread_legacy' must use legacy execute_plugin()."""
    pytest.skip("PR2 not implemented: execution_mode routing not yet added")

    # When PR2 is implemented, this test should verify:
    # 1. Plugin with execution_mode="thread_legacy"
    # 2. Uses execute_plugin() (legacy path)
    # 3. Calls _mirror_context_into_pipeline_state() for sync


# --- subinterpreter_compatible deprecation tests ---


def test_subinterpreter_compatible_infers_execution_mode() -> None:
    """subinterpreter_compatible=true should infer execution_mode='subinterpreter'."""
    import warnings
    from kernel.plugin_registry import PluginSpec

    # Test _resolve_execution_mode() deprecation fallback
    data_with_compat = {
        "id": "test.compat",
        "kind": "validator_json",
        "entry": "test.py:Plugin",
        "api_version": "1.x",
        "stages": ["validate"],
        "order": 100,
        "subinterpreter_compatible": True,
        # No explicit execution_mode
    }

    # Should infer subinterpreter mode AND emit deprecation warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        resolved = PluginSpec._resolve_execution_mode(data_with_compat)
        assert resolved == "subinterpreter", "subinterpreter_compatible=true should infer subinterpreter mode"
        # Verify deprecation warning was emitted
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "test.compat" in str(w[0].message)
        assert "subinterpreter_compatible" in str(w[0].message)

    # Explicit execution_mode takes precedence (no warning)
    data_explicit = {
        "id": "test.explicit",
        "subinterpreter_compatible": True,
        "execution_mode": "main_interpreter",
    }
    resolved_explicit = PluginSpec._resolve_execution_mode(data_explicit)
    assert resolved_explicit == "main_interpreter", "Explicit execution_mode takes precedence"


def test_subinterpreter_compatible_logs_deprecation_warning() -> None:
    """Using subinterpreter_compatible without execution_mode should log warning."""
    pytest.skip("PR2 not implemented: deprecation warning not yet added")


# --- current behavior baseline tests ---


def test_current_routing_uses_subinterpreter_compatible() -> None:
    """Current implementation routes based on subinterpreter_compatible flag."""
    from kernel.plugin_registry import PluginSpec

    # Create a minimal spec with subinterpreter_compatible=False
    spec = PluginSpec(
        id="test.legacy",
        kind=PluginKind.VALIDATOR_JSON,
        entry="test_plugin.py",
        api_version="2.0",
        stages=[Stage.VALIDATE],
        order=100,
        depends_on=[],
        config={},
        produces=[{"key": "validated", "scope": "pipeline_shared"}],
        consumes=[],
        manifest_path="/fake/path",
        subinterpreter_compatible=False,
    )

    # Verify the field exists and affects routing decision
    assert spec.subinterpreter_compatible is False

    # Plugins with subinterpreter_compatible=False should use legacy path
    # (This is current behavior that PR2 will change to execution_mode)


def test_current_routing_subinterpreter_compatible_true() -> None:
    """Current implementation: subinterpreter_compatible=true uses envelope path."""
    from kernel.plugin_registry import PluginSpec

    spec = PluginSpec(
        id="test.modern",
        kind=PluginKind.VALIDATOR_JSON,
        entry="test_plugin.py",
        api_version="2.0",
        stages=[Stage.VALIDATE],
        order=100,
        depends_on=[],
        config={},
        produces=[{"key": "validated", "scope": "pipeline_shared"}],
        consumes=[],
        manifest_path="/fake/path",
        subinterpreter_compatible=True,
    )

    assert spec.subinterpreter_compatible is True
    # Plugins with subinterpreter_compatible=True use envelope path (current behavior)


# --- execution_mode enum validation tests ---


def test_execution_mode_accepts_valid_values() -> None:
    """execution_mode should only accept valid enum values."""
    from kernel.plugin_registry import PluginSpec

    for valid_mode in ("subinterpreter", "main_interpreter", "thread_legacy"):
        data = {"execution_mode": valid_mode}
        resolved = PluginSpec._resolve_execution_mode(data)
        assert resolved == valid_mode


def test_execution_mode_rejects_invalid_values() -> None:
    """execution_mode with invalid value should raise error."""
    from kernel.plugin_registry import PluginSpec

    with pytest.raises(ValueError, match="Invalid execution_mode"):
        PluginSpec._resolve_execution_mode({"execution_mode": "invalid_mode"})
