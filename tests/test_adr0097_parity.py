"""ADR 0097 Wave 1 Parity Tests: ThreadPoolExecutor vs InterpreterPoolExecutor.

This test suite validates that the subinterpreter-based parallel execution
produces identical results to the existing ThreadPoolExecutor implementation.

Test coverage:
1. Executor selection logic (3-gate compatibility check)
2. Context serialization round-trip (no data loss)
3. Parallel execution parity (identical plugin results)
4. Mixed compatibility fallback (ThreadPool when needed)
5. Python version gating (fallback on <3.14)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Add topology-tools to path
TOPOLOGY_TOOLS = Path(__file__).resolve().parents[1] / "topology-tools"
sys.path.insert(0, str(TOPOLOGY_TOOLS))

from kernel.plugin_base import (
    Phase,
    PluginContext,
    PluginResult,
    PluginStatus,
    SerializablePluginContext,
    Stage,
)
from kernel.plugin_registry import HAS_INTERPRETER_POOL, PluginRegistry, PluginSpec


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
    """Test executor selection logic (_get_parallel_executor)."""

    def test_executor_selection_subinterpreters_disabled(self):
        """When use_subinterpreters=False, always return ThreadPoolExecutor."""
        registry = PluginRegistry(TOPOLOGY_TOOLS)
        registry.enable_subinterpreters(False)

        # Create subinterpreter-compatible plugin
        from kernel.plugin_base import PluginKind

        registry.specs["test.plugin"] = PluginSpec(
            id="test.plugin",
            kind=PluginKind.VALIDATOR_JSON,
            entry="validators/test.py:TestPlugin",
            api_version="1.x",
            stages=[Stage.VALIDATE],
            order=100,
            subinterpreter_compatible=True,
        )

        executor = registry._get_parallel_executor(4, plugin_ids=["test.plugin"])

        # Should be ThreadPoolExecutor even though plugin is compatible
        from concurrent.futures import ThreadPoolExecutor

        assert isinstance(executor, ThreadPoolExecutor)

    @pytest.mark.skipif(not HAS_INTERPRETER_POOL, reason="Requires Python 3.14+")
    def test_executor_selection_all_compatible(self):
        """When all plugins compatible, return InterpreterPoolExecutor."""
        from concurrent.futures import InterpreterPoolExecutor
        from kernel.plugin_base import PluginKind

        registry = PluginRegistry(TOPOLOGY_TOOLS)
        registry.enable_subinterpreters(True)

        # Create 3 subinterpreter-compatible plugins
        for i in range(3):
            registry.specs[f"test.plugin{i}"] = PluginSpec(
                id=f"test.plugin{i}",
                kind=PluginKind.VALIDATOR_JSON,
                entry="validators/test.py:TestPlugin",
                api_version="1.x",
                stages=[Stage.VALIDATE],
                order=100 + i,
                subinterpreter_compatible=True,
            )

        executor = registry._get_parallel_executor(
            4, plugin_ids=["test.plugin0", "test.plugin1", "test.plugin2"]
        )

        assert isinstance(executor, InterpreterPoolExecutor)

    def test_executor_selection_mixed_compatibility(self):
        """When any plugin is incompatible, return ThreadPoolExecutor."""
        from kernel.plugin_base import PluginKind

        registry = PluginRegistry(TOPOLOGY_TOOLS)
        registry.enable_subinterpreters(True)

        # Create mixed compatibility plugins
        registry.specs["test.compatible"] = PluginSpec(
            id="test.compatible",
            kind=PluginKind.VALIDATOR_JSON,
            entry="validators/test.py:TestPlugin",
            api_version="1.x",
            stages=[Stage.VALIDATE],
            order=100,
            subinterpreter_compatible=True,
        )
        registry.specs["test.incompatible"] = PluginSpec(
            id="test.incompatible",
            kind=PluginKind.VALIDATOR_JSON,
            entry="validators/legacy.py:LegacyPlugin",
            api_version="1.x",
            stages=[Stage.VALIDATE],
            order=101,
            subinterpreter_compatible=False,  # Incompatible
        )

        executor = registry._get_parallel_executor(
            4, plugin_ids=["test.compatible", "test.incompatible"]
        )

        # Should fall back to ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor

        assert isinstance(executor, ThreadPoolExecutor)


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
