"""Main-interpreter pipeline state primitives for ADR 0097 PR1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .plugin_base import (
    EmittedEvent,
    Phase,
    PluginDataExchangeError,
    PluginExecutionEnvelope,
    PublishedDataMeta,
    Stage,
    SubscriptionValue,
)


@dataclass
class PipelineState:
    """Main-interpreter owner of committed published values and event log."""

    committed_data: dict[str, dict[str, Any]] = field(default_factory=dict)
    published_meta: dict[tuple[str, str], PublishedDataMeta] = field(default_factory=dict)
    emitted_events: list[EmittedEvent] = field(default_factory=list)

    def commit_envelope(
        self,
        *,
        plugin_id: str,
        stage: Stage,
        phase: Phase,
        produces: list[dict[str, Any]],
        envelope: PluginExecutionEnvelope,
    ) -> None:
        """Validate and atomically commit a plugin execution envelope."""
        declared_scopes: dict[str, str] = {}
        for item in produces:
            key = item.get("key")
            if not isinstance(key, str) or not key:
                continue
            scope = item.get("scope", "pipeline_shared")
            declared_scopes[key] = scope if scope in {"pipeline_shared", "stage_local"} else "pipeline_shared"

        pending_messages: list[tuple[str, Any, PublishedDataMeta]] = []
        for message in envelope.published_messages:
            if message.plugin_id != plugin_id:
                raise PluginDataExchangeError(
                    f"Envelope publish plugin mismatch: expected '{plugin_id}', got '{message.plugin_id}'."
                )
            if message.key not in declared_scopes:
                raise PluginDataExchangeError(
                    f"Plugin '{plugin_id}' published undeclared key '{message.key}'."
                )
            pending_messages.append(
                (
                    message.key,
                    message.value,
                    PublishedDataMeta(stage=stage, phase=phase, scope=declared_scopes[message.key]),
                )
            )

        pending_events: list[EmittedEvent] = []
        for event in envelope.emitted_events:
            if event.plugin_id != plugin_id:
                raise PluginDataExchangeError(
                    f"Envelope event plugin mismatch: expected '{plugin_id}', got '{event.plugin_id}'."
                )
            pending_events.append(event)

        plugin_data = dict(self.committed_data.get(plugin_id, {}))
        for key, value, _meta in pending_messages:
            plugin_data[key] = value

        self.committed_data[plugin_id] = plugin_data
        for key, _value, meta in pending_messages:
            self.published_meta[(plugin_id, key)] = meta
        self.emitted_events.extend(pending_events)

    def resolve_subscription(self, *, from_plugin: str, key: str, stage: Stage) -> SubscriptionValue:
        """Resolve a committed published value for snapshot building."""
        plugin_payload = self.committed_data.get(from_plugin)
        if plugin_payload is None:
            raise PluginDataExchangeError(f"Plugin '{from_plugin}' has not published any committed data.")
        if key not in plugin_payload:
            raise PluginDataExchangeError(f"Plugin '{from_plugin}' has not published committed key '{key}'.")
        meta = self.published_meta.get((from_plugin, key))
        if meta is not None and meta.scope == "stage_local" and meta.stage != stage:
            raise PluginDataExchangeError(
                f"Cannot resolve stage_local key '{from_plugin}.{key}' from stage '{meta.stage.value}' "
                f"while building snapshot for stage '{stage.value}'."
            )
        return SubscriptionValue(
            from_plugin=from_plugin,
            key=key,
            value=plugin_payload[key],
            scope=meta.scope if meta is not None else "pipeline_shared",
            stage=meta.stage if meta is not None else None,
            phase=meta.phase if meta is not None else None,
        )

    def invalidate_stage_local_data(self, stage: Stage) -> list[str]:
        """Remove all committed stage_local keys for the completed stage."""
        removed: list[str] = []
        for (plugin_id, key), meta in list(self.published_meta.items()):
            if meta.scope != "stage_local" or meta.stage != stage:
                continue
            plugin_payload = self.committed_data.get(plugin_id)
            if plugin_payload is not None and key in plugin_payload:
                del plugin_payload[key]
                if not plugin_payload:
                    del self.committed_data[plugin_id]
            del self.published_meta[(plugin_id, key)]
            removed.append(f"{plugin_id}.{key}")
        return removed
