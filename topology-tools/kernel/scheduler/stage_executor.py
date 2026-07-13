"""Stage executor: full-stage plugin orchestration (S6).

Executes all phases of one pipeline stage: when-predicate filtering with
I4013 skip results, preflight gates (model-version and capability guards),
sequential and wavefront-parallel phase execution, fail-fast handling with
guaranteed FINALIZE, stage failure context recording, and the `finally`
invariants (stage-local invalidation, pipeline-state sync, stage_end
trace event).

The executor calls back into the registry facade through the `host`
parameter (bound methods), preserving the runtime-test patch points on
registry instances (host-surface normalization done in S9: unused facade
delegates removed, tests target the scheduler module APIs directly).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol

from ..pipeline_runtime import PipelineState
from ..plugin_base import (
    Phase,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    PluginStatus,
)
from ..registry import PHASE_ORDER
from ..specs import KERNEL_API_VERSION

if TYPE_CHECKING:
    from ..plugin_base import (
        PluginContext,
        PluginExecutionEnvelope,
        PluginInputSnapshot,
        Stage,
    )
    from ..specs import PluginSpec

__all__ = ["StageExecutionHost", "execute_stage"]


class StageExecutionHost(Protocol):
    """Registry facade surface required by execute_stage (transitional)."""

    specs: dict[str, PluginSpec]
    _results: list[PluginResult]

    def get_execution_order(self, stage: Stage, profile: Optional[str] = None, phase: Phase = Phase.RUN) -> list[str]: ...

    def _trace_event(
        self,
        *,
        event: str,
        stage: Stage,
        phase: Phase | None = None,
        plugin_id: str | None = None,
        status: Any = None,
        message: str | None = None,
    ) -> None: ...

    def _ensure_pipeline_state(self, ctx: PluginContext) -> PipelineState: ...

    def _when_predicates_allow(self, spec: PluginSpec, ctx: PluginContext) -> bool: ...

    def _validate_model_versions(
        self,
        stage: Stage,
        ctx: PluginContext,
        active_plugin_ids: list[str],
    ) -> list[PluginDiagnostic]: ...

    def _validate_required_capabilities(
        self,
        stage: Stage,
        ctx: PluginContext,
        profile: Optional[str],
        active_plugin_ids: list[str],
    ) -> list[PluginDiagnostic]: ...

    def _preload_plugins(self, plugin_ids: list[str]) -> None: ...

    def _execute_phase_parallel(
        self,
        *,
        stage: Stage,
        phase: Phase,
        ctx: PluginContext,
        plugin_ids: list[str],
        trace_execution: bool = False,
        contract_warnings: bool = False,
        contract_errors: bool = False,
    ) -> list[PluginResult]: ...

    def execute_plugin(
        self,
        plugin_id: str,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase = Phase.RUN,
        *,
        contract_warnings: bool = False,
        contract_errors: bool = False,
    ) -> PluginResult: ...

    def _mirror_context_into_pipeline_state(self, ctx: PluginContext, pipeline_state: PipelineState) -> None: ...

    def _sync_pipeline_state_to_context(self, ctx: PluginContext, pipeline_state: PipelineState) -> None: ...

    def _build_input_snapshot(
        self,
        *,
        plugin_id: str,
        stage: Stage,
        phase: Phase,
        ctx: PluginContext,
        pipeline_state: PipelineState,
    ) -> PluginInputSnapshot: ...

    def _validate_required_consumes_snapshot(
        self,
        *,
        spec: PluginSpec,
        snapshot: PluginInputSnapshot,
        stage: Stage,
        phase: Phase,
    ) -> list[PluginDiagnostic]: ...

    def _failed_result_with_diagnostics(
        self,
        *,
        spec: PluginSpec,
        stage: Stage,
        phase: Phase,
        diagnostics: list[PluginDiagnostic],
    ) -> PluginResult: ...

    def _execute_plugin_envelope_local(
        self,
        *,
        plugin_id: str,
        spec: PluginSpec,
        stage: Stage,
        phase: Phase,
        snapshot: PluginInputSnapshot,
        timeout: float,
    ) -> PluginExecutionEnvelope: ...

    def _commit_envelope_result(
        self,
        *,
        ctx: PluginContext,
        pipeline_state: PipelineState,
        spec: PluginSpec,
        stage: Stage,
        phase: Phase,
        envelope: PluginExecutionEnvelope,
        contract_warnings: bool,
        contract_errors: bool,
    ) -> PluginResult: ...


def execute_stage(
    *,
    host: StageExecutionHost,
    stage: Stage,
    ctx: PluginContext,
    profile: Optional[str] = None,
    fail_fast: bool = False,
    parallel_plugins: bool = False,
    trace_execution: bool = False,
    contract_warnings: bool = False,
    contract_errors: bool = False,
) -> list[PluginResult]:
    """Execute all plugins for a stage.

    Args:
        host: Registry facade providing plugin state and execution helpers
        stage: Pipeline stage to execute
        ctx: Execution context
        profile: Current execution profile
        fail_fast: Stop on first failure
        parallel_plugins: Enable parallel execution within each stage/phase
        trace_execution: Record stage/phase/plugin execution trace events
        contract_warnings: Emit transitional W800x warnings for undeclared produces/consumes
        contract_errors: Treat undeclared produces/consumes as hard errors (Wave H style)

    Returns:
        List of PluginResult for each executed plugin
    """
    results: list[PluginResult] = []
    phase_plugin_ids: dict[Phase, list[str]] = {
        phase: host.get_execution_order(stage, profile, phase=phase) for phase in PHASE_ORDER
    }
    ordered_plugin_ids = [plugin_id for phase in PHASE_ORDER for plugin_id in phase_plugin_ids[phase]]

    if not ordered_plugin_ids:
        return results

    if trace_execution:
        host._trace_event(
            event="stage_start",
            stage=stage,
            message=f"plugins={len(ordered_plugin_ids)} parallel={parallel_plugins}",
        )

    invalidated_stage_local: list[str] = []
    try:
        pipeline_state = host._ensure_pipeline_state(ctx)
        stage_failure_context: list[dict[str, Any]] = []
        ctx.config["stage_failure_context"] = stage_failure_context

        def _record_stage_failure(result: PluginResult, *, phase: Phase) -> None:
            if result.status not in {PluginStatus.FAILED, PluginStatus.TIMEOUT}:
                return
            diagnostics_payload: list[dict[str, Any]] = []
            diag_codes = [
                diag.code
                for diag in result.diagnostics
                if isinstance(diag, PluginDiagnostic) and isinstance(diag.code, str) and diag.code
            ]
            for diag in result.diagnostics:
                if not isinstance(diag, PluginDiagnostic):
                    continue
                diagnostics_payload.append(
                    {
                        "code": diag.code,
                        "severity": diag.severity,
                        "phase": diag.phase,
                        "message": diag.message,
                        "path": diag.path,
                        "plugin_id": diag.plugin_id,
                    }
                )
            stage_failure_context.append(
                {
                    "plugin_id": result.plugin_id,
                    "status": result.status.value,
                    "phase": phase.value,
                    "diagnostic_codes": diag_codes,
                    "diagnostics": diagnostics_payload,
                }
            )

        when_allowed_by_plugin: dict[str, bool] = {}
        for plugin_id in ordered_plugin_ids:
            spec = host.specs.get(plugin_id)
            if spec is None:
                when_allowed_by_plugin[plugin_id] = False
                continue
            when_allowed_by_plugin[plugin_id] = host._when_predicates_allow(spec, ctx)

        active_plugin_ids = [
            plugin_id for plugin_id in ordered_plugin_ids if when_allowed_by_plugin.get(plugin_id, False)
        ]

        # Model version validation (scheduler.preflight via host delegate)
        model_version_diags = host._validate_model_versions(stage, ctx, active_plugin_ids)
        if model_version_diags:
            result = PluginResult.failed(
                plugin_id="kernel.model_version_guard",
                api_version=KERNEL_API_VERSION,
                diagnostics=model_version_diags,
            )
            results.append(result)
            host._results.append(result)
            return results

        # Capability validation (scheduler.preflight via host delegate)
        capability_diags = host._validate_required_capabilities(stage, ctx, profile, active_plugin_ids)
        if capability_diags:
            result = PluginResult.failed(
                plugin_id="kernel.capability_guard",
                api_version=KERNEL_API_VERSION,
                diagnostics=capability_diags,
            )
            results.append(result)
            host._results.append(result)
            return results

        if parallel_plugins:
            host._preload_plugins(active_plugin_ids)

        fail_fast_triggered = False
        for phase in PHASE_ORDER:
            if fail_fast_triggered and phase is not Phase.FINALIZE:
                continue

            if trace_execution:
                host._trace_event(event="phase_start", stage=stage, phase=phase)

            phase_active_plugin_ids: list[str] = []
            for plugin_id in phase_plugin_ids[phase]:
                spec = host.specs.get(plugin_id)
                if spec is None:
                    continue

                if not when_allowed_by_plugin.get(plugin_id, False):
                    skipped = PluginResult.skipped(
                        plugin_id=plugin_id,
                        api_version=spec.api_version,
                        reason=f"when predicate evaluated to false for phase '{phase.value}'",
                    )
                    skipped.diagnostics.append(
                        PluginDiagnostic(
                            code="I4013",
                            severity="info",
                            stage=stage.value,
                            phase=phase.value,
                            message=f"Plugin '{plugin_id}' skipped by when predicates.",
                            path=f"plugin:{plugin_id}",
                            plugin_id="kernel",
                        )
                    )
                    results.append(skipped)
                    host._results.append(skipped)
                    if trace_execution:
                        host._trace_event(
                            event="plugin_result",
                            stage=stage,
                            phase=phase,
                            plugin_id=plugin_id,
                            status=skipped.status,
                            message="when=false",
                        )
                    continue

                phase_active_plugin_ids.append(plugin_id)

            if not phase_active_plugin_ids:
                continue

            use_parallel_phase_executor = parallel_plugins and not fail_fast and len(phase_active_plugin_ids) > 1
            if use_parallel_phase_executor:
                phase_results = host._execute_phase_parallel(
                    stage=stage,
                    phase=phase,
                    ctx=ctx,
                    plugin_ids=phase_active_plugin_ids,
                    trace_execution=trace_execution,
                    contract_warnings=contract_warnings,
                    contract_errors=contract_errors,
                )
                results.extend(phase_results)
                for phase_result in phase_results:
                    _record_stage_failure(phase_result, phase=phase)
                continue

            for plugin_id in phase_active_plugin_ids:
                if trace_execution:
                    host._trace_event(event="plugin_start", stage=stage, phase=phase, plugin_id=plugin_id)
                spec = host.specs[plugin_id]
                # ADR 0097 PR2: Route based on execution_mode
                if spec.execution_mode == "thread_legacy":
                    # Legacy path: direct execute_plugin() with context merge-back
                    result = host.execute_plugin(
                        plugin_id,
                        ctx,
                        stage,
                        phase=phase,
                        contract_warnings=contract_warnings,
                        contract_errors=contract_errors,
                    )
                    host._mirror_context_into_pipeline_state(ctx, pipeline_state)
                else:
                    # Envelope path: both subinterpreter and main_interpreter modes
                    try:
                        snapshot = host._build_input_snapshot(
                            plugin_id=plugin_id,
                            stage=stage,
                            phase=phase,
                            ctx=ctx,
                            pipeline_state=pipeline_state,
                        )
                    except PluginDataExchangeError as exc:
                        result = PluginResult.failed(
                            plugin_id=plugin_id,
                            api_version=spec.api_version,
                            diagnostics=[
                                PluginDiagnostic(
                                    code="E8003",
                                    severity="error",
                                    stage=stage.value,
                                    phase=phase.value,
                                    message=str(exc),
                                    path=f"plugin:{plugin_id}:snapshot",
                                    plugin_id="kernel",
                                )
                            ],
                        )
                    else:
                        required_consume_diags = host._validate_required_consumes_snapshot(
                            spec=spec,
                            snapshot=snapshot,
                            stage=stage,
                            phase=phase,
                        )
                        if required_consume_diags:
                            result = host._failed_result_with_diagnostics(
                                spec=spec,
                                stage=stage,
                                phase=phase,
                                diagnostics=required_consume_diags,
                            )
                        else:
                            envelope = host._execute_plugin_envelope_local(
                                plugin_id=plugin_id,
                                spec=spec,
                                stage=stage,
                                phase=phase,
                                snapshot=snapshot,
                                timeout=spec.timeout,
                            )
                            result = host._commit_envelope_result(
                                ctx=ctx,
                                pipeline_state=pipeline_state,
                                spec=spec,
                                stage=stage,
                                phase=phase,
                                envelope=envelope,
                                contract_warnings=contract_warnings,
                                contract_errors=contract_errors,
                            )
                results.append(result)
                _record_stage_failure(result, phase=phase)
                if trace_execution:
                    host._trace_event(
                        event="plugin_result",
                        stage=stage,
                        phase=phase,
                        plugin_id=plugin_id,
                        status=result.status,
                    )

                if (
                    fail_fast
                    and phase is not Phase.FINALIZE
                    and result.status in (PluginStatus.FAILED, PluginStatus.TIMEOUT)
                ):
                    fail_fast_triggered = True
                    break

        return results
    finally:
        pipeline_state = getattr(ctx, "_pipeline_state", None)
        if isinstance(pipeline_state, PipelineState):
            invalidated_stage_local = pipeline_state.invalidate_stage_local_data(stage)
            host._sync_pipeline_state_to_context(ctx, pipeline_state)
        else:
            invalidated_stage_local = ctx.invalidate_stage_local_data(stage)
        if trace_execution:
            suffix = f"invalidated_stage_local={len(invalidated_stage_local)}"
            host._trace_event(event="stage_end", stage=stage, message=suffix)
