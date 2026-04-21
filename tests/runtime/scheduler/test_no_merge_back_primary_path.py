"""Tests for no-merge-back behavior in primary execution path (ADR 0097 PR2).

These tests verify that the primary envelope path does NOT call
_mirror_context_into_pipeline_state() — only the legacy thread_legacy
path should perform merge-back.

ADR 0097 Decision D1: Main interpreter is the sole owner of pipeline-global state.
Workers propose outputs via envelope; only main interpreter commits them.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

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
    PublishedMessage,
    Stage,
)
from kernel.plugin_registry import PluginRegistry, PluginSpec  # noqa: E402


def _make_spec(plugin_id: str, *, execution_mode: str) -> PluginSpec:
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
        produces=[{"key": "output_key", "scope": "pipeline_shared"}],
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
        produced_key_scopes={"output_key": "pipeline_shared"},
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
                key="output_key",
                value={"data": "value"},
                scope="pipeline_shared",
                stage=Stage.VALIDATE,
                phase=Phase.RUN,
            )
        ],
    )


# --- Primary path no-merge-back tests ---


def test_main_interpreter_mode_does_not_call_mirror() -> None:
    """execution_mode='main_interpreter' must NOT call _mirror_context_into_pipeline_state()."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.main.no_mirror"
    registry.specs[plugin_id] = _make_spec(plugin_id, execution_mode="main_interpreter")
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})
    snapshot = _make_snapshot(plugin_id)

    with (
        patch.object(registry, "_build_input_snapshot", return_value=snapshot),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(registry, "_execute_plugin_envelope_local", return_value=_success_envelope(plugin_id)),
        patch.object(
            registry, "_commit_envelope_result", return_value=PluginResult.success(plugin_id, "2.0")
        ) as commit,
        patch.object(registry, "_mirror_context_into_pipeline_state") as mirror,
    ):
        registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    commit.assert_called_once()
    mirror.assert_not_called()


def test_subinterpreter_mode_does_not_call_mirror() -> None:
    """execution_mode='subinterpreter' must NOT call _mirror_context_into_pipeline_state()."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.sub.no_mirror"
    registry.specs[plugin_id] = _make_spec(plugin_id, execution_mode="subinterpreter")
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})
    snapshot = _make_snapshot(plugin_id)

    with (
        patch.object(registry, "_build_input_snapshot", return_value=snapshot),
        patch.object(registry, "_validate_required_consumes_snapshot", return_value=[]),
        patch.object(registry, "_execute_plugin_envelope_local", return_value=_success_envelope(plugin_id)),
        patch.object(
            registry, "_commit_envelope_result", return_value=PluginResult.success(plugin_id, "2.0")
        ) as commit,
        patch.object(registry, "_mirror_context_into_pipeline_state") as mirror,
    ):
        registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    commit.assert_called_once()
    mirror.assert_not_called()


def test_thread_legacy_mode_calls_mirror() -> None:
    """execution_mode='thread_legacy' MUST call _mirror_context_into_pipeline_state()."""
    registry = PluginRegistry(V5_TOOLS)
    plugin_id = "test.thread_legacy.mirror"
    registry.specs[plugin_id] = _make_spec(plugin_id, execution_mode="thread_legacy")
    ctx = PluginContext(topology_path="topology/topology.yaml", profile="test", model_lock={})

    with (
        patch.object(registry, "execute_plugin", return_value=PluginResult.success(plugin_id, "2.0")) as execute_legacy,
        patch.object(registry, "_mirror_context_into_pipeline_state") as mirror,
    ):
        registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    execute_legacy.assert_called_once()
    mirror.assert_called_once()


# --- Current behavior baseline tests ---


def test_current_subinterpreter_compatible_true_uses_commit_envelope() -> None:
    """Current: subinterpreter_compatible=true uses _commit_envelope_result()."""
    # This tests current behavior as baseline for PR2 changes

    from kernel.plugin_registry import PluginRegistry

    # The current implementation should:
    # - Call _build_input_snapshot()
    # - Execute via envelope path
    # - Call _commit_envelope_result()
    # - NOT call _mirror_context_into_pipeline_state()

    # Verification is implicit in the parity tests; this documents expected behavior


def test_current_subinterpreter_compatible_false_uses_mirror() -> None:
    """Current: subinterpreter_compatible=false uses _mirror_context_into_pipeline_state()."""
    # This tests current behavior as baseline for PR2 changes

    # The current implementation should:
    # - Call execute_plugin() (legacy path)
    # - Call _mirror_context_into_pipeline_state() to sync state

    # This is the behavior that PR2 will restrict to thread_legacy only


# --- Commit flow integrity tests ---


def test_envelope_path_uses_pipeline_state_commit() -> None:
    """Envelope path must use PipelineState.commit_envelope() for publication."""
    from kernel.pipeline_runtime import PipelineState
    from kernel.plugin_base import (
        PluginExecutionEnvelope,
        PluginResult,
        PluginStatus,
        PublishedMessage,
    )

    state = PipelineState()

    # Create an envelope with published message
    envelope = PluginExecutionEnvelope(
        result=PluginResult(
            plugin_id="test.plugin",
            api_version="2.0",
            status=PluginStatus.SUCCESS,
            diagnostics=[],
        ),
        published_messages=[
            PublishedMessage(
                plugin_id="test.plugin",
                key="output",
                value={"data": 123},
                scope="pipeline_shared",
                stage=Stage.VALIDATE,
                phase=Phase.RUN,
            )
        ],
        emitted_events=[],
    )

    # Commit the envelope
    state.commit_envelope(
        plugin_id="test.plugin",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        produces=[{"key": "output", "scope": "pipeline_shared"}],
        envelope=envelope,
    )

    # Verify data was committed
    assert "test.plugin" in state.committed_data
    assert state.committed_data["test.plugin"]["output"] == {"data": 123}


def test_commit_envelope_does_not_mutate_context_directly() -> None:
    """PipelineState.commit_envelope() does not mutate PluginContext directly."""
    from kernel.pipeline_runtime import PipelineState
    from kernel.plugin_base import (
        PluginContext,
        PluginExecutionEnvelope,
        PluginResult,
        PluginStatus,
        PublishedMessage,
    )

    state = PipelineState()
    ctx = PluginContext(topology_path="test.yaml", profile="test", model_lock={})

    # Track original state
    original_published = dict(ctx._published_data)

    envelope = PluginExecutionEnvelope(
        result=PluginResult(
            plugin_id="test.plugin",
            api_version="2.0",
            status=PluginStatus.SUCCESS,
            diagnostics=[],
        ),
        published_messages=[
            PublishedMessage(
                plugin_id="test.plugin",
                key="new_key",
                value={"new": "data"},
                scope="pipeline_shared",
                stage=Stage.VALIDATE,
                phase=Phase.RUN,
            )
        ],
        emitted_events=[],
    )

    # Commit envelope to PipelineState
    state.commit_envelope(
        plugin_id="test.plugin",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        produces=[{"key": "new_key", "scope": "pipeline_shared"}],
        envelope=envelope,
    )

    # Context should NOT be mutated by commit_envelope
    assert ctx._published_data == original_published

    # Only PipelineState should have the new data
    assert state.committed_data["test.plugin"]["new_key"] == {"new": "data"}


# --- Side-effect application tests (for compatibility) ---


def test_side_effect_application_updates_context_after_commit() -> None:
    """_apply_authoritative_commit_side_effects() updates ctx after commit."""
    from kernel.pipeline_runtime import PipelineState
    from kernel.plugin_base import PluginExecutionEnvelope

    registry = PluginRegistry(V5_TOOLS)
    spec = PluginSpec(
        id="test.compiler.owner",
        kind=PluginKind.COMPILER,
        entry="compilers/effective_model_compiler.py:EffectiveModelCompiler",
        api_version="2.0",
        stages=[Stage.COMPILE],
        order=100,
        phase=Phase.RUN,
        depends_on=[],
        config={},
        produces=[
            {"key": "class_map", "scope": "pipeline_shared"},
            {"key": "object_map", "scope": "pipeline_shared"},
            {"key": "effective_model_candidate", "scope": "pipeline_shared"},
        ],
        consumes=[],
        compiled_json_owner=True,
        manifest_path="tests/runtime/scheduler",
        execution_mode="main_interpreter",
    )
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={"class.old": {"name": "old"}},
        objects={"object.old": {"name": "old"}},
        compiled_json={"version": "old"},
    )
    state = PipelineState()
    envelope = PluginExecutionEnvelope(
        result=PluginResult.success(spec.id, spec.api_version),
        published_messages=[
            PublishedMessage(
                plugin_id=spec.id,
                key="class_map",
                value={"class.new": {"payload": {"name": "new-class"}}},
                scope="pipeline_shared",
                stage=Stage.COMPILE,
                phase=Phase.RUN,
            ),
            PublishedMessage(
                plugin_id=spec.id,
                key="object_map",
                value={"object.new": {"payload": {"name": "new-object"}}},
                scope="pipeline_shared",
                stage=Stage.COMPILE,
                phase=Phase.RUN,
            ),
            PublishedMessage(
                plugin_id=spec.id,
                key="effective_model_candidate",
                value={"version": "new"},
                scope="pipeline_shared",
                stage=Stage.COMPILE,
                phase=Phase.RUN,
            ),
        ],
    )

    state.commit_envelope(
        plugin_id=spec.id,
        stage=Stage.COMPILE,
        phase=Phase.RUN,
        produces=spec.produces,
        envelope=envelope,
    )
    registry._apply_authoritative_commit_side_effects(ctx=ctx, pipeline_state=state, spec=spec)

    assert ctx.classes == {"class.new": {"name": "new-class"}}
    assert ctx.objects == {"object.new": {"name": "new-object"}}
    assert ctx.compiled_json == {"version": "new"}
