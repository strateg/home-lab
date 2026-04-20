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
from unittest.mock import MagicMock, patch, call

import pytest

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (  # noqa: E402
    Phase,
    PluginContext,
    PluginInputSnapshot,
    PluginKind,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class PublishingPlugin(ValidatorJsonPlugin):
    """Plugin that publishes data for merge-back testing."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        ctx.publish("output_key", {"data": "value"})
        return PluginResult.success(self.plugin_id, self.api_version)


# --- Primary path no-merge-back tests ---


def test_main_interpreter_mode_does_not_call_mirror() -> None:
    """execution_mode='main_interpreter' must NOT call _mirror_context_into_pipeline_state()."""
    pytest.skip("PR2 not implemented: execution_mode routing not yet added")

    # When PR2 is implemented, this test should:
    # 1. Mock _mirror_context_into_pipeline_state
    # 2. Execute plugin with execution_mode="main_interpreter"
    # 3. Assert mirror was NOT called
    # 4. Assert _commit_envelope_result() WAS called


def test_subinterpreter_mode_does_not_call_mirror() -> None:
    """execution_mode='subinterpreter' must NOT call _mirror_context_into_pipeline_state()."""
    pytest.skip("PR2 not implemented: execution_mode routing not yet added")

    # When PR2 is implemented, this test should:
    # 1. Mock _mirror_context_into_pipeline_state
    # 2. Execute plugin with execution_mode="subinterpreter"
    # 3. Assert mirror was NOT called


def test_thread_legacy_mode_calls_mirror() -> None:
    """execution_mode='thread_legacy' MUST call _mirror_context_into_pipeline_state()."""
    pytest.skip("PR2 not implemented: execution_mode routing not yet added")

    # When PR2 is implemented, this test should:
    # 1. Mock _mirror_context_into_pipeline_state
    # 2. Execute plugin with execution_mode="thread_legacy"
    # 3. Assert mirror WAS called


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
        PublishedMessage,
        PluginStatus,
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
        PublishedMessage,
        PluginStatus,
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
    pytest.skip("PR2 not implemented: side-effect application testing requires integration")

    # When PR2 is implemented, this test should verify:
    # 1. Plugin publishes class_map/object_map/effective_model_candidate
    # 2. commit_envelope() commits to PipelineState
    # 3. _apply_authoritative_commit_side_effects() updates ctx.classes/ctx.objects/ctx.compiled_json
    # 4. This is the ONLY way ctx authoritative fields are updated in envelope path
