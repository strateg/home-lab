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


def test_commit_envelope_commits_declared_messages() -> None:
    state = PipelineState()
    envelope = PluginExecutionEnvelope(
        result=PluginResult.success("test.plugin"),
        published_messages=[
            PublishedMessage(
                plugin_id="test.plugin",
                key="ready",
                value={"ok": True},
                scope="pipeline_shared",
                stage=Stage.VALIDATE,
                phase=Phase.RUN,
            )
        ],
    )

    state.commit_envelope(
        plugin_id="test.plugin",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        produces=[{"key": "ready", "scope": "pipeline_shared"}],
        envelope=envelope,
    )

    assert state.committed_data == {"test.plugin": {"ready": {"ok": True}}}


def test_commit_envelope_rejects_undeclared_publish_without_partial_commit() -> None:
    state = PipelineState()
    envelope = PluginExecutionEnvelope(
        result=PluginResult.success("test.plugin"),
        published_messages=[
            PublishedMessage(
                plugin_id="test.plugin",
                key="undeclared",
                value={"ok": True},
                scope="pipeline_shared",
                stage=Stage.VALIDATE,
                phase=Phase.RUN,
            )
        ],
    )

    with pytest.raises(PluginDataExchangeError, match="undeclared key"):
        state.commit_envelope(
            plugin_id="test.plugin",
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            produces=[{"key": "ready", "scope": "pipeline_shared"}],
            envelope=envelope,
        )

    assert state.committed_data == {}


def test_commit_envelope_rejects_plugin_id_mismatch() -> None:
    state = PipelineState()
    envelope = PluginExecutionEnvelope(
        result=PluginResult.success("test.plugin"),
        published_messages=[
            PublishedMessage(
                plugin_id="other.plugin",
                key="ready",
                value=True,
                scope="pipeline_shared",
                stage=Stage.VALIDATE,
                phase=Phase.RUN,
            )
        ],
    )

    with pytest.raises(PluginDataExchangeError, match="plugin mismatch"):
        state.commit_envelope(
            plugin_id="test.plugin",
            stage=Stage.VALIDATE,
            phase=Phase.RUN,
            produces=[{"key": "ready", "scope": "pipeline_shared"}],
            envelope=envelope,
        )
