"""Phase executor: wavefront-parallel execution of one pipeline phase (S5).

Executes one (stage, phase) plugin set in dependency-respecting wavefronts
computed by `parallel_executor.compute_wavefronts` (the single wavefront
implementation, ADR 0063 §6). Routing per plugin follows ADR 0097 PR2
execution modes: subinterpreter pool, main-interpreter inline envelope,
or the thread_legacy compatibility path.

The executor calls back into the registry facade through the `host`
parameter (bound methods), preserving the runtime-test patch points on
registry instances. `has_real_subinterpreters` and `isolated_worker` are
passed explicitly per call, so callers (including tests) control routing
without patching module globals (host-surface normalization done in S9).
"""

from __future__ import annotations

import concurrent.futures
import traceback
from typing import TYPE_CHECKING, Any, Callable, Protocol

from ..plugin_base import (
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
)
from .parallel_executor import compute_wavefronts
from .snapshot_builder import SerializablePluginSpec

if TYPE_CHECKING:
    from pathlib import Path

    from ..pipeline_runtime import PipelineState
    from ..plugin_base import (
        Phase,
        PluginContext,
        PluginExecutionEnvelope,
        PluginInputSnapshot,
        Stage,
    )
    from ..specs import PluginSpec

__all__ = ["PhaseExecutionHost", "execute_phase_parallel"]


class PhaseExecutionHost(Protocol):
    """Registry facade surface required by execute_phase_parallel (transitional)."""

    specs: dict[str, PluginSpec]
    base_path: Path

    def _plugin_sort_key(self, plugin_id: str) -> tuple[int, str]: ...

    def _get_parallel_executor(self, max_workers: int) -> Any: ...

    def validate_plugin_config(self, plugin_id: str) -> list[str]: ...

    def execute_plugin(
        self,
        plugin_id: str,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase,
        timeout: float | None,
        *,
        record_result: bool = True,
        contract_warnings: bool = False,
        contract_errors: bool = False,
    ) -> PluginResult: ...

    def _ensure_pipeline_state(self, ctx: PluginContext) -> PipelineState: ...

    def _mirror_context_into_pipeline_state(self, ctx: PluginContext, pipeline_state: PipelineState) -> None: ...

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

    def _is_cross_interpreter_shareability_error(self, exc: Exception) -> bool: ...


def execute_phase_parallel(
    *,
    host: PhaseExecutionHost,
    stage: Stage,
    phase: Phase,
    ctx: PluginContext,
    plugin_ids: list[str],
    trace_execution: bool = False,
    contract_warnings: bool = False,
    contract_errors: bool = False,
    has_real_subinterpreters: bool,
    isolated_worker: Callable[..., PluginExecutionEnvelope],
) -> list[PluginResult]:
    """Execute one phase in dependency-respecting wavefronts."""
    if not plugin_ids:
        return []

    pipeline_state = host._ensure_pipeline_state(ctx)
    plugin_set = set(plugin_ids)

    results_by_plugin: dict[str, PluginResult] = {}
    max_workers = min(8, max(1, len(plugin_ids)))

    # ADR 0097 Wave 5: Always use subinterpreters (Python 3.14+ required)
    executor = host._get_parallel_executor(max_workers)

    # ADR 0097: Pre-validate all plugin configs before parallel submission
    # Validates upfront to fail fast and avoid wasted subinterpreter spawning
    config_validation_failed: dict[str, list[str]] = {}
    for plugin_id in plugin_ids:
        errors = host.validate_plugin_config(plugin_id)
        if errors:
            config_validation_failed[plugin_id] = errors

    # Create early failures for invalid configs; these plugins never execute
    # and their dependents stay blocked (no result recorded for dependents).
    for plugin_id, errors in config_validation_failed.items():
        spec = host.specs.get(plugin_id)
        if spec is None:
            continue
        results_by_plugin[plugin_id] = PluginResult.failed(
            plugin_id=plugin_id,
            api_version=spec.api_version,
            diagnostics=[
                PluginDiagnostic(
                    code="E4001",
                    severity="error",
                    stage=stage.value,
                    phase=phase.value,
                    message=f"Config validation failed: {'; '.join(errors)}",
                    path="kernel.config_validation",
                    plugin_id="kernel",
                )
            ],
        )

    wavefronts = compute_wavefronts(plugin_ids, host.specs, host._plugin_sort_key)
    blocked: set[str] = set(config_validation_failed)

    with executor:
        for raw_wavefront in wavefronts:
            wavefront: list[str] = []
            for plugin_id in raw_wavefront:
                # Skip plugins that failed config validation
                if plugin_id in config_validation_failed:
                    continue
                # Skip (and block) plugins depending on a blocked plugin:
                # matches inline behavior where such plugins never became ready.
                spec = host.specs.get(plugin_id)
                dep_ids = spec.depends_on if spec is not None else []
                if any(dep_id in blocked for dep_id in dep_ids if dep_id in plugin_set):
                    blocked.add(plugin_id)
                    continue
                wavefront.append(plugin_id)

            if not wavefront:
                continue  # No valid plugins to execute in this wavefront

            futures: dict[concurrent.futures.Future[PluginExecutionEnvelope], str] = {}
            snapshots_by_plugin: dict[str, PluginInputSnapshot] = {}
            for plugin_id in wavefront:
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
                        phase,
                        None,
                        record_result=False,
                        contract_warnings=contract_warnings,
                        contract_errors=contract_errors,
                    )
                    results_by_plugin[plugin_id] = result
                    host._mirror_context_into_pipeline_state(ctx, pipeline_state)
                    if trace_execution:
                        host._trace_event(
                            event="plugin_result",
                            stage=stage,
                            phase=phase,
                            plugin_id=plugin_id,
                            status=result.status,
                            message="thread_legacy compatibility path",
                        )
                    continue

                try:
                    snapshot = host._build_input_snapshot(
                        plugin_id=plugin_id,
                        stage=stage,
                        phase=phase,
                        ctx=ctx,
                        pipeline_state=pipeline_state,
                    )
                except PluginDataExchangeError as exc:
                    failed = PluginResult.failed(
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
                    results_by_plugin[plugin_id] = failed
                    if trace_execution:
                        host._trace_event(
                            event="plugin_result",
                            stage=stage,
                            phase=phase,
                            plugin_id=plugin_id,
                            status=failed.status,
                            message="snapshot-build failed",
                        )
                    continue

                required_consume_diags = host._validate_required_consumes_snapshot(
                    spec=spec,
                    snapshot=snapshot,
                    stage=stage,
                    phase=phase,
                )
                if required_consume_diags:
                    failed = host._failed_result_with_diagnostics(
                        spec=spec,
                        stage=stage,
                        phase=phase,
                        diagnostics=required_consume_diags,
                    )
                    results_by_plugin[plugin_id] = failed
                    if trace_execution:
                        host._trace_event(
                            event="plugin_result",
                            stage=stage,
                            phase=phase,
                            plugin_id=plugin_id,
                            status=failed.status,
                            message="snapshot preflight failed",
                        )
                    continue

                # ADR 0097 PR2: execution_mode routing
                # - "subinterpreter" + Python 3.14+ → isolated subinterpreter pool
                # - "subinterpreter" + Python <3.14 → ThreadPoolExecutor parallel
                # - "main_interpreter" → inline in main interpreter (no cross-interpreter sharing)
                if spec.execution_mode == "subinterpreter" and has_real_subinterpreters:
                    # Submit to real subinterpreter pool (ADR 0063 Phase 3: delegate to scheduler)
                    snapshots_by_plugin[plugin_id] = snapshot
                    serialized_spec = SerializablePluginSpec.from_plugin_spec(spec)
                    future = executor.submit(
                        isolated_worker,
                        snapshot.__dict__,
                        str(host.base_path),
                        serialized_spec.to_dict(),
                    )
                    futures[future] = plugin_id
                elif spec.execution_mode == "main_interpreter" or has_real_subinterpreters:
                    # Execute inline in main interpreter (ADR 0097 D1: main owns state)
                    # This includes: main_interpreter mode, or subinterpreter fallback on Py3.14+
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
                    results_by_plugin[plugin_id] = result
                    if trace_execution:
                        host._trace_event(
                            event="plugin_result",
                            stage=stage,
                            phase=phase,
                            plugin_id=plugin_id,
                            status=result.status,
                            message="main_interpreter inline execution",
                        )
                else:
                    # Python <3.14: use ThreadPoolExecutor for parallel execution
                    future = executor.submit(
                        host._execute_plugin_envelope_local,
                        plugin_id=plugin_id,
                        spec=spec,
                        stage=stage,
                        phase=phase,
                        snapshot=snapshot,
                        timeout=spec.timeout,
                    )
                    futures[future] = plugin_id

            for future in concurrent.futures.as_completed(futures):
                plugin_id = futures[future]
                spec = host.specs.get(plugin_id)
                if spec is None:
                    continue
                try:
                    envelope = future.result(timeout=spec.timeout if has_real_subinterpreters else None)
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
                    results_by_plugin[plugin_id] = result
                    if trace_execution:
                        host._trace_event(
                            event="plugin_result",
                            stage=stage,
                            phase=phase,
                            plugin_id=plugin_id,
                            status=result.status,
                        )
                except Exception as exc:
                    snapshot = snapshots_by_plugin.get(plugin_id)
                    if snapshot is not None and host._is_cross_interpreter_shareability_error(exc):
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
                        results_by_plugin[plugin_id] = result
                        if trace_execution:
                            host._trace_event(
                                event="plugin_result",
                                stage=stage,
                                phase=phase,
                                plugin_id=plugin_id,
                                status=result.status,
                                message="fallback to local envelope path",
                            )
                        continue
                    failed = PluginResult.failed(
                        plugin_id=plugin_id,
                        api_version=spec.api_version,
                        diagnostics=[
                            PluginDiagnostic(
                                code="E4102",
                                severity="error",
                                stage=stage.value,
                                phase=phase.value,
                                message=f"Plugin crashed in parallel execution: {exc}",
                                path="kernel",
                                plugin_id="kernel",
                            )
                        ],
                        error_traceback=traceback.format_exc(),
                    )
                    results_by_plugin[plugin_id] = failed
                    if trace_execution:
                        host._trace_event(
                            event="plugin_result",
                            stage=stage,
                            phase=phase,
                            plugin_id=plugin_id,
                            status=failed.status,
                            message=str(exc),
                        )

    return [results_by_plugin[plugin_id] for plugin_id in plugin_ids if plugin_id in results_by_plugin]
