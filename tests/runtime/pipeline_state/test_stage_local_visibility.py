from __future__ import annotations

import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginDataExchangeError  # noqa: E402
from kernel.pipeline_runtime import PipelineState  # noqa: E402
from kernel.plugin_base import (  # noqa: E402
    Phase,
    PluginExecutionEnvelope,
    PluginResult,
    PublishedMessage,
    Stage,
)


def _commit_stage_local(state: PipelineState) -> None:
    state.commit_envelope(
        plugin_id="compile.producer",
        stage=Stage.COMPILE,
        phase=Phase.RUN,
        produces=[{"key": "tmp", "scope": "stage_local"}],
        envelope=PluginExecutionEnvelope(
            result=PluginResult.success("compile.producer"),
            published_messages=[
                PublishedMessage(
                    plugin_id="compile.producer",
                    key="tmp",
                    value={"ok": True},
                    scope="stage_local",
                    stage=Stage.COMPILE,
                    phase=Phase.RUN,
                )
            ],
        ),
    )


def test_stage_local_visible_within_same_stage() -> None:
    state = PipelineState()
    _commit_stage_local(state)

    value = state.resolve_subscription(from_plugin="compile.producer", key="tmp", stage=Stage.COMPILE)

    assert value.value == {"ok": True}
    assert value.scope == "stage_local"


def test_stage_local_blocked_across_stage_boundary() -> None:
    state = PipelineState()
    _commit_stage_local(state)

    with pytest.raises(PluginDataExchangeError, match="stage_local key"):
        state.resolve_subscription(from_plugin="compile.producer", key="tmp", stage=Stage.VALIDATE)


def test_stage_local_invalidation_removes_payload() -> None:
    state = PipelineState()
    _commit_stage_local(state)

    removed = state.invalidate_stage_local_data(Stage.COMPILE)

    assert removed == ["compile.producer.tmp"]
    with pytest.raises(PluginDataExchangeError):
        state.resolve_subscription(from_plugin="compile.producer", key="tmp", stage=Stage.COMPILE)
