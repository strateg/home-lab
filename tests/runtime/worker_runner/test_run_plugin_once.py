from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (  # noqa: E402
    Phase,
    PluginDataExchangeError,
    PluginInputSnapshot,
    PluginKind,
    PluginResult,
    Stage,
    SubscriptionValue,
    ValidatorJsonPlugin,
)
from kernel.plugin_runner import run_plugin_once  # noqa: E402


class PublisherPlugin(ValidatorJsonPlugin):
    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        payload = ctx.subscribe("producer.input", "rows")
        ctx.publish("ready", {"rows": len(payload)})
        ctx.emit("validator.ready", {"rows": len(payload)})
        return PluginResult.success(self.plugin_id, self.api_version)


class CrashPlugin(ValidatorJsonPlugin):
    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        raise RuntimeError("boom")


class MissingDependencyPlugin(ValidatorJsonPlugin):
    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON

    def execute(self, ctx, stage):
        try:
            ctx.subscribe("producer.input", "rows")
        except PluginDataExchangeError:
            return PluginResult.success(self.plugin_id, self.api_version)
        raise AssertionError("expected subscribe failure")


def test_run_plugin_once_builds_envelope_from_snapshot() -> None:
    snapshot = PluginInputSnapshot(
        plugin_id="validator.publisher",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        subscriptions={
            ("producer.input", "rows"): SubscriptionValue(
                from_plugin="producer.input",
                key="rows",
                value=[{"instance": "a"}, {"instance": "b"}],
            )
        },
        allowed_dependencies=frozenset({"producer.input"}),
        produced_key_scopes={"ready": "pipeline_shared"},
    )

    plugin = PublisherPlugin("validator.publisher")
    envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

    assert envelope.result.plugin_id == "validator.publisher"
    assert envelope.result.status.value == "SUCCESS"
    assert len(envelope.published_messages) == 1
    assert envelope.published_messages[0].key == "ready"
    assert envelope.published_messages[0].value == {"rows": 2}
    assert len(envelope.emitted_events) == 1
    assert envelope.emitted_events[0].topic == "validator.ready"


def test_run_plugin_once_wraps_plugin_crash_in_failed_envelope() -> None:
    snapshot = PluginInputSnapshot(
        plugin_id="validator.crash",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
    )

    plugin = CrashPlugin("validator.crash")
    envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

    assert envelope.result.plugin_id == "validator.crash"
    assert envelope.result.status.value == "FAILED"
    assert envelope.result.error_traceback
    assert envelope.published_messages == []


def test_run_plugin_once_uses_snapshot_dependencies_only() -> None:
    snapshot = PluginInputSnapshot(
        plugin_id="validator.missing-dep",
        stage=Stage.VALIDATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        allowed_dependencies=frozenset(),
    )

    plugin = MissingDependencyPlugin("validator.missing-dep")
    envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

    assert envelope.result.status.value == "SUCCESS"
    assert envelope.published_messages == []
