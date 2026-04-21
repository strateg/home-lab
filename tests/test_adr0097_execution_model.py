"""ADR 0097 Execution Model Tests: Subinterpreter Execution (Python 3.14+ Required).

This test suite validates the subinterpreter-based parallel execution system.
Python 3.14+ is the minimum version - ThreadPoolExecutor fallback removed.

Test coverage:
1. NoOpLock functionality
2. Executor returns InterpreterPoolExecutor
3. Plugin manifest schema parsing
4. Event plane API
5. SerializablePluginSpec serialization
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
    PluginKind,
    Stage,
)
from kernel.plugin_registry import PluginRegistry, PluginSpec, SerializablePluginSpec


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


class TestSerializablePluginSpec:
    """Test SerializablePluginSpec serialization/deserialization (ADR 0097)."""

    def test_roundtrip_serialization(self):
        """Test that PluginSpec survives serialization via SerializablePluginSpec."""
        # Create a realistic PluginSpec
        original_spec = PluginSpec(
            id="test.validator_json.roundtrip",
            kind=PluginKind.VALIDATOR_JSON,
            entry="validators/test_roundtrip.py:TestPlugin",
            api_version="1.x",
            stages=[Stage.VALIDATE],
            order=100,
            phase=Phase.RUN,
            depends_on=["test.compiler.base", "test.compiler.secondary"],
            config={"timeout": 30, "strict_mode": True, "patterns": ["*.yaml", "*.json"]},
            produces=[
                {"topic": "validation_results", "schema_ref": "validation-schema.json"},
                {"topic": "warnings", "schema_ref": "warnings-schema.json"},
            ],
            consumes=[
                {"from_plugin": "test.compiler.base", "topic": "compiled_data"},
            ],
            manifest_path="/path/to/manifest.yaml",
        )

        # Convert to SerializablePluginSpec
        serialized = SerializablePluginSpec.from_plugin_spec(original_spec)

        # Verify serialized fields
        assert serialized.id == original_spec.id
        assert serialized.kind == original_spec.kind.value
        assert serialized.entry == original_spec.entry
        assert serialized.api_version == original_spec.api_version
        assert serialized.depends_on == original_spec.depends_on
        assert serialized.config == original_spec.config
        assert serialized.produces == original_spec.produces
        assert serialized.consumes == original_spec.consumes
        assert serialized.manifest_path == str(original_spec.manifest_path)

        # Convert to dict and back (simulates pickle serialization across interpreters)
        serialized_dict = serialized.to_dict()
        restored = SerializablePluginSpec.from_dict(serialized_dict)

        # Verify round-trip preserves all fields
        assert restored.id == original_spec.id
        assert restored.kind == original_spec.kind.value
        assert restored.entry == original_spec.entry
        assert restored.api_version == original_spec.api_version
        assert restored.depends_on == original_spec.depends_on
        assert restored.config == original_spec.config
        assert restored.produces == original_spec.produces
        assert restored.consumes == original_spec.consumes
        assert restored.manifest_path == str(original_spec.manifest_path)

    def test_minimal_spec_serialization(self):
        """Test serialization with minimal required fields."""
        minimal_spec = PluginSpec(
            id="test.minimal",
            kind=PluginKind.VALIDATOR_JSON,
            entry="validators/minimal.py:MinimalPlugin",
            api_version="1.x",
            stages=[Stage.VALIDATE],
            order=100,
            manifest_path="/manifest.yaml",
        )

        serialized = SerializablePluginSpec.from_plugin_spec(minimal_spec)
        serialized_dict = serialized.to_dict()
        restored = SerializablePluginSpec.from_dict(serialized_dict)

        assert restored.id == minimal_spec.id
        assert restored.kind == minimal_spec.kind.value
        assert restored.depends_on == []
        assert restored.config == {}
        assert restored.produces == []
        assert restored.consumes == []

    def test_config_deep_copy(self):
        """Test that config is deep copied, not referenced."""
        config = {"nested": {"value": 123}, "list": [1, 2, 3]}
        original_spec = PluginSpec(
            id="test.deepcopy",
            kind=PluginKind.VALIDATOR_JSON,
            entry="validators/test.py:Plugin",
            api_version="1.x",
            stages=[Stage.VALIDATE],
            order=100,
            config=config,
            manifest_path="/manifest.yaml",
        )

        serialized = SerializablePluginSpec.from_plugin_spec(original_spec)

        # Modify original config
        config["nested"]["value"] = 999
        config["list"].append(4)

        # Serialized config should be unchanged (deep copy)
        assert serialized.config["nested"]["value"] == 123
        assert serialized.config["list"] == [1, 2, 3]

    def test_depends_on_deep_copy(self):
        """Test that depends_on is deep copied."""
        depends_on = ["plugin.a", "plugin.b"]
        original_spec = PluginSpec(
            id="test.depends",
            kind=PluginKind.VALIDATOR_JSON,
            entry="validators/test.py:Plugin",
            api_version="1.x",
            stages=[Stage.VALIDATE],
            order=100,
            depends_on=depends_on,
            manifest_path="/manifest.yaml",
        )

        serialized = SerializablePluginSpec.from_plugin_spec(original_spec)

        # Modify original list
        depends_on.append("plugin.c")

        # Serialized depends_on should be unchanged
        assert serialized.depends_on == ["plugin.a", "plugin.b"]


class TestEventPlane:
    """Test event plane API (ADR 0097)."""

    def test_emit_and_poll_events(self):
        """Test basic emit/poll_events workflow."""
        ctx = PluginContext(
            topology_path="/test",
            profile="test",
            model_lock={},
        )

        # Set up execution scope for publisher
        publisher_scope = PluginExecutionScope(
            plugin_id="test.publisher",
            allowed_dependencies=frozenset(),
            phase=Phase.RUN,
            config={},
            stage=Stage.VALIDATE,
        )
        token = ctx._set_execution_scope(publisher_scope)

        # Subscribe to topic
        ctx.subscribe_topic("test.events")

        # Emit an event
        ctx.emit("test.events", {"message": "hello"})
        ctx._clear_execution_scope(token)

        # Set up execution scope for subscriber
        subscriber_scope = PluginExecutionScope(
            plugin_id="test.publisher",  # Same plugin in this test
            allowed_dependencies=frozenset(),
            phase=Phase.RUN,
            config={},
            stage=Stage.VALIDATE,
        )
        token = ctx._set_execution_scope(subscriber_scope)

        # Poll events
        events = ctx.poll_events("test.events")

        assert len(events) == 1
        assert events[0].topic == "test.events"
        assert events[0].payload == {"message": "hello"}
        assert events[0].source_plugin == "test.publisher"

        # Second poll should return empty (events consumed)
        events = ctx.poll_events("test.events")
        assert len(events) == 0

        ctx._clear_execution_scope(token)

    def test_subscribe_topic_no_depends_on_required(self):
        """Test that subscribe_topic doesn't require depends_on (loose coupling)."""
        ctx = PluginContext(
            topology_path="/test",
            profile="test",
            model_lock={},
        )

        # Set up scope with empty dependencies
        scope = PluginExecutionScope(
            plugin_id="test.subscriber",
            allowed_dependencies=frozenset(),  # No dependencies
            phase=Phase.RUN,
            config={},
            stage=Stage.VALIDATE,
        )
        token = ctx._set_execution_scope(scope)

        # subscribe_topic should work without depends_on
        ctx.subscribe_topic("any.topic")  # Should not raise

        ctx._clear_execution_scope(token)

    def test_multiple_subscribers(self):
        """Test multiple plugins subscribing to same topic."""
        ctx = PluginContext(
            topology_path="/test",
            profile="test",
            model_lock={},
        )

        # Subscriber A subscribes
        scope_a = PluginExecutionScope(
            plugin_id="test.subscriber_a",
            allowed_dependencies=frozenset(),
            phase=Phase.RUN,
            config={},
            stage=Stage.VALIDATE,
        )
        token = ctx._set_execution_scope(scope_a)
        ctx.subscribe_topic("shared.topic")
        ctx._clear_execution_scope(token)

        # Subscriber B subscribes
        scope_b = PluginExecutionScope(
            plugin_id="test.subscriber_b",
            allowed_dependencies=frozenset(),
            phase=Phase.RUN,
            config={},
            stage=Stage.VALIDATE,
        )
        token = ctx._set_execution_scope(scope_b)
        ctx.subscribe_topic("shared.topic")
        ctx._clear_execution_scope(token)

        # Publisher emits
        publisher_scope = PluginExecutionScope(
            plugin_id="test.publisher",
            allowed_dependencies=frozenset(),
            phase=Phase.RUN,
            config={},
            stage=Stage.VALIDATE,
        )
        token = ctx._set_execution_scope(publisher_scope)
        ctx.emit("shared.topic", {"data": 123})
        ctx._clear_execution_scope(token)

        # Subscriber A polls
        token = ctx._set_execution_scope(scope_a)
        events_a = ctx.poll_events()
        ctx._clear_execution_scope(token)

        # Subscriber B polls
        token = ctx._set_execution_scope(scope_b)
        events_b = ctx.poll_events()
        ctx._clear_execution_scope(token)

        # Both should receive the event
        assert len(events_a) == 1
        assert events_a[0].payload == {"data": 123}
        assert len(events_b) == 1
        assert events_b[0].payload == {"data": 123}

    def test_event_history(self):
        """Test get_event_history for debugging."""
        ctx = PluginContext(
            topology_path="/test",
            profile="test",
            model_lock={},
        )

        scope = PluginExecutionScope(
            plugin_id="test.plugin",
            allowed_dependencies=frozenset(),
            phase=Phase.RUN,
            config={},
            stage=Stage.VALIDATE,
        )
        token = ctx._set_execution_scope(scope)

        ctx.emit("topic.a", {"msg": 1})
        ctx.emit("topic.b", {"msg": 2})
        ctx.emit("topic.a", {"msg": 3})

        ctx._clear_execution_scope(token)

        # Get all history
        all_events = ctx.get_event_history()
        assert len(all_events) == 3

        # Get filtered history
        topic_a_events = ctx.get_event_history("topic.a")
        assert len(topic_a_events) == 2
        assert topic_a_events[0].payload == {"msg": 1}
        assert topic_a_events[1].payload == {"msg": 3}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
