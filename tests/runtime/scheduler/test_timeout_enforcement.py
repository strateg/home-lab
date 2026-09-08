"""Tests for F02/R09 timeout enforcement in scheduler.

These tests verify that:
1. Individual plugin deadlines are enforced from submission time
2. Results arriving after deadline are rejected with TIMEOUT status
3. Bounded shutdown prevents infinite hangs
4. PluginStatus.TIMEOUT is used (not FAILED) for timeout scenarios
"""

from __future__ import annotations

import concurrent.futures
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (  # noqa: E402
    Phase,
    PluginContext,
    PluginDiagnostic,
    PluginExecutionEnvelope,
    PluginInputSnapshot,
    PluginKind,
    PluginResult,
    PluginStatus,
    PublishedMessage,
    Stage,
)
from kernel.plugin_registry import PluginRegistry, PluginSpec  # noqa: E402
from kernel.scheduler import phase_executor  # noqa: E402


def _make_spec(
    plugin_id: str,
    *,
    execution_mode: str = "subinterpreter",
    timeout: float = 1.0,
) -> PluginSpec:
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
        produces=[{"key": "output", "scope": "pipeline_shared"}],
        consumes=[],
        manifest_path="tests/runtime/scheduler",
        execution_mode=execution_mode,
        timeout=timeout,
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
        produced_key_scopes={"output": "pipeline_shared"},
    )


def _success_envelope(plugin_id: str) -> PluginExecutionEnvelope:
    return PluginExecutionEnvelope(
        result=PluginResult(
            plugin_id=plugin_id,
            api_version="2.0",
            status=PluginStatus.SUCCESS,
            diagnostics=[],
        ),
        published_messages=[
            PublishedMessage(
                plugin_id=plugin_id,
                key="output",
                value={"ok": True},
                scope="pipeline_shared",
                stage=Stage.VALIDATE,
                phase=Phase.RUN,
            )
        ],
    )


# --- Deadline enforcement tests ---


def test_deadline_exceeded_returns_timeout_status() -> None:
    """Plugin that exceeds individual deadline must return TIMEOUT status (not FAILED)."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.slow"
    spec = _make_spec(plugin_id, timeout=0.5)  # 0.5s timeout
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})

    def _slow_isolated(snapshot_dict, _base_path_str, _serialized_spec_dict):
        # Simulate slow plugin that takes 1.0s (exceeds 0.5s timeout)
        time.sleep(1.0)
        return _success_envelope(snapshot_dict["plugin_id"])

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_build_input_snapshot", return_value=_make_snapshot(plugin_id)),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(registry, "_commit_envelope_result", return_value=PluginResult.success(plugin_id, "2.0")),
    ):
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=True,
            isolated_worker=_slow_isolated,
        )

    assert len(results) == 1
    result = results[0]
    # F02/R09: Must use TIMEOUT status, not FAILED
    assert result.status == PluginStatus.TIMEOUT, f"Expected TIMEOUT, got {result.status}"
    # Must have E4103 diagnostic
    assert any(d.code == "E4103" for d in result.diagnostics)


def test_fast_plugin_returns_success() -> None:
    """Plugin that completes within deadline should return SUCCESS."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.fast"
    spec = _make_spec(plugin_id, timeout=2.0)  # 2.0s timeout
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})

    def _fast_isolated(snapshot_dict, _base_path_str, _serialized_spec_dict):
        # Fast plugin that completes in 0.1s (within 2.0s timeout)
        time.sleep(0.1)
        return _success_envelope(snapshot_dict["plugin_id"])

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_build_input_snapshot", return_value=_make_snapshot(plugin_id)),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(
            registry, "_commit_envelope_result", return_value=PluginResult.success(plugin_id, "2.0")
        ),
    ):
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=True,
            isolated_worker=_fast_isolated,
        )

    assert len(results) == 1
    result = results[0]
    assert result.status == PluginStatus.SUCCESS


def test_global_timeout_returns_timeout_status() -> None:
    """Global timeout expiry must return TIMEOUT status for pending plugins."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.hung"
    spec = _make_spec(plugin_id, timeout=0.5)
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})

    def _hanging_isolated(snapshot_dict, _base_path_str, _serialized_spec_dict):
        # Simulate hung plugin that takes very long
        time.sleep(10.0)
        return _success_envelope(snapshot_dict["plugin_id"])

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_build_input_snapshot", return_value=_make_snapshot(plugin_id)),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
    ):
        start = time.monotonic()
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=True,
            isolated_worker=_hanging_isolated,
        )
        elapsed = time.monotonic() - start

    assert len(results) == 1
    result = results[0]
    # Must use TIMEOUT status
    assert result.status == PluginStatus.TIMEOUT
    # Must have E4103 diagnostic
    assert any(d.code == "E4103" for d in result.diagnostics)
    # F02/R09: Must return in bounded time (not wait for 10s worker)
    # max_timeout = 0.5 + 5.0 = 5.5s, but we expect return before worker finishes
    assert elapsed < 8.0, f"Expected bounded return, but took {elapsed:.1f}s"


def test_bounded_shutdown_does_not_block() -> None:
    """Executor shutdown must be bounded, not wait indefinitely for hung workers."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.zombie"
    spec = _make_spec(plugin_id, timeout=0.3)
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})

    worker_started = False

    def _zombie_isolated(snapshot_dict, _base_path_str, _serialized_spec_dict):
        nonlocal worker_started
        worker_started = True
        # Zombie worker that runs longer than timeout
        time.sleep(5.0)
        return _success_envelope(snapshot_dict["plugin_id"])

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_build_input_snapshot", return_value=_make_snapshot(plugin_id)),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
    ):
        start = time.monotonic()
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=True,
            isolated_worker=_zombie_isolated,
        )
        elapsed = time.monotonic() - start

    # Worker was started
    assert worker_started
    # But phase returned in bounded time (not waiting for 5s worker)
    # max_timeout = 0.3 + 5.0 = 5.3s global, but shutdown should be immediate
    assert elapsed < 7.0, f"Shutdown not bounded: took {elapsed:.1f}s"
    assert len(results) == 1
    assert results[0].status == PluginStatus.TIMEOUT


def test_e4103_diagnostic_is_present() -> None:
    """Timeout result must include E4103 diagnostic code."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.timeout_diag"
    spec = _make_spec(plugin_id, timeout=0.2)
    registry.specs[plugin_id] = spec
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})

    def _slow_isolated(snapshot_dict, _base_path_str, _serialized_spec_dict):
        time.sleep(0.5)
        return _success_envelope(snapshot_dict["plugin_id"])

    with (
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_build_input_snapshot", return_value=_make_snapshot(plugin_id)),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
    ):
        results = phase_executor.execute_phase_parallel(
            host=registry,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
            has_real_subinterpreters=True,
            isolated_worker=_slow_isolated,
        )

    assert len(results) == 1
    result = results[0]
    assert result.status == PluginStatus.TIMEOUT

    e4103_diags = [d for d in result.diagnostics if d.code == "E4103"]
    assert len(e4103_diags) == 1

    diag = e4103_diags[0]
    assert diag.severity == "error"
    assert "timeout" in diag.message.lower() or "deadline" in diag.message.lower()
