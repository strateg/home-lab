"""Legacy thread-path plugin execution (S7, ADR 0097 D13 quarantine).

QUARANTINED COMPATIBILITY CODE - delete together with the thread_legacy
execution mode (ADR 0097 D13). New code must use the envelope path
(scheduler.envelope_pipeline / scheduler.phase_executor).

This module contains the pre-envelope execution model moved verbatim from
the plugin_registry facade (PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07
S7, no behavior change):

- execute_plugin: direct in-context plugin execution in a single-worker
  ThreadPoolExecutor with timeout (E4102), execution-scope tokens, and
  context merge-back semantics
- attach_data_bus_contract_diagnostics: post-hoc W800x/E800x data-bus
  contract diagnostics derived from live context publish/subscribe event
  streams (the envelope path validates proposals before commit instead)

The functions call back into the registry facade through the `host`
parameter (bound methods), preserving the runtime-test patch points on
registry instances (host-surface normalization done in S9: unused facade
delegates removed, tests target the scheduler module APIs directly).
"""

from __future__ import annotations

import concurrent.futures
import contextvars
import time
import traceback
from typing import TYPE_CHECKING, Any, Optional, Protocol

from ..plugin_base import (
    Phase,
    PluginDiagnostic,
    PluginExecutionScope,
    PluginResult,
)
from ..registry import ConfigValidationError, PluginLoadError

if TYPE_CHECKING:
    from ..plugin_base import PluginBase, PluginContext, Stage
    from ..specs import PluginSpec

__all__ = ["LegacyExecutionHost", "attach_data_bus_contract_diagnostics", "execute_plugin"]


class LegacyExecutionHost(Protocol):
    """Registry facade surface required by the legacy execution path (transitional)."""

    specs: dict[str, PluginSpec]
    _results: list[PluginResult]

    def load_plugin(self, plugin_id: str) -> PluginBase: ...

    def _validate_required_consumes_pre_run(
        self,
        *,
        spec: PluginSpec,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase,
    ) -> list[PluginDiagnostic]: ...

    def _attach_data_bus_contract_diagnostics(
        self,
        *,
        spec: PluginSpec,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase,
        result: PluginResult,
        publish_event_start: int,
        subscribe_event_start: int,
        emit_warnings: bool,
        undeclared_as_errors: bool,
    ) -> None: ...

    def _schema_ref_by_produced_key(self, spec: PluginSpec) -> dict[str, str]: ...

    def _schema_ref_by_consumed_key(self, spec: PluginSpec) -> dict[tuple[str, str], str]: ...

    def _declared_consumes(self, spec: PluginSpec) -> set[tuple[str, str]]: ...

    def _validate_schema_ref_payload(
        self,
        *,
        result: PluginResult,
        stage: Stage,
        phase: Phase,
        spec: PluginSpec,
        payload: Any,
        schema_ref: str,
        path_suffix: str,
    ) -> None: ...

    def _apply_result_status_from_diagnostics(self, result: PluginResult) -> None: ...


def attach_data_bus_contract_diagnostics(
    *,
    host: LegacyExecutionHost,
    spec: PluginSpec,
    ctx: PluginContext,
    stage: Stage,
    phase: Phase,
    result: PluginResult,
    publish_event_start: int,
    subscribe_event_start: int,
    emit_warnings: bool,
    undeclared_as_errors: bool,
) -> None:
    """Attach W800x/E800x data-bus contract diagnostics from live context events."""
    publish_events = ctx._get_publish_events_since(
        publish_event_start,
        plugin_id=spec.id,
        stage=stage,
        phase=phase,
    )
    subscribe_events = ctx._get_subscribe_events_since(
        subscribe_event_start,
        plugin_id=spec.id,
        stage=stage,
        phase=phase,
    )
    published_payloads = ctx.get_published_data()
    produce_schema_refs = host._schema_ref_by_produced_key(spec)
    consume_schema_refs = host._schema_ref_by_consumed_key(spec)

    if publish_events and (emit_warnings or undeclared_as_errors):
        declared_produces = {key for key in spec.declared_produced_scopes()}
        published_keys = sorted({event.key for event in publish_events})
        warning_severity = "error" if undeclared_as_errors else "warning"
        warning_code = "E8004" if undeclared_as_errors else "W8001"
        warning_code_undeclared = "E8005" if undeclared_as_errors else "W8002"
        if not declared_produces:
            result.diagnostics.append(
                PluginDiagnostic(
                    code=warning_code,
                    severity=warning_severity,
                    stage=stage.value,
                    phase=phase.value,
                    message=(
                        f"Plugin '{spec.id}' published keys {published_keys} "
                        "without manifest produces declaration."
                    ),
                    path=f"plugin:{spec.id}",
                    plugin_id="kernel",
                )
            )
        else:
            undeclared_publish = sorted(key for key in published_keys if key not in declared_produces)
            if undeclared_publish:
                result.diagnostics.append(
                    PluginDiagnostic(
                        code=warning_code_undeclared,
                        severity=warning_severity,
                        stage=stage.value,
                        phase=phase.value,
                        message=(
                            f"Plugin '{spec.id}' published undeclared keys {undeclared_publish}. "
                            "Declare them under produces[]."
                        ),
                        path=f"plugin:{spec.id}",
                        plugin_id="kernel",
                    )
                )

    if subscribe_events and (emit_warnings or undeclared_as_errors):
        declared_consumes = host._declared_consumes(spec)
        consumed_pairs = {(event.from_plugin, event.key) for event in subscribe_events}
        consumed_keys = sorted(f"{from_plugin}.{key}" for from_plugin, key in consumed_pairs)
        warning_severity = "error" if undeclared_as_errors else "warning"
        warning_code = "E8006" if undeclared_as_errors else "W8003"
        warning_code_undeclared = "E8007" if undeclared_as_errors else "W8004"
        if not declared_consumes:
            result.diagnostics.append(
                PluginDiagnostic(
                    code=warning_code,
                    severity=warning_severity,
                    stage=stage.value,
                    phase=phase.value,
                    message=(
                        f"Plugin '{spec.id}' consumed keys {consumed_keys} "
                        "without manifest consumes declaration."
                    ),
                    path=f"plugin:{spec.id}",
                    plugin_id="kernel",
                )
            )
        else:
            undeclared_consume = sorted(
                f"{from_plugin}.{key}"
                for from_plugin, key in consumed_pairs
                if (from_plugin, key) not in declared_consumes
            )
            if undeclared_consume:
                result.diagnostics.append(
                    PluginDiagnostic(
                        code=warning_code_undeclared,
                        severity=warning_severity,
                        stage=stage.value,
                        phase=phase.value,
                        message=(
                            f"Plugin '{spec.id}' consumed undeclared keys {undeclared_consume}. "
                            "Declare them under consumes[]."
                        ),
                        path=f"plugin:{spec.id}",
                        plugin_id="kernel",
                    )
                )

    for key in sorted({event.key for event in publish_events}):
        schema_ref = produce_schema_refs.get(key)
        if schema_ref is None:
            continue
        payload = published_payloads.get(spec.id, {}).get(key)
        host._validate_schema_ref_payload(
            result=result,
            stage=stage,
            phase=phase,
            spec=spec,
            payload=payload,
            schema_ref=schema_ref,
            path_suffix=f"produces.{key}",
        )

    for from_plugin, key in sorted({(event.from_plugin, event.key) for event in subscribe_events}):
        schema_ref = consume_schema_refs.get((from_plugin, key))
        if schema_ref is None:
            continue
        payload = published_payloads.get(from_plugin, {}).get(key)
        host._validate_schema_ref_payload(
            result=result,
            stage=stage,
            phase=phase,
            spec=spec,
            payload=payload,
            schema_ref=schema_ref,
            path_suffix=f"consumes.{from_plugin}.{key}",
        )

    host._apply_result_status_from_diagnostics(result)


def execute_plugin(
    *,
    host: LegacyExecutionHost,
    plugin_id: str,
    ctx: PluginContext,
    stage: Stage,
    phase: Phase = Phase.RUN,
    timeout: Optional[float] = None,
    record_result: bool = True,
    contract_warnings: bool = False,
    contract_errors: bool = False,
) -> PluginResult:
    """Execute a single plugin with timeout and error handling (legacy path).

    Args:
        host: Registry facade providing plugin state and helpers
        plugin_id: Plugin ID to execute
        ctx: Execution context
        stage: Current pipeline stage
        phase: Current pipeline phase
        timeout: Timeout in seconds (uses plugin spec timeout if None)
        record_result: Append the result to host._results
        contract_warnings: Emit transitional W800x contract warnings
        contract_errors: Treat undeclared produces/consumes as hard errors

    Returns:
        PluginResult with execution status and diagnostics
    """
    if plugin_id not in host.specs:
        return PluginResult.failed(
            plugin_id=plugin_id,
            diagnostics=[
                PluginDiagnostic(
                    code="E4004",
                    severity="error",
                    stage=stage.value,
                    phase=phase.value,
                    message=f"Plugin not found: {plugin_id}",
                    path="kernel",
                    plugin_id="kernel",
                )
            ],
        )

    spec = host.specs[plugin_id]
    effective_timeout = timeout if timeout is not None else spec.timeout

    # Runtime config already present in ctx.config takes precedence over manifest defaults.
    base_config = ctx.config.copy()
    scoped_config = {**spec.config, **base_config}
    produced_key_scopes = spec.declared_produced_scopes()
    scope = PluginExecutionScope(
        plugin_id=plugin_id,
        allowed_dependencies=frozenset(spec.declared_dependency_ids()),
        phase=phase,
        config=scoped_config,
        stage=stage,
        produced_key_scopes=produced_key_scopes,
    )

    try:
        plugin = host.load_plugin(plugin_id)
    except (PluginLoadError, ConfigValidationError) as e:
        return PluginResult.failed(
            plugin_id=plugin_id,
            api_version=spec.api_version,
            diagnostics=[
                PluginDiagnostic(
                    code="E4004",
                    severity="error",
                    stage=stage.value,
                    phase=phase.value,
                    message=str(e),
                    path="kernel",
                    plugin_id="kernel",
                )
            ],
        )

    scope_token = ctx._set_execution_scope(scope)
    execution_context = contextvars.copy_context()
    publish_event_start = ctx._get_publish_event_count()
    subscribe_event_start = ctx._get_subscribe_event_count()
    required_consume_diags = host._validate_required_consumes_pre_run(
        spec=spec,
        ctx=ctx,
        stage=stage,
        phase=phase,
    )
    if required_consume_diags:
        failed = PluginResult.failed(
            plugin_id=plugin_id,
            api_version=spec.api_version,
            diagnostics=required_consume_diags,
        )
        if record_result:
            host._results.append(failed)
        ctx._clear_execution_scope(scope_token)
        return failed

    # Execute with timeout
    start_time = time.perf_counter()
    timed_out = False
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    try:
        future = executor.submit(execution_context.run, plugin.execute_phase, ctx, stage, phase)
        try:
            result = future.result(timeout=effective_timeout)
            duration_ms = (time.perf_counter() - start_time) * 1000
            # Update duration in result
            result.duration_ms = duration_ms
            host._attach_data_bus_contract_diagnostics(
                spec=spec,
                ctx=ctx,
                stage=stage,
                phase=phase,
                result=result,
                publish_event_start=publish_event_start,
                subscribe_event_start=subscribe_event_start,
                emit_warnings=contract_warnings,
                undeclared_as_errors=contract_errors,
            )
            if record_result:
                host._results.append(result)
            return result
        except concurrent.futures.TimeoutError:
            timed_out = True
            future.cancel()
            duration_ms = (time.perf_counter() - start_time) * 1000
            result = PluginResult.timeout(
                plugin_id=plugin_id,
                api_version=spec.api_version,
                duration_ms=duration_ms,
            )
            result.diagnostics.append(
                PluginDiagnostic(
                    code="E4102",
                    severity="error",
                    stage=stage.value,
                    phase=phase.value,
                    message=f"Plugin exceeded timeout of {effective_timeout}s",
                    path="kernel",
                    plugin_id="kernel",
                )
            )
            host._attach_data_bus_contract_diagnostics(
                spec=spec,
                ctx=ctx,
                stage=stage,
                phase=phase,
                result=result,
                publish_event_start=publish_event_start,
                subscribe_event_start=subscribe_event_start,
                emit_warnings=contract_warnings,
                undeclared_as_errors=contract_errors,
            )
            if record_result:
                host._results.append(result)
            return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        tb = traceback.format_exc()
        result = PluginResult.failed(
            plugin_id=plugin_id,
            api_version=spec.api_version,
            duration_ms=duration_ms,
            error_traceback=tb,
            diagnostics=[
                PluginDiagnostic(
                    code="E4102",
                    severity="error",
                    stage=stage.value,
                    phase=phase.value,
                    message=f"Plugin crashed: {e}",
                    path="kernel",
                    plugin_id="kernel",
                )
            ],
        )
        host._attach_data_bus_contract_diagnostics(
            spec=spec,
            ctx=ctx,
            stage=stage,
            phase=phase,
            result=result,
            publish_event_start=publish_event_start,
            subscribe_event_start=subscribe_event_start,
            emit_warnings=contract_warnings,
            undeclared_as_errors=contract_errors,
        )
        if record_result:
            host._results.append(result)
        return result
    finally:
        # Do not wait for timed-out plugins; this avoids blocking the pipeline
        # after we already returned TIMEOUT.
        executor.shutdown(wait=not timed_out, cancel_futures=True)
        ctx._clear_execution_scope(scope_token)
