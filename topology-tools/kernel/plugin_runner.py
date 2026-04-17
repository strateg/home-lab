"""Envelope-model plugin runner utilities for ADR 0097 PR1.

This module introduces the snapshot-backed execution path without yet replacing
all legacy registry scheduling behavior.
"""

from __future__ import annotations

import time
import traceback
from typing import Any

from .plugin_base import (
    PluginBase,
    PluginContext,
    PluginDiagnostic,
    PluginExecutionEnvelope,
    PluginExecutionScope,
    PluginInputSnapshot,
    PluginResult,
    PluginStatus,
)


def run_plugin_once(*, snapshot: PluginInputSnapshot, plugin: PluginBase) -> PluginExecutionEnvelope:
    """Execute a single plugin from immutable snapshot input and collect an envelope."""
    ctx = PluginContext.from_snapshot(snapshot)
    scope = PluginExecutionScope(
        plugin_id=snapshot.plugin_id,
        allowed_dependencies=snapshot.allowed_dependencies,
        phase=snapshot.phase,
        config=ctx.config.copy(),
        stage=snapshot.stage,
        produced_key_scopes=snapshot.produced_key_scopes,
    )
    token = ctx._set_execution_scope(scope)
    start_time = time.perf_counter()
    try:
        result = plugin.execute_phase(ctx, snapshot.stage, snapshot.phase)
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return PluginExecutionEnvelope(
            result=result,
            published_messages=ctx.drain_outbox(),
            emitted_events=ctx.drain_event_outbox(),
        )
    except Exception as exc:  # noqa: BLE001
        duration_ms = (time.perf_counter() - start_time) * 1000
        result = PluginResult(
            plugin_id=snapshot.plugin_id,
            api_version=plugin.api_version,
            status=PluginStatus.FAILED,
            duration_ms=duration_ms,
            diagnostics=[
                PluginDiagnostic(
                    code="E4102",
                    severity="error",
                    stage=snapshot.stage.value,
                    phase=snapshot.phase.value,
                    message=f"Plugin crashed: {exc}",
                    path="kernel.plugin_runner",
                    plugin_id="kernel",
                )
            ],
            error_traceback=traceback.format_exc(),
        )
        return PluginExecutionEnvelope(
            result=result,
            published_messages=ctx.drain_outbox(),
            emitted_events=ctx.drain_event_outbox(),
            execution_metadata={"runner_error": str(exc)},
        )
    finally:
        ctx._clear_execution_scope(token)
