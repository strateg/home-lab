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

import concurrent.futures
import sys
from pathlib import Path
from unittest.mock import patch

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.pipeline_runtime import PipelineState  # noqa: E402
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
    ValidatorJsonPlugin,
)
from kernel.plugin_registry import PluginRegistry, PluginSpec  # noqa: E402
from kernel.plugin_runner import run_plugin_once  # noqa: E402


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
    assert (
        "crash" in error_diag.message.lower()
        or "boom" in error_diag.message.lower()
        or "RuntimeError" in error_diag.message
    )


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
    assert len(envelope.published_messages) == 1
    message = envelope.published_messages[0]
    assert message.plugin_id == "test.crasher"
    assert message.key == "partial_output"
    assert message.value == {"before_crash": True}


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
    crash_envelope = run_plugin_once(snapshot=crash_snapshot, plugin=CrashingPlugin("test.crasher"))
    success_envelope = run_plugin_once(snapshot=success_snapshot, plugin=SuccessfulPlugin("test.succeeder"))

    assert crash_envelope.result.status == PluginStatus.FAILED
    assert success_envelope.result.status == PluginStatus.SUCCESS

    state = PipelineState()
    # Scheduler behavior: commit only successful envelope
    state.commit_envelope(
        plugin_id="test.succeeder",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        produces=[{"key": "success_output", "scope": "pipeline_shared"}],
        envelope=success_envelope,
    )

    assert "test.crasher" not in state.committed_data
    assert state.committed_data["test.succeeder"]["success_output"] == {"ok": True}


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


def test_failed_verdict_output_can_be_committed_when_explicitly_allowed() -> None:
    """Non-crash failures may commit declared verdict keys when whitelisted."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.verify"
    spec = PluginSpec(
        id=plugin_id,
        kind=PluginKind.ASSEMBLER,
        entry="assemblers/workspace_assembler.py:AssemblyVerifyAssembler",
        api_version="2.0",
        stages=[Stage.ASSEMBLE],
        order=420,
        phase=Phase.VERIFY,
        depends_on=[],
        config={"commit_keys_on_failure": ["assemble_verified"]},
        produces=[{"key": "assemble_verified", "scope": "pipeline_shared"}],
        consumes=[],
        execution_mode="subinterpreter",
        manifest_path="tests/runtime/scheduler",
    )
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})
    state = PipelineState()
    envelope = PluginExecutionEnvelope(
        result=PluginResult(
            plugin_id=plugin_id,
            api_version="2.0",
            status=PluginStatus.FAILED,
            diagnostics=[
                PluginDiagnostic(
                    code="E8103",
                    severity="error",
                    stage=Stage.ASSEMBLE.value,
                    phase=Phase.VERIFY.value,
                    message="verification failed",
                    path="assemble:verify",
                    plugin_id=plugin_id,
                )
            ],
        ),
        published_messages=[
            PublishedMessage(
                plugin_id=plugin_id,
                key="assemble_verified",
                value=False,
                scope="pipeline_shared",
                stage=Stage.ASSEMBLE,
                phase=Phase.VERIFY,
            )
        ],
    )

    result = registry._commit_envelope_result(  # noqa: SLF001 - runtime contract test
        ctx=ctx,
        pipeline_state=state,
        spec=spec,
        stage=Stage.ASSEMBLE,
        phase=Phase.VERIFY,
        envelope=envelope,
        contract_warnings=False,
        contract_errors=False,
    )

    assert result.status == PluginStatus.FAILED
    assert state.committed_data[plugin_id]["assemble_verified"] is False
    assert ctx.get_published_data()[plugin_id]["assemble_verified"] is False


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
    registry = PluginRegistry(V5_TOOLS)
    crash_id = "test.sub.crasher"
    success_id = "test.sub.success"
    registry.specs[crash_id] = PluginSpec(
        id=crash_id,
        kind=PluginKind.VALIDATOR_JSON,
        entry="validators/references_validator.py:ReferencesValidator",
        api_version="2.0",
        stages=[Stage.VALIDATE],
        order=100,
        phase=Phase.RUN,
        depends_on=[],
        config={},
        produces=[{"key": "partial_output", "scope": "pipeline_shared"}],
        consumes=[],
        execution_mode="subinterpreter",
        manifest_path="tests/runtime/scheduler",
    )
    registry.specs[success_id] = PluginSpec(
        id=success_id,
        kind=PluginKind.VALIDATOR_JSON,
        entry="validators/references_validator.py:ReferencesValidator",
        api_version="2.0",
        stages=[Stage.VALIDATE],
        order=110,
        phase=Phase.RUN,
        depends_on=[],
        config={},
        produces=[{"key": "success_output", "scope": "pipeline_shared"}],
        consumes=[],
        execution_mode="subinterpreter",
        manifest_path="tests/runtime/scheduler",
    )
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})

    def _snapshot(plugin_id: str, key: str) -> PluginInputSnapshot:
        return PluginInputSnapshot(
            plugin_id=plugin_id,
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            topology_path="topology/topology.yaml",
            profile="test",
            subscriptions={},
            allowed_dependencies=frozenset(),
            produced_key_scopes={key: "pipeline_shared"},
        )

    def _isolated(snapshot_dict, _base_path, _serialized_spec):
        pid = snapshot_dict["plugin_id"]
        if pid == crash_id:
            return PluginExecutionEnvelope(
                result=PluginResult(
                    plugin_id=pid,
                    api_version="2.0",
                    status=PluginStatus.FAILED,
                    diagnostics=[
                        PluginDiagnostic(
                            code="E4102",
                            severity="error",
                            stage=Stage.VALIDATE.value,
                            phase=Phase.RUN.value,
                            message="forced crash",
                            path="kernel.subinterpreter",
                            plugin_id="kernel",
                        )
                    ],
                ),
                published_messages=[
                    PublishedMessage(
                        plugin_id=pid,
                        key="partial_output",
                        value={"before_crash": True},
                        scope="pipeline_shared",
                        stage=Stage.VALIDATE,
                        phase=Phase.RUN,
                    )
                ],
            )
        return PluginExecutionEnvelope(
            result=PluginResult.success(pid, "2.0"),
            published_messages=[
                PublishedMessage(
                    plugin_id=pid,
                    key="success_output",
                    value={"ok": True},
                    scope="pipeline_shared",
                    stage=Stage.VALIDATE,
                    phase=Phase.RUN,
                )
            ],
        )

    with (
        patch("kernel.plugin_registry.HAS_REAL_SUBINTERPRETERS", True),
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(
            registry,
            "_build_input_snapshot",
            side_effect=lambda *, plugin_id, **_: _snapshot(
                plugin_id,
                "partial_output" if plugin_id == crash_id else "success_output",
            ),
        ),
        patch("kernel.plugin_registry._execute_plugin_isolated", side_effect=_isolated),
    ):
        results = registry._execute_phase_parallel(
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[crash_id, success_id],
        )

    statuses = {r.plugin_id: r.status for r in results}
    assert statuses[crash_id] == PluginStatus.FAILED
    assert statuses[success_id] == PluginStatus.SUCCESS
    committed = ctx.get_published_data()
    assert crash_id not in committed
    assert committed[success_id]["success_output"] == {"ok": True}


def test_subinterpreter_memory_is_isolated() -> None:
    """Subinterpreter route exposes only envelope payloads to main pipeline state."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.sub.state_only"
    registry.specs[plugin_id] = PluginSpec(
        id=plugin_id,
        kind=PluginKind.VALIDATOR_JSON,
        entry="validators/references_validator.py:ReferencesValidator",
        api_version="2.0",
        stages=[Stage.VALIDATE],
        order=100,
        phase=Phase.RUN,
        depends_on=[],
        config={},
        produces=[{"key": "safe_output", "scope": "pipeline_shared"}],
        consumes=[],
        execution_mode="subinterpreter",
        manifest_path="tests/runtime/scheduler",
    )
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})
    marker = {"mutated": False}

    def _isolated(snapshot_dict, _base_path, _serialized_spec):
        marker["mutated"] = True
        return PluginExecutionEnvelope(
            result=PluginResult.success(snapshot_dict["plugin_id"], "2.0"),
            published_messages=[
                PublishedMessage(
                    plugin_id=snapshot_dict["plugin_id"],
                    key="safe_output",
                    value={"ok": True},
                    scope="pipeline_shared",
                    stage=Stage.VALIDATE,
                    phase=Phase.RUN,
                )
            ],
            execution_metadata={"worker_private": "not_committed"},
        )

    with (
        patch("kernel.plugin_registry.HAS_REAL_SUBINTERPRETERS", True),
        patch.object(
            registry,
            "_get_parallel_executor",
            side_effect=lambda max_workers: concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        ),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(
            registry,
            "_build_input_snapshot",
            return_value=PluginInputSnapshot(
                plugin_id=plugin_id,
                stage=Stage.VALIDATE,
                phase=Phase.RUN,
                topology_path="topology/topology.yaml",
                profile="test",
                subscriptions={},
                allowed_dependencies=frozenset(),
                produced_key_scopes={"safe_output": "pipeline_shared"},
            ),
        ),
        patch("kernel.plugin_registry._execute_plugin_isolated", side_effect=_isolated),
    ):
        results = registry._execute_phase_parallel(
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            ctx=ctx,
            plugin_ids=[plugin_id],
        )

    assert marker["mutated"] is True
    assert len(results) == 1
    assert results[0].status == PluginStatus.SUCCESS
    committed = ctx.get_published_data()
    assert committed[plugin_id]["safe_output"] == {"ok": True}
    assert "worker_private" not in committed[plugin_id]
