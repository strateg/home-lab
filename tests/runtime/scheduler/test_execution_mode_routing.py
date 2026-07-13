"""Tests for execution_mode routing in scheduler (ADR 0097 PR2).

These tests verify that the scheduler routes plugins correctly based on
execution_mode manifest field:
- "subinterpreter": isolated execution in Python subinterpreter
- "main_interpreter": envelope path in main interpreter
- "thread_legacy": legacy execute_plugin() path for compatibility
"""

from __future__ import annotations

import concurrent.futures
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (  # noqa: E402
    Phase,
    PluginContext,
    PluginExecutionEnvelope,
    PluginInputSnapshot,
    PluginKind,
    PluginResult,
    PluginStatus,
    Stage,
    ValidatorJsonPlugin,
)
from kernel.plugin_registry import PluginRegistry, PluginSpec  # noqa: E402
from kernel.scheduler import phase_executor  # noqa: E402


class SimpleValidatorPlugin(ValidatorJsonPlugin):
    """Minimal validator for routing tests."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        ctx.publish("validated", {"ok": True})
        return PluginResult.success(self.plugin_id, self.api_version)


def _make_spec(plugin_id: str, *, execution_mode: str = "main_interpreter") -> PluginSpec:
    return PluginSpec(
        id=plugin_id,
        kind=PluginKind.VALIDATOR_JSON,
        entry="validators/references_validator.py:ReferencesValidator",
        api_version="2.0",
        stages=[Stage.VALIDATE],
        order=100,
        phase=Phase.RUN,
        depends_on=[],
        config={},
        produces=[{"key": "validated", "scope": "pipeline_shared"}],
        consumes=[],
        manifest_path="tests/runtime/scheduler",
        execution_mode=execution_mode,
    )


def _make_snapshot(plugin_id: str) -> PluginInputSnapshot:
    return PluginInputSnapshot(
        plugin_id=plugin_id,
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={},
        allowed_dependencies=frozenset(),
        produced_key_scopes={"validated": "pipeline_shared"},
    )


def _success_envelope(plugin_id: str) -> PluginExecutionEnvelope:
    return PluginExecutionEnvelope(
        result=PluginResult(
            plugin_id=plugin_id,
            api_version="2.0",
            status=PluginStatus.SUCCESS,
            diagnostics=[],
        )
    )


# --- execution_mode field existence tests ---


def test_plugin_spec_has_execution_mode_field() -> None:
    """PluginSpec should have execution_mode field after PR2."""
    from kernel.plugin_registry import PluginSpec

    # Check if execution_mode field exists
    spec_fields = {f.name for f in PluginSpec.__dataclass_fields__.values()}

    # PR2 implemented: execution_mode field is now present
    assert "execution_mode" in spec_fields, "PluginSpec must have execution_mode field"


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
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.main"
    spec = _make_spec(plugin_id, execution_mode="main_interpreter")
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})
    snapshot = _make_snapshot(plugin_id)

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_build_input_snapshot", return_value=snapshot),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(
            registry, "_execute_plugin_envelope_local", return_value=_success_envelope(plugin_id)
        ) as execute_local,
        patch.object(
            registry, "_commit_envelope_result", return_value=PluginResult.success(plugin_id, "2.0")
        ) as commit,
        patch.object(registry, "execute_plugin", return_value=PluginResult.success(plugin_id, "2.0")) as execute_legacy,
        patch.object(registry, "_mirror_context_into_pipeline_state") as mirror,
    ):
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=True,
            isolated_worker=MagicMock(),
        )

    assert len(results) == 1
    execute_local.assert_called_once()
    commit.assert_called_once()
    execute_legacy.assert_not_called()
    mirror.assert_not_called()


def test_subinterpreter_mode_uses_isolated_execution() -> None:
    """Plugins with execution_mode='subinterpreter' must use isolated execution when available."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.sub"
    spec = _make_spec(plugin_id, execution_mode="subinterpreter")
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})
    snapshot = _make_snapshot(plugin_id)

    def _isolated(snapshot_dict, _base_path_str, _serialized_spec_dict):
        return _success_envelope(snapshot_dict["plugin_id"])

    execute_isolated = MagicMock(side_effect=_isolated)

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_build_input_snapshot", return_value=snapshot),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(registry, "_execute_plugin_envelope_local") as execute_local,
        patch.object(registry, "_commit_envelope_result", return_value=PluginResult.success(plugin_id, "2.0")),
    ):
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=True,
            isolated_worker=execute_isolated,
        )

    assert len(results) == 1
    execute_isolated.assert_called_once()
    execute_local.assert_not_called()


def test_subinterpreter_mode_falls_back_to_local_envelope_without_real_subinterpreters() -> None:
    """subinterpreter mode should use local envelope runner when real subinterpreters are unavailable."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.sub.fallback"
    spec = _make_spec(plugin_id, execution_mode="subinterpreter")
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})
    snapshot = _make_snapshot(plugin_id)

    execute_isolated = MagicMock()

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_build_input_snapshot", return_value=snapshot),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(
            registry, "_execute_plugin_envelope_local", return_value=_success_envelope(plugin_id)
        ) as execute_local,
        patch.object(registry, "_commit_envelope_result", return_value=PluginResult.success(plugin_id, "2.0")),
    ):
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=False,
            isolated_worker=execute_isolated,
        )

    assert len(results) == 1
    execute_isolated.assert_not_called()
    execute_local.assert_called_once()


def test_thread_legacy_mode_uses_execute_plugin() -> None:
    """Plugins with execution_mode='thread_legacy' must use legacy execute_plugin()."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.thread_legacy"
    spec = _make_spec(plugin_id, execution_mode="thread_legacy")
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "execute_plugin", return_value=PluginResult.success(plugin_id, "2.0")) as execute_legacy,
        patch.object(registry, "_mirror_context_into_pipeline_state") as mirror,
        patch.object(registry, "_build_input_snapshot") as build_snapshot,
    ):
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=True,
            isolated_worker=MagicMock(),
        )

    assert len(results) == 1
    execute_legacy.assert_called_once()
    mirror.assert_called_once()
    build_snapshot.assert_not_called()


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
