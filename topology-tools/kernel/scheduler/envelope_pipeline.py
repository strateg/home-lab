"""Envelope execution and commit pipeline (ADR 0097 / ADR 0063 decomposition).

Runs snapshot-compatible plugins in-process with timeout handling and commits
their execution envelopes through scheduler-owned pipeline state. Commit-time
validation is delegated to the registry EnvelopeValidator; legacy context
synchronization is delegated to context_bridge (D13 shim).
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import TYPE_CHECKING

from ..plugin_base import (
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginExecutionEnvelope,
    PluginResult,
    PluginStatus,
)
from ..plugin_runner import run_plugin_once
from .context_bridge import (
    apply_authoritative_commit_side_effects,
    sync_pipeline_state_to_context,
)

if TYPE_CHECKING:
    from ..pipeline_runtime import PipelineState
    from ..plugin_base import (
        Phase,
        PluginBase,
        PluginContext,
        PluginInputSnapshot,
        Stage,
    )
    from ..registry.envelope_validator import EnvelopeValidator
    from ..specs import PluginSpec

__all__ = [
    "failed_result_with_diagnostics",
    "execute_plugin_envelope_local",
    "is_cross_interpreter_shareability_error",
    "commit_envelope_result",
    "commit_keys_on_failure",
    "apply_result_status_from_diagnostics",
]


def failed_result_with_diagnostics(
    *,
    spec: PluginSpec,
    stage: Stage,
    phase: Phase,
    diagnostics: list[PluginDiagnostic],
) -> PluginResult:
    return PluginResult.failed(
        plugin_id=spec.id,
        api_version=spec.api_version,
        diagnostics=diagnostics,
    )


def execute_plugin_envelope_local(
    *,
    plugin: PluginBase,
    plugin_id: str,
    spec: PluginSpec,
    stage: Stage,
    phase: Phase,
    snapshot: PluginInputSnapshot,
    timeout: float,
) -> PluginExecutionEnvelope:
    """Run one snapshot-compatible plugin in-process with timeout handling."""
    start_time = time.perf_counter()
    timed_out = False
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(run_plugin_once, snapshot=snapshot, plugin=plugin)
        try:
            envelope = future.result(timeout=timeout)
            envelope.result.duration_ms = (time.perf_counter() - start_time) * 1000
            return envelope
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
                    message=f"Plugin exceeded timeout of {timeout}s",
                    path="kernel",
                    plugin_id="kernel",
                )
            )
            return PluginExecutionEnvelope(result=result)
    finally:
        executor.shutdown(wait=not timed_out, cancel_futures=True)


def is_cross_interpreter_shareability_error(exc: Exception) -> bool:
    message = str(exc)
    return "NotShareableError" in message or "does not support cross-interpreter data" in message


def commit_envelope_result(
    *,
    ctx: PluginContext,
    pipeline_state: PipelineState,
    spec: PluginSpec,
    stage: Stage,
    phase: Phase,
    envelope: PluginExecutionEnvelope,
    contract_warnings: bool,
    contract_errors: bool,
    envelope_validator: EnvelopeValidator,
) -> PluginResult:
    """Validate and commit an execution envelope through main-interpreter state."""
    result = envelope.result
    validation_diags = envelope_validator.validate_for_commit(
        spec=spec,
        stage=stage,
        phase=phase,
        envelope=envelope,
        emit_warnings=contract_warnings,
        undeclared_as_errors=contract_errors,
    )
    if validation_diags:
        result.diagnostics.extend(validation_diags)
        apply_result_status_from_diagnostics(result)

    envelope_to_commit = envelope
    if result.status in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}:
        pass
    elif (
        result.status == PluginStatus.FAILED
        and result.error_traceback is None
        and not any(diag.severity == "error" for diag in validation_diags)
    ):
        failure_commit_keys = commit_keys_on_failure(spec)
        if not failure_commit_keys:
            return result
        filtered_messages = [
            message for message in envelope.published_messages if message.key in failure_commit_keys
        ]
        if not filtered_messages:
            return result
        envelope_to_commit = PluginExecutionEnvelope(
            result=result,
            published_messages=filtered_messages,
            execution_metadata=envelope.execution_metadata,
        )
    else:
        return result

    try:
        pipeline_state.commit_envelope(
            plugin_id=spec.id,
            stage=stage,
            phase=phase,
            produces=spec.produces,
            envelope=envelope_to_commit,
        )
    except PluginDataExchangeError as exc:
        result.diagnostics.append(
            PluginDiagnostic(
                code="E8005",
                severity="error",
                stage=stage.value,
                phase=phase.value,
                message=str(exc),
                path=f"plugin:{spec.id}",
                plugin_id="kernel",
            )
        )
        apply_result_status_from_diagnostics(result)
        return result

    sync_pipeline_state_to_context(ctx, pipeline_state)
    apply_authoritative_commit_side_effects(ctx=ctx, pipeline_state=pipeline_state, spec=spec)
    return result


def commit_keys_on_failure(spec: PluginSpec) -> set[str]:
    """Return declared output keys that may be committed from non-crash failures.

    This is a narrow compatibility mechanism for verdict-style outputs such as
    verification booleans that downstream plugins need even when the producer
    reports diagnostics and therefore returns FAILED.
    """
    config = getattr(spec, "config", {})
    if not isinstance(config, dict):
        return set()
    raw = config.get("commit_keys_on_failure")
    if not isinstance(raw, list):
        return set()
    declared = {
        item.get("key")
        for item in spec.produces
        if isinstance(item, dict) and isinstance(item.get("key"), str) and item.get("key")
    }
    return {item.strip() for item in raw if isinstance(item, str) and item.strip() in declared}


def apply_result_status_from_diagnostics(result: PluginResult) -> None:
    if result.status not in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}:
        return
    has_errors = any(diag.severity == "error" for diag in result.diagnostics)
    has_warnings = any(diag.severity == "warning" for diag in result.diagnostics)
    if has_errors:
        result.status = PluginStatus.FAILED
    elif has_warnings:
        result.status = PluginStatus.PARTIAL
