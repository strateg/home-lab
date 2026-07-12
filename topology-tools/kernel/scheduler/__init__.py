"""Plugin scheduler submodules (ADR 0063 decomposition).

This package provides modular components for plugin execution scheduling:

- execution_planner: Plan plugin execution order and filtering
- parallel_executor: Execute plugins in parallel with subinterpreters
- snapshot_builder: Build input snapshots for isolated execution
- context_bridge: PipelineState <-> legacy PluginContext shim (D13 quarantine)
- envelope_pipeline: Local envelope execution and commit pipeline
- phase_executor: Wavefront-parallel execution of one pipeline phase
- stage_executor: Full-stage plugin orchestration
- preflight: Model-version and capability gates (E4010/E4011/E4012)

Usage:
    from kernel.scheduler import ExecutionPlanner, ParallelExecutor
    from kernel.scheduler import SnapshotBuilder, SerializablePluginSpec
"""

from __future__ import annotations

from .context_bridge import (
    apply_authoritative_commit_side_effects,
    ensure_pipeline_state,
    mirror_context_into_pipeline_state,
    sync_pipeline_state_to_context,
)
from .envelope_pipeline import (
    apply_result_status_from_diagnostics,
    commit_envelope_result,
    commit_keys_on_failure,
    execute_plugin_envelope_local,
    failed_result_with_diagnostics,
    is_cross_interpreter_shareability_error,
)
from .execution_planner import ExecutionPlanner, PlanningError
from .parallel_executor import (
    HAS_REAL_SUBINTERPRETERS,
    compute_wavefronts,
    execute_plugin_isolated,
    get_parallel_executor,
)
from .snapshot_builder import SerializablePluginSpec, SnapshotBuilder

__all__ = [
    # execution_planner
    "ExecutionPlanner",
    "PlanningError",
    # parallel_executor
    "compute_wavefronts",
    "execute_plugin_isolated",
    "get_parallel_executor",
    "HAS_REAL_SUBINTERPRETERS",
    # snapshot_builder
    "SnapshotBuilder",
    "SerializablePluginSpec",
    # context_bridge (D13 shim)
    "ensure_pipeline_state",
    "mirror_context_into_pipeline_state",
    "sync_pipeline_state_to_context",
    "apply_authoritative_commit_side_effects",
    # envelope_pipeline
    "failed_result_with_diagnostics",
    "execute_plugin_envelope_local",
    "is_cross_interpreter_shareability_error",
    "commit_envelope_result",
    "commit_keys_on_failure",
    "apply_result_status_from_diagnostics",
]
