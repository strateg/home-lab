"""Plugin parallel executor (ADR 0063 registry decomposition).

This module handles parallel plugin execution with subinterpreters:
the isolated worker entry point, subinterpreter pool creation, and the
single wavefront computation implementation.
"""

from __future__ import annotations

import heapq
import sys
from typing import TYPE_CHECKING, Any, Callable

from ..plugin_base import PluginExecutionEnvelope

if TYPE_CHECKING:
    from ..specs import PluginSpec

__all__ = [
    "compute_wavefronts",
    "execute_plugin_isolated",
    "get_parallel_executor",
    "HAS_REAL_SUBINTERPRETERS",
]

# ADR 0097 Wave 5: Python 3.14+ required - always use subinterpreters
HAS_REAL_SUBINTERPRETERS = sys.version_info >= (3, 14)

if HAS_REAL_SUBINTERPRETERS:
    from concurrent.futures import InterpreterPoolExecutor
else:
    from concurrent.futures import ThreadPoolExecutor as InterpreterPoolExecutor  # type: ignore[assignment]


def execute_plugin_isolated(
    snapshot_dict: dict[str, Any],
    base_path_str: str,
    serialized_spec_dict: dict[str, Any],
) -> PluginExecutionEnvelope:
    """Execute plugin in isolated subinterpreter (ADR 0097).

    This function is submitted to InterpreterPoolExecutor for execution in a separate
    Python subinterpreter. It reconstructs the minimal runtime environment needed for
    snapshot-backed plugin execution and returns a proposal envelope to the main
    interpreter for validation and commit.

    Args:
        snapshot_dict: PluginInputSnapshot as dict (for pickling)
        base_path_str: Base path for plugin loading (as string)
        serialized_spec_dict: SerializablePluginSpec as dict (minimal fields only)

    Returns:
        PluginExecutionEnvelope from isolated worker execution.

    Note:
        This function runs in an isolated interpreter with no shared state from the
        main interpreter. All data is passed via serialized arguments.
    """
    import sys
    from pathlib import Path

    # Reconstruct base path
    base_path = Path(base_path_str)
    plugins_path = base_path / "plugins"
    if str(plugins_path) not in sys.path:
        sys.path.insert(0, str(plugins_path))
    if str(base_path) not in sys.path:
        sys.path.insert(0, str(base_path))

    # Import kernel modules in subinterpreter
    from kernel.plugin_base import PluginContext as SubPluginContext
    from kernel.plugin_base import PluginDiagnostic as SubPluginDiagnostic
    from kernel.plugin_base import PluginExecutionEnvelope as SubEnvelope
    from kernel.plugin_base import PluginInputSnapshot as SubSnapshot
    from kernel.plugin_base import PluginKind as SubPluginKind
    from kernel.plugin_base import Stage as SubStage
    from kernel.scheduler.snapshot_builder import SerializablePluginSpec

    # Reconstruct objects
    snapshot = SubSnapshot(**snapshot_dict)
    spec = SerializablePluginSpec.from_dict(serialized_spec_dict)

    # Resolve plugin entry point
    from kernel.registry.plugin_loader import PluginLoader

    loader = PluginLoader(base_path)

    # Create minimal spec-like object for loader
    class MinimalSpec:
        def __init__(self, data: dict[str, Any]):
            self.id = data["id"]
            self.kind = SubPluginKind(data["kind"])
            self.entry = data["entry"]
            self.api_version = data["api_version"]
            self.manifest_path = data["manifest_path"]

    minimal = MinimalSpec(serialized_spec_dict)

    try:
        plugin_class = loader._load_entry_point(minimal)  # type: ignore[arg-type]
        instance = plugin_class(spec.id, spec.api_version)

        # Build snapshot-backed context
        ctx = SubPluginContext.from_snapshot(snapshot)

        # Execute plugin
        stage = SubStage(snapshot.stage.value if hasattr(snapshot.stage, "value") else snapshot.stage)
        result = instance.execute(ctx, stage)

        # Build envelope
        return SubEnvelope(
            plugin_id=spec.id,
            result=result,
            proposed_context_updates=ctx._pending_updates if hasattr(ctx, "_pending_updates") else {},
            proposed_diagnostics=list(ctx._pending_diagnostics) if hasattr(ctx, "_pending_diagnostics") else [],
        )

    except Exception as exc:
        import traceback

        return SubEnvelope(
            plugin_id=spec.id,
            result=None,
            proposed_context_updates={},
            proposed_diagnostics=[
                SubPluginDiagnostic(
                    code="E4102",
                    severity="error",
                    stage=str(snapshot.stage),
                    phase=str(snapshot.phase),
                    message=f"Plugin crashed in isolated interpreter: {exc}",
                    path=f"plugin:{spec.id}:subinterpreter",
                    plugin_id="kernel",
                    traceback=traceback.format_exc(),
                )
            ],
        )


def get_parallel_executor(max_workers: int) -> InterpreterPoolExecutor:
    """Return subinterpreter executor for parallel plugin execution (ADR 0097 Wave 5).

    Python 3.14+ is required. All plugins execute in isolated subinterpreters
    providing true parallelism via per-interpreter GIL. On Python < 3.14 a
    ThreadPoolExecutor is used for development/testing.

    Args:
        max_workers: Maximum number of parallel workers

    Returns:
        InterpreterPoolExecutor instance
    """
    return InterpreterPoolExecutor(max_workers=max_workers)


def compute_wavefronts(
    plugin_ids: list[str],
    specs: dict[str, PluginSpec],
    sort_key: Callable[[str], tuple[int, str]],
) -> list[list[str]]:
    """Compute execution wavefronts respecting dependencies.

    The single wavefront implementation (ADR 0063 §6): dependency-respecting
    topological grouping with (order, plugin_id) tie-breaks within each
    wavefront. Dependencies outside plugin_ids are ignored.

    Args:
        plugin_ids: List of plugin IDs to execute
        specs: Plugin specifications
        sort_key: Callable to get sort key for plugin

    Returns:
        List of wavefronts (each wavefront is a list of plugin IDs)
    """
    if not plugin_ids:
        return []

    plugin_set = set(plugin_ids)
    indegree: dict[str, int] = {plugin_id: 0 for plugin_id in plugin_ids}
    dependents: dict[str, list[str]] = {plugin_id: [] for plugin_id in plugin_ids}

    for plugin_id in plugin_ids:
        spec = specs.get(plugin_id)
        if spec is None:
            continue
        for dep_id in spec.depends_on:
            if dep_id not in plugin_set:
                continue
            indegree[plugin_id] += 1
            dependents[dep_id].append(plugin_id)

    # Build initial ready queue
    ready: list[tuple[int, str]] = []
    for plugin_id in plugin_ids:
        if indegree[plugin_id] == 0:
            heapq.heappush(ready, sort_key(plugin_id))

    wavefronts: list[list[str]] = []

    while ready:
        wavefront: list[str] = []
        while ready:
            _, plugin_id = heapq.heappop(ready)
            wavefront.append(plugin_id)

        if wavefront:
            wavefronts.append(wavefront)

            # Update ready queue with newly unblocked plugins
            for plugin_id in wavefront:
                for dependent_id in dependents[plugin_id]:
                    indegree[dependent_id] -= 1
                    if indegree[dependent_id] == 0:
                        heapq.heappush(ready, sort_key(dependent_id))

    return wavefronts
