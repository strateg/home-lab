from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (  # noqa: E402
    EmittedEvent,
    Phase,
    PluginExecutionEnvelope,
    PluginInputSnapshot,
    PluginResult,
    PublishedMessage,
    Stage,
    SubscriptionValue,
)


def test_plugin_input_snapshot_defaults() -> None:
    snapshot = PluginInputSnapshot(
        plugin_id="test.plugin",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
    )

    assert snapshot.plugin_id == "test.plugin"
    assert snapshot.subscriptions == {}
    assert snapshot.allowed_dependencies == frozenset()
    assert snapshot.produced_key_scopes == {}


def test_envelope_contains_result_messages_and_events() -> None:
    result = PluginResult.success("test.plugin")
    message = PublishedMessage(
        plugin_id="test.plugin",
        key="ready",
        value={"ok": True},
        scope="pipeline_shared",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
    )
    event = EmittedEvent(
        plugin_id="test.plugin",
        topic="test.ready",
        payload={"ok": True},
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
    )
    envelope = PluginExecutionEnvelope(result=result, published_messages=[message], emitted_events=[event])

    assert envelope.result is result
    assert envelope.published_messages == [message]
    assert envelope.emitted_events == [event]


def test_subscription_value_preserves_scope_and_origin() -> None:
    value = SubscriptionValue(
        from_plugin="producer.plugin",
        key="normalized_rows",
        value=[{"instance": "x"}],
        scope="stage_local",
        stage=Stage.COMPILE,
        phase=Phase.RUN,
    )

    assert value.from_plugin == "producer.plugin"
    assert value.scope == "stage_local"
    assert value.stage == Stage.COMPILE
    assert value.phase == Phase.RUN
