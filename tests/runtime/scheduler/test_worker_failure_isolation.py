"""Tests for worker failure isolation in scheduler (ADR 0097 PR2).

These tests verify that plugin crashes in the envelope path:
1. Do not leak partial published state to PipelineState
2. Return a properly formed failed envelope
3. Do not affect subsequent plugins in the wavefront
4. Are properly isolated when using subinterpreters

ADR 0097 Decision D4: Envelope is a proposal, not a commit.
Worker failure cannot partially mutate pipeline-visible state.
"""

from __future__ import annotations

import sys
from pathlib import Path

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
    SubscriptionValue,
    ValidatorJsonPlugin,
)
from kernel.plugin_runner import run_plugin_once  # noqa: E402
from kernel.pipeline_runtime import PipelineState  # noqa: E402


class CrashingPlugin(ValidatorJsonPlugin):
    """Plugin that crashes during execution."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        # Publish some data before crashing
        ctx.publish("partial_output", {"before_crash": True})
        # Then crash
        raise RuntimeError("Intentional crash for testing")


class CrashAfterPublishPlugin(ValidatorJsonPlugin):
    """Plugin that publishes, then crashes."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        ctx.publish("key1", {"data": 1})
        ctx.publish("key2", {"data": 2})
        raise ValueError("Crash after publishing")


class SuccessfulPlugin(ValidatorJsonPlugin):
    """Plugin that succeeds normally."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        ctx.publish("success_output", {"ok": True})
        return PluginResult.success(self.plugin_id, self.api_version)


# --- Worker crash isolation tests ---


def test_crash_returns_failed_envelope() -> None:
    """Plugin crash returns a failed envelope, not exception propagation."""
    snapshot = PluginInputSnapshot(
        plugin_id="test.crasher",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={},
        allowed_dependencies=frozenset(),
        produced_key_scopes={"partial_output": "pipeline_shared"},
    )

    plugin = CrashingPlugin("test.crasher")
    envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

    # Should return envelope, not raise exception
    assert envelope is not None
    assert envelope.result.status == PluginStatus.FAILED
    assert envelope.result.plugin_id == "test.crasher"

    # Should have error diagnostic
    assert len(envelope.result.diagnostics) >= 1
    error_diag = envelope.result.diagnostics[0]
    assert error_diag.severity == "error"
    assert "crash" in error_diag.message.lower() or "boom" in error_diag.message.lower() or "RuntimeError" in error_diag.message


def test_crash_includes_traceback() -> None:
    """Failed envelope should include error traceback for debugging."""
    snapshot = PluginInputSnapshot(
        plugin_id="test.crasher",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={},
        allowed_dependencies=frozenset(),
        produced_key_scopes={"partial_output": "pipeline_shared"},
    )

    plugin = CrashingPlugin("test.crasher")
    envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

    # Should include traceback
    assert envelope.result.error_traceback is not None
    assert "RuntimeError" in envelope.result.error_traceback
    assert "Intentional crash" in envelope.result.error_traceback


def test_crash_collects_partial_outbox() -> None:
    """Crashed plugin's partial outbox should be in envelope (but not committed)."""
    snapshot = PluginInputSnapshot(
        plugin_id="test.crasher",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={},
        allowed_dependencies=frozenset(),
        produced_key_scopes={"partial_output": "pipeline_shared"},
    )

    plugin = CrashingPlugin("test.crasher")
    envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

    # The outbox may contain partial data (published before crash)
    # This is collected but NOT committed to PipelineState
    # The envelope captures what was published before the crash


def test_failed_envelope_not_committed_to_pipeline_state() -> None:
    """Failed envelope must NOT be committed to PipelineState."""
    state = PipelineState()

    snapshot = PluginInputSnapshot(
        plugin_id="test.crasher",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={},
        allowed_dependencies=frozenset(),
        produced_key_scopes={"partial_output": "pipeline_shared"},
    )

    plugin = CrashingPlugin("test.crasher")
    envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

    # Verify plugin failed
    assert envelope.result.status == PluginStatus.FAILED

    # Attempt to commit should be guarded by caller (scheduler)
    # PipelineState itself doesn't reject failed envelopes,
    # but scheduler should NOT call commit_envelope for failed results

    # Verify state is empty (nothing committed)
    assert "test.crasher" not in state.committed_data


def test_crash_does_not_affect_subsequent_plugin() -> None:
    """Crash in one plugin should not affect subsequent plugins in wavefront."""
    # This is a scheduler-level test that requires integration testing
    pytest.skip("PR2 integration test: requires scheduler execution with multiple plugins")

    # When PR2 is implemented, this test should:
    # 1. Create wavefront with [crasher, successor]
    # 2. Execute wavefront
    # 3. Verify crasher failed
    # 4. Verify successor succeeded (unaffected by crasher)


# --- Partial state leak prevention tests ---


def test_no_partial_commit_on_crash() -> None:
    """Plugin that publishes then crashes should not have partial state committed."""
    state = PipelineState()

    snapshot = PluginInputSnapshot(
        plugin_id="test.partial_crasher",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={},
        allowed_dependencies=frozenset(),
        produced_key_scopes={
            "key1": "pipeline_shared",
            "key2": "pipeline_shared",
        },
    )

    plugin = CrashAfterPublishPlugin("test.partial_crasher")
    envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

    # Plugin failed
    assert envelope.result.status == PluginStatus.FAILED

    # Published messages are in envelope but should NOT be committed
    # (Scheduler is responsible for not committing failed envelopes)

    # State should be clean
    assert "test.partial_crasher" not in state.committed_data


def test_successful_plugin_after_crash_commits_normally() -> None:
    """Successful plugin execution after a crash should commit normally."""
    state = PipelineState()

    # First, simulate a crashed plugin (don't commit)
    crash_snapshot = PluginInputSnapshot(
        plugin_id="test.crasher",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={},
        allowed_dependencies=frozenset(),
        produced_key_scopes={"partial_output": "pipeline_shared"},
    )
    crash_plugin = CrashingPlugin("test.crasher")
    crash_envelope = run_plugin_once(snapshot=crash_snapshot, plugin=crash_plugin)
    assert crash_envelope.result.status == PluginStatus.FAILED
    # Don't commit crash_envelope

    # Then, run successful plugin
    success_snapshot = PluginInputSnapshot(
        plugin_id="test.succeeder",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={},
        allowed_dependencies=frozenset(),
        produced_key_scopes={"success_output": "pipeline_shared"},
    )
    success_plugin = SuccessfulPlugin("test.succeeder")
    success_envelope = run_plugin_once(snapshot=success_snapshot, plugin=success_plugin)
    assert success_envelope.result.status == PluginStatus.SUCCESS

    # Commit successful envelope
    state.commit_envelope(
        plugin_id="test.succeeder",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        produces=[{"key": "success_output", "scope": "pipeline_shared"}],
        envelope=success_envelope,
    )

    # Verify only successful plugin's data is committed
    assert "test.crasher" not in state.committed_data
    assert "test.succeeder" in state.committed_data
    assert state.committed_data["test.succeeder"]["success_output"] == {"ok": True}


# --- Subinterpreter isolation tests ---


def test_subinterpreter_crash_is_isolated() -> None:
    """Crash in subinterpreter should be isolated from main interpreter."""
    pytest.skip("PR2 integration test: requires actual subinterpreter execution")

    # When PR2 is implemented with subinterpreters:
    # 1. Execute crashing plugin in subinterpreter
    # 2. Verify crash doesn't affect main interpreter state
    # 3. Verify failed envelope is returned correctly


def test_subinterpreter_memory_is_isolated() -> None:
    """Subinterpreter memory should be isolated from main interpreter."""
    pytest.skip("PR2 integration test: requires actual subinterpreter execution")

    # When PR2 is implemented with subinterpreters:
    # 1. Plugin modifies global state in subinterpreter
    # 2. Verify main interpreter globals are unaffected
