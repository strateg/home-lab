"""ADR 0097 Wave 5 Tests: Subinterpreter Execution (Python 3.14+ Required).

This test suite validates the subinterpreter-based parallel execution system.
Python 3.14+ is the minimum version - ThreadPoolExecutor fallback removed.

Test coverage:
1. Context serialization round-trip (no data loss)
2. NoOpLock functionality
3. Executor returns InterpreterPoolExecutor
4. Plugin manifest schema parsing
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Skip entire module if Python < 3.14 (InterpreterPoolExecutor not available)
pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="ADR 0097 requires Python 3.14+ for InterpreterPoolExecutor",
)

# Conditional import - only available in Python 3.14+
if sys.version_info >= (3, 14):
    from concurrent.futures import InterpreterPoolExecutor
else:
    InterpreterPoolExecutor = None  # type: ignore[misc,assignment]

# Add topology-tools to path
TOPOLOGY_TOOLS = Path(__file__).resolve().parents[1] / "topology-tools"
sys.path.insert(0, str(TOPOLOGY_TOOLS))

from kernel.plugin_base import (
    NoOpLock,
    Phase,
    PluginContext,
    PluginExecutionScope,
    SerializablePluginContext,
    Stage,
)
from kernel.plugin_registry import PluginRegistry, PluginSpec


class TestSerializablePluginContext:
    """Test SerializablePluginContext serialization/deserialization."""

    def test_roundtrip_serialization(self):
        """Test that context survives serialization round-trip without data loss."""
        # Create a realistic PluginContext
        original_ctx = PluginContext(
            topology_path="/path/to/topology.yaml",
            profile="production",
            model_lock={"core_model_version": "0062-1.0", "framework_version": "0.5.0"},
            compiled_json={
                "instances": {"example": {"@class": "host", "hostname": "test"}},
                "metadata": {"version": "1.0"},
            },
            config={
                "parallel_execution": True,
                "timeout": 30,
                "custom_flag": "value",
            },
            output_dir="/path/to/output",
            capability_catalog={"cap1": {"provider": "plugin1"}},
            changed_input_scopes=["topology", "instances"],
        )

        # Serialize
        serialized = SerializablePluginContext.from_plugin_context(original_ctx)

        # Verify serialized fields
        assert serialized.topology_path == original_ctx.topology_path
        assert serialized.profile == original_ctx.profile
        assert serialized.model_lock == original_ctx.model_lock
        assert serialized.output_dir == original_ctx.output_dir
        assert serialized.capability_catalog == original_ctx.capability_catalog
        assert serialized.changed_input_scopes == original_ctx.changed_input_scopes
        assert isinstance(serialized.compiled_json_bytes, bytes)
        assert isinstance(serialized.plugin_config_bytes, bytes)

        # Deserialize
        restored_ctx = serialized.to_plugin_context()

        # Verify all data preserved
        assert restored_ctx.topology_path == original_ctx.topology_path
        assert restored_ctx.profile == original_ctx.profile
        assert restored_ctx.model_lock == original_ctx.model_lock
        assert restored_ctx.compiled_json == original_ctx.compiled_json
        assert restored_ctx.config == original_ctx.config
        assert restored_ctx.output_dir == original_ctx.output_dir
        assert restored_ctx.capability_catalog == original_ctx.capability_catalog
        assert restored_ctx.changed_input_scopes == original_ctx.changed_input_scopes

    def test_serialization_with_minimal_context(self):
        """Test serialization with minimal required fields."""
        ctx = PluginContext(
            topology_path="/topology.yaml",
            profile="test-real",
            model_lock={},
        )

        serialized = SerializablePluginContext.from_plugin_context(ctx)
        restored = serialized.to_plugin_context()

        assert restored.topology_path == ctx.topology_path
        assert restored.profile == ctx.profile
        assert restored.model_lock == ctx.model_lock
        assert restored.compiled_json == {}
        assert restored.output_dir == ""


class TestExecutorSelection:
    """Test executor selection (_get_parallel_executor)."""

    def test_executor_returns_interpreter_pool(self):
        """Verify _get_parallel_executor returns InterpreterPoolExecutor."""
        registry = PluginRegistry(TOPOLOGY_TOOLS)
        executor = registry._get_parallel_executor(4)
        assert isinstance(executor, InterpreterPoolExecutor)


class TestPluginManifestSchema:
    """Test that subinterpreter_compatible field is properly parsed."""

    def test_manifest_parsing_compatible_true(self):
        """Test parsing manifest with subinterpreter_compatible: true."""
        manifest_data = {
            "id": "test.plugin.compatible",
            "kind": "validator_json",
            "entry": "validators/test.py:TestPlugin",
            "api_version": "1.x",
            "stages": ["validate"],
            "order": 100,
            "subinterpreter_compatible": True,
        }

        spec = PluginSpec.from_dict(manifest_data, "/path/to/manifest.yaml")

        assert spec.subinterpreter_compatible is True

    def test_manifest_parsing_default_value(self):
        """Test that subinterpreter_compatible defaults to False when omitted."""
        manifest_data = {
            "id": "test.plugin.default",
            "kind": "validator_json",
            "entry": "validators/test.py:TestPlugin",
            "api_version": "1.x",
            "stages": ["validate"],
            "order": 100,
            # subinterpreter_compatible omitted
        }

        spec = PluginSpec.from_dict(manifest_data, "/path/to/manifest.yaml")

        # Default should be False for backward compatibility
        assert spec.subinterpreter_compatible is False


class TestNoOpLock:
    """Test NoOpLock functionality (ADR 0097 Wave 5)."""

    def test_nooplock_context_manager(self):
        """Test NoOpLock works as a context manager."""
        lock = NoOpLock()
        with lock:
            # Should not block or raise
            pass
        # Should complete without issues

    def test_nooplock_acquire_release(self):
        """Test NoOpLock acquire/release methods."""
        lock = NoOpLock()
        result = lock.acquire()
        assert result is True
        lock.release()  # Should not raise

    def test_context_uses_nooplock(self):
        """Test that PluginContext uses NoOpLock (Python 3.14+ always uses subinterpreters)."""
        ctx = PluginContext(
            topology_path="/test",
            profile="test",
            model_lock={},
        )
        assert isinstance(ctx._published_data_lock, NoOpLock)

    def test_deserialized_context_uses_nooplock(self):
        """Test that deserialized context uses NoOpLock."""
        original_ctx = PluginContext(
            topology_path="/test",
            profile="test",
            model_lock={},
            compiled_json={"test": "data"},
        )

        # Serialize and deserialize
        serialized = SerializablePluginContext.from_plugin_context(original_ctx)
        restored = serialized.to_plugin_context()

        # Deserialized context should use NoOpLock
        assert isinstance(restored._published_data_lock, NoOpLock)

    def test_publish_works_with_nooplock(self):
        """Test that publish() works with NoOpLock."""
        ctx = PluginContext(
            topology_path="/test",
            profile="test",
            model_lock={},
        )

        # Set execution scope for publish to work
        scope = PluginExecutionScope(
            plugin_id="test.plugin",
            allowed_dependencies=frozenset(),
            phase=Phase.RUN,
            config={},
            stage=Stage.VALIDATE,
        )
        token = ctx._set_execution_scope(scope)

        try:
            # publish() should work with NoOpLock
            ctx.publish("test_key", {"value": 123})

            # Verify data was published
            assert "test.plugin" in ctx._published_data
            assert ctx._published_data["test.plugin"]["test_key"] == {"value": 123}
        finally:
            ctx._clear_execution_scope(token)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
