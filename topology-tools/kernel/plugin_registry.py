"""Plugin registry and loader for v5 topology compiler (ADR 0063).

This module is the main facade for plugin management. Internal functionality
has been decomposed into submodules (ADR 0063 Phase 3):

- kernel.registry: Manifest loading, spec validation, dependency resolution
- kernel.scheduler: Execution planning, parallel execution, snapshots

This module re-exports classes for backwards compatibility.
"""

from __future__ import annotations

import concurrent.futures
import contextvars
import heapq
import re
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Optional, Type

# ADR 0097 Wave 5: Python 3.14+ required - always use subinterpreters
# On Python < 3.14, fall back to ThreadPoolExecutor for development/testing
HAS_REAL_SUBINTERPRETERS = sys.version_info >= (3, 14)
if HAS_REAL_SUBINTERPRETERS:
    from concurrent.futures import InterpreterPoolExecutor
else:
    # For development/testing on Python < 3.14, fall back to ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor as InterpreterPoolExecutor  # type: ignore[assignment]

from .pipeline_runtime import PipelineState
from .plugin_base import (
    Phase,
    PluginBase,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginExecutionEnvelope,
    PluginExecutionScope,
    PluginInputSnapshot,
    PluginKind,
    PluginResult,
    PluginStatus,
    Stage,
)

# ADR 0063 Phase 3: Import from decomposed submodules
# These are re-exported for backwards compatibility
from .registry import ENTRY_FAMILIES as _ENTRY_FAMILIES
from .registry import KIND_ENTRY_FAMILY as _KIND_ENTRY_FAMILY
from .registry import KIND_STAGE_AFFINITY as _KIND_STAGE_AFFINITY
from .registry import PHASE_ORDER as _PHASE_ORDER
from .registry import STAGE_ORDER as _STAGE_ORDER
from .registry import STAGE_ORDER_RANGES as _STAGE_ORDER_RANGES
from .registry import SUPPORTED_API_VERSIONS as _SUPPORTED_API_VERSIONS
from .registry import (
    ConfigValidationError,
    ConfigValidator,
    DependencyError,
    DependencyResolver,
    EnvelopeValidator,
    ManifestLoader,
    ManifestLoadError,
    PluginCycleError,
    PluginLoader,
    PluginLoadError,
    SpecValidationError,
    SpecValidator,
)
from .scheduler import HAS_REAL_SUBINTERPRETERS as _HAS_REAL_SUBINTERPRETERS
from .scheduler import (
    ExecutionPlanner,
    ParallelExecutor,
    PlanningError,
    SerializablePluginSpec,
    SnapshotBuilder,
    execute_plugin_isolated,
)
from .scheduler import context_bridge as _context_bridge
from .scheduler import envelope_pipeline as _envelope_pipeline

# Kernel version/compatibility constants and plugin spec types live in
# kernel.specs (leaf module) and are re-exported here for backwards
# compatibility (ADR 0063 decomposition).
from .specs import (  # noqa: E402
    DEFAULT_PLUGIN_TIMEOUT,
    EXECUTION_PROFILES,
    KERNEL_API_VERSION,
    KERNEL_VERSION,
    MODEL_VERSIONS,
    SUPPORTED_API_VERSIONS,
    PluginManifest,
    PluginSpec,
)

# Re-export constants from registry.spec_validator for backwards compatibility
PHASE_ORDER = _PHASE_ORDER
STAGE_ORDER = _STAGE_ORDER
STAGE_ORDER_RANGES = _STAGE_ORDER_RANGES
KIND_STAGE_AFFINITY = _KIND_STAGE_AFFINITY
KIND_ENTRY_FAMILY = _KIND_ENTRY_FAMILY
ENTRY_FAMILIES = _ENTRY_FAMILIES

# execute_plugin_isolated is imported from .scheduler (ADR 0063 Phase 3)
# SerializablePluginSpec is imported from .scheduler for backwards compatibility


# Exception classes are imported from .registry for backwards compatibility:
# - PluginLoadError from registry.plugin_loader
# - PluginCycleError from registry.dependency_resolver
# - ConfigValidationError (alias PluginConfigError) from registry.config_validator

# Backwards compatibility alias
PluginConfigError = ConfigValidationError


class PluginRegistry:
    """Registry for loading, resolving, and managing plugins.

    This class is the main facade for plugin management. It delegates to
    extracted submodules for specific functionality (ADR 0063 Phase 3):

    - ManifestLoader: Manifest loading and schema validation
    - SpecValidator: Plugin specification validation
    - ConfigValidator: Plugin config schema validation
    - ExecutionPlanner: Execution order planning
    - SnapshotBuilder: Input snapshot building
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize registry with base path for resolving plugin entries."""
        self.base_path = base_path
        self._ensure_import_path(self.base_path)
        self.manifest_schema_path = self.base_path / "schemas" / "plugin-manifest.schema.json"
        self.specs: dict[str, PluginSpec] = {}
        self.instances: dict[str, PluginBase] = {}
        self._manifest_loader = ManifestLoader(self.manifest_schema_path)
        # S2 decomposition: manifest bookkeeping lives in ManifestLoader.
        # Facade attributes alias the same list objects because append order
        # and identity are observable API (compile-topology.py reads slices).
        self.manifests: list[str] = self._manifest_loader.manifests
        self._load_errors: list[str] = self._manifest_loader._load_errors
        self._results: list[PluginResult] = []
        self._instances_lock = threading.Lock()
        self._execution_trace: list[dict[str, Any]] = []
        self._trace_lock = threading.Lock()

        # ADR 0063 Phase 3: Delegate to extracted components
        self._spec_validator = SpecValidator(self.specs)
        self._config_validator = ConfigValidator(self.base_path)
        self._envelope_validator = EnvelopeValidator(self._config_validator)
        self._dependency_resolver = DependencyResolver(self.specs)
        self._execution_planner = ExecutionPlanner(self.specs)
        self._snapshot_builder = SnapshotBuilder(
            self.specs,
            metadata_provider=self._inject_snapshot_metadata,
        )
        self._plugin_loader = PluginLoader(self.base_path)

    def _get_parallel_executor(self, max_workers: int) -> InterpreterPoolExecutor:
        """Return subinterpreter executor for parallel plugin execution (ADR 0097 Wave 5).

        Python 3.14+ is required. All plugins execute in isolated subinterpreters
        providing true parallelism via per-interpreter GIL.

        Args:
            max_workers: Maximum number of parallel workers

        Returns:
            InterpreterPoolExecutor instance
        """
        return InterpreterPoolExecutor(max_workers=max_workers)

    def _trace_event(
        self,
        *,
        event: str,
        stage: Stage,
        phase: Phase | None = None,
        plugin_id: str | None = None,
        status: PluginStatus | None = None,
        message: str | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "seq": 0,
            "ts": time.time(),
            "event": event,
            "stage": stage.value,
        }
        if phase is not None:
            entry["phase"] = phase.value
        if plugin_id is not None:
            entry["plugin_id"] = plugin_id
        if status is not None:
            entry["status"] = status.value
        if message:
            entry["message"] = message
        with self._trace_lock:
            entry["seq"] = len(self._execution_trace) + 1
            self._execution_trace.append(entry)

    @staticmethod
    def _ensure_import_path(path: Path) -> None:
        candidate = str(path.resolve())
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    def _register_spec(self, spec: PluginSpec) -> None:
        """Validate and register a spec loaded from a manifest.

        Passed as on_spec callback to ManifestLoader (S2 decomposition).
        Raises PluginLoadError for invalid specs.
        """
        self._validate_spec(spec)
        self.specs[spec.id] = spec

    def load_manifest(self, manifest_path: Path, *, _loaded_paths: set[Path] | None = None) -> None:
        """Load plugins from a manifest file.

        Supports 'includes' key for manifest sharding (Phase 2 improvement).
        Include paths are resolved relative to the manifest file directory.

        Delegates to ManifestLoader (S2 decomposition); converts
        ManifestLoadError to PluginLoadError for backwards compatibility.
        """
        try:
            self._manifest_loader.load_manifest(
                manifest_path,
                PluginSpec.from_dict,
                self._register_spec,
                existing_ids=self.specs,
                _loaded_paths=_loaded_paths,
            )
        except ManifestLoadError as e:
            raise PluginLoadError(e.source, e.message) from e

    def load_manifests_from_dir(self, search_dir: Path, pattern: str = "plugins.yaml") -> None:
        """Recursively load all plugin manifests from a directory."""
        self._manifest_loader.load_manifests_from_dir(
            search_dir,
            PluginSpec.from_dict,
            self._register_spec,
            existing_ids=self.specs,
            pattern=pattern,
        )

    def _validate_spec(self, spec: PluginSpec) -> None:
        """Validate plugin specification.

        Delegates to SpecValidator (ADR 0063 Phase 3).
        Converts SpecValidationError to PluginLoadError for backwards compatibility.
        """
        try:
            self._spec_validator.validate(spec)
        except SpecValidationError as e:
            raise PluginLoadError(e.plugin_id, str(e).split(": ", 1)[-1]) from e

    @staticmethod
    def _extract_entry_plugin_family(entry: str) -> str | None:
        """Delegate to SpecValidator (ADR 0063 Phase 3)."""
        return SpecValidator._extract_entry_plugin_family(entry)

    @staticmethod
    def _entry_uses_plugins_prefix_without_family(entry: str) -> bool:
        """Delegate to SpecValidator (ADR 0063 Phase 3)."""
        return SpecValidator._entry_uses_plugins_prefix_without_family(entry)

    def _is_api_compatible(self, plugin_api: str) -> bool:
        """Delegate to SpecValidator (ADR 0063 Phase 3)."""
        return SpecValidator._is_api_compatible(plugin_api)

    @staticmethod
    def _stage_rank(stage: Stage) -> int:
        """Delegate to SpecValidator (ADR 0063 Phase 3)."""
        return SpecValidator.stage_rank(stage)

    @staticmethod
    def _phase_rank(phase: Phase) -> int:
        """Delegate to SpecValidator (ADR 0063 Phase 3)."""
        return SpecValidator.phase_rank(phase)

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        """Delegate to ExecutionPlanner (ADR 0063 Phase 3)."""
        return ExecutionPlanner._string_list(value)

    def _active_changed_input_scopes(self, ctx: PluginContext) -> set[str] | None:
        """Delegate to ExecutionPlanner (ADR 0063 Phase 3)."""
        return self._execution_planner._active_changed_input_scopes(ctx)

    def _profile_allows_spec(self, spec: PluginSpec, profile: Optional[str]) -> bool:
        """Delegate to ExecutionPlanner (ADR 0063 Phase 3)."""
        return self._execution_planner._profile_allows_spec(spec, profile)

    def _when_predicates_allow(self, spec: PluginSpec, ctx: PluginContext) -> bool:
        """Delegate to ExecutionPlanner (ADR 0063 Phase 3)."""
        return self._execution_planner._when_predicates_allow(spec, ctx)

    @staticmethod
    def _declared_consumes(spec: PluginSpec) -> set[tuple[str, str]]:
        """Delegate to SnapshotBuilder (ADR 0063 Phase 3)."""
        return SnapshotBuilder._declared_consumes(spec)

    def _inject_snapshot_metadata(self, plugin_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Inject plugin-specific metadata into snapshot config (ADR 0063 Phase 3).

        This callback is passed to SnapshotBuilder for metadata injection.
        """
        # ADR 0097 P4.1: Inject generator migration metadata for artifact_contract_guard
        # This replaces direct plugin_registry access, enabling subinterpreter execution.
        if plugin_id == "base.assembler.artifact_contract_guard":
            config["generator_migration_metadata"] = self._compute_generator_migration_metadata()
        return config

    def _build_input_snapshot(
        self,
        *,
        plugin_id: str,
        stage: Stage,
        phase: Phase,
        ctx: PluginContext,
        pipeline_state: PipelineState | None = None,
    ) -> PluginInputSnapshot:
        """Build immutable plugin input for the envelope-model execution path.

        Delegates to SnapshotBuilder (ADR 0063 Phase 3).
        """
        return self._snapshot_builder.build(
            plugin_id=plugin_id,
            stage=stage,
            phase=phase,
            ctx=ctx,
            pipeline_state=pipeline_state,
        )

    @staticmethod
    def _compatibility_producer_ids(spec: PluginSpec) -> set[str]:
        """Delegate to SnapshotBuilder (ADR 0063 Phase 3)."""
        return SnapshotBuilder._compatibility_producer_ids(spec)

    def _compute_generator_migration_metadata(self) -> dict[str, dict[str, str]]:
        """Compute generator migration metadata for ADR0097 P4.1 subinterpreter compatibility.

        Returns a dict mapping generator plugin IDs to their migration metadata:
        {
            "plugin_id": {"migration_mode": "legacy|migrating|migrated|rollback"}
        }

        This pre-computed metadata replaces direct plugin_registry access in
        subinterpreter-mode assemblers that need to inspect generator contracts.
        """
        metadata: dict[str, dict[str, str]] = {}
        for plugin_id, spec in self.specs.items():
            if spec.kind != PluginKind.GENERATOR:
                continue
            metadata[plugin_id] = {
                "migration_mode": str(getattr(spec, "migration_mode", "legacy")).strip().lower() or "legacy",
            }
        return metadata

    def _ensure_pipeline_state(self, ctx: PluginContext) -> PipelineState:
        """Delegate to scheduler.context_bridge (S4 decomposition)."""
        return _context_bridge.ensure_pipeline_state(ctx)

    def _mirror_context_into_pipeline_state(self, ctx: PluginContext, pipeline_state: PipelineState) -> None:
        """Delegate to scheduler.context_bridge (S4 decomposition)."""
        _context_bridge.mirror_context_into_pipeline_state(ctx, pipeline_state)

    def _sync_pipeline_state_to_context(self, ctx: PluginContext, pipeline_state: PipelineState) -> None:
        """Delegate to scheduler.context_bridge (S4 decomposition)."""
        _context_bridge.sync_pipeline_state_to_context(ctx, pipeline_state)

    def _apply_authoritative_commit_side_effects(
        self,
        *,
        ctx: PluginContext,
        pipeline_state: PipelineState,
        spec: PluginSpec,
    ) -> None:
        """Delegate to scheduler.context_bridge (S4 decomposition)."""
        _context_bridge.apply_authoritative_commit_side_effects(
            ctx=ctx,
            pipeline_state=pipeline_state,
            spec=spec,
        )

    def _validate_required_consumes_snapshot(
        self,
        *,
        spec: PluginSpec,
        snapshot: PluginInputSnapshot,
        stage: Stage,
        phase: Phase,
    ) -> list[PluginDiagnostic]:
        """Delegate to EnvelopeValidator (S3 decomposition)."""
        return self._envelope_validator.validate_required_consumes_snapshot(
            spec=spec,
            snapshot=snapshot,
            stage=stage,
            phase=phase,
        )

    def _validate_envelope_for_commit(
        self,
        *,
        spec: PluginSpec,
        stage: Stage,
        phase: Phase,
        envelope: PluginExecutionEnvelope,
        emit_warnings: bool,
        undeclared_as_errors: bool,
    ) -> list[PluginDiagnostic]:
        """Delegate to EnvelopeValidator (ADR 0063 Phase 3)."""
        return self._envelope_validator.validate_for_commit(
            spec=spec,
            stage=stage,
            phase=phase,
            envelope=envelope,
            emit_warnings=emit_warnings,
            undeclared_as_errors=undeclared_as_errors,
        )

    def _failed_result_with_diagnostics(
        self,
        *,
        spec: PluginSpec,
        stage: Stage,
        phase: Phase,
        diagnostics: list[PluginDiagnostic],
    ) -> PluginResult:
        """Delegate to scheduler.envelope_pipeline (S4 decomposition)."""
        return _envelope_pipeline.failed_result_with_diagnostics(
            spec=spec,
            stage=stage,
            phase=phase,
            diagnostics=diagnostics,
        )

    def _execute_plugin_envelope_local(
        self,
        *,
        plugin_id: str,
        spec: PluginSpec,
        stage: Stage,
        phase: Phase,
        snapshot: PluginInputSnapshot,
        timeout: float,
    ) -> PluginExecutionEnvelope:
        """Delegate to scheduler.envelope_pipeline (S4 decomposition)."""
        return _envelope_pipeline.execute_plugin_envelope_local(
            plugin=self.load_plugin(plugin_id),
            plugin_id=plugin_id,
            spec=spec,
            stage=stage,
            phase=phase,
            snapshot=snapshot,
            timeout=timeout,
        )

    @staticmethod
    def _is_cross_interpreter_shareability_error(exc: Exception) -> bool:
        """Delegate to scheduler.envelope_pipeline (S4 decomposition)."""
        return _envelope_pipeline.is_cross_interpreter_shareability_error(exc)

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
    ) -> PluginResult:
        """Delegate to scheduler.envelope_pipeline (S4 decomposition)."""
        return _envelope_pipeline.commit_envelope_result(
            ctx=ctx,
            pipeline_state=pipeline_state,
            spec=spec,
            stage=stage,
            phase=phase,
            envelope=envelope,
            contract_warnings=contract_warnings,
            contract_errors=contract_errors,
            envelope_validator=self._envelope_validator,
        )

    @staticmethod
    def _commit_keys_on_failure(spec: PluginSpec) -> set[str]:
        """Delegate to scheduler.envelope_pipeline (S4 decomposition)."""
        return _envelope_pipeline.commit_keys_on_failure(spec)

    @staticmethod
    def _apply_result_status_from_diagnostics(result: PluginResult) -> None:
        """Delegate to scheduler.envelope_pipeline (S4 decomposition)."""
        _envelope_pipeline.apply_result_status_from_diagnostics(result)

    def _resolve_payload_schema_path(self, spec: PluginSpec, schema_ref: str) -> Path | None:
        """Delegate to ConfigValidator (ADR 0063 Phase 3)."""
        return self._config_validator.resolve_schema_path(spec, schema_ref)

    def _load_payload_schema(self, spec: PluginSpec, schema_ref: str) -> tuple[dict[str, Any] | None, str | None]:
        """Delegate to ConfigValidator (ADR 0063 Phase 3)."""
        return self._config_validator.load_payload_schema(spec, schema_ref)

    def _schema_ref_by_produced_key(self, spec: PluginSpec) -> dict[str, str]:
        """Delegate to ConfigValidator (ADR 0063 Phase 3)."""
        return self._config_validator.schema_ref_by_produced_key(spec)

    def _schema_ref_by_consumed_key(self, spec: PluginSpec) -> dict[tuple[str, str], str]:
        """Delegate to ConfigValidator (ADR 0063 Phase 3)."""
        return self._config_validator.schema_ref_by_consumed_key(spec)

    def _validate_required_consumes_pre_run(
        self,
        *,
        spec: PluginSpec,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase,
    ) -> list[PluginDiagnostic]:
        """Delegate to EnvelopeValidator (S3 decomposition)."""
        return self._envelope_validator.validate_required_consumes_pre_run(
            spec=spec,
            published_data=ctx.get_published_data(),
            stage=stage,
            phase=phase,
        )

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
    ) -> None:
        """Delegate to EnvelopeValidator (S3 decomposition); appends into result."""
        result.diagnostics.extend(
            self._envelope_validator.validate_payload_schema(
                spec=spec,
                stage=stage,
                phase=phase,
                payload=payload,
                schema_ref=schema_ref,
                path_suffix=path_suffix,
            )
        )

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
    ) -> None:
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
        produce_schema_refs = self._schema_ref_by_produced_key(spec)
        consume_schema_refs = self._schema_ref_by_consumed_key(spec)

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
            declared_consumes = self._declared_consumes(spec)
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
            self._validate_schema_ref_payload(
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
            self._validate_schema_ref_payload(
                result=result,
                stage=stage,
                phase=phase,
                spec=spec,
                payload=payload,
                schema_ref=schema_ref,
                path_suffix=f"consumes.{from_plugin}.{key}",
            )

        self._apply_result_status_from_diagnostics(result)

    def validate_plugin_config(self, plugin_id: str) -> list[str]:
        """Validate plugin config against its config_schema.

        Returns list of validation errors (empty if valid).
        Delegates to ConfigValidator (ADR 0063 Phase 3).
        """
        if plugin_id not in self.specs:
            return [f"Plugin not found: {plugin_id}"]
        return self._config_validator.validate(self.specs[plugin_id])

    def resolve_dependencies(self) -> list[str]:
        """Resolve plugin dependencies and return execution order.

        Delegates to DependencyResolver (ADR 0063 Phase 3).
        Converts DependencyError to PluginLoadError for backwards compatibility.

        Returns:
            List of plugin IDs in execution order

        Raises:
            PluginCycleError: If circular dependency detected
            PluginLoadError: If dependency not found
        """
        try:
            return self._dependency_resolver.resolve()
        except DependencyError as e:
            raise PluginLoadError(e.plugin_id, str(e).split(": ", 1)[-1]) from e

    def get_execution_order(self, stage: Stage, profile: Optional[str] = None, phase: Phase = Phase.RUN) -> list[str]:
        """Get plugins to execute for a stage, in order.

        Validates global dependency graph then delegates to ExecutionPlanner
        (ADR 0063 Phase 3).

        Args:
            stage: Pipeline stage
            profile: Current execution profile (for filtering)
            phase: Execution phase

        Returns:
            List of plugin IDs in execution order
        """
        # Validate dependency graph globally (missing deps / cycles).
        # Ordering itself is then resolved stage-locally by ExecutionPlanner.
        self.resolve_dependencies()
        return self._execution_planner.get_execution_order(stage, phase, profile)

    def _plugin_sort_key(self, plugin_id: str) -> tuple[int, str]:
        """Delegate to ExecutionPlanner (ADR 0063 Phase 3)."""
        return self._execution_planner.plugin_sort_key(plugin_id)

    def _preload_plugins(self, plugin_ids: list[str]) -> None:
        """Preload plugin classes/instances before optional parallel execution."""
        for plugin_id in plugin_ids:
            try:
                self.load_plugin(plugin_id)
            except (PluginLoadError, PluginConfigError):
                # Execution path emits canonical plugin diagnostics.
                continue

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
    ) -> list[PluginResult]:
        """Execute one phase in dependency-respecting wavefronts."""
        if not plugin_ids:
            return []

        pipeline_state = self._ensure_pipeline_state(ctx)
        plugin_set = set(plugin_ids)
        indegree: dict[str, int] = {plugin_id: 0 for plugin_id in plugin_ids}
        dependents: dict[str, list[str]] = {plugin_id: [] for plugin_id in plugin_ids}

        for plugin_id in plugin_ids:
            spec = self.specs.get(plugin_id)
            if spec is None:
                continue
            for dep_id in spec.depends_on:
                if dep_id not in plugin_set:
                    continue
                indegree[plugin_id] += 1
                dependents[dep_id].append(plugin_id)

        ready: list[tuple[int, str]] = []
        for plugin_id in plugin_ids:
            if indegree[plugin_id] == 0:
                heapq.heappush(ready, self._plugin_sort_key(plugin_id))

        results_by_plugin: dict[str, PluginResult] = {}
        max_workers = min(8, max(1, len(plugin_ids)))

        # ADR 0097 Wave 5: Always use subinterpreters (Python 3.14+ required)
        executor = self._get_parallel_executor(max_workers)

        # ADR 0097: Pre-validate all plugin configs before parallel submission
        # Validates upfront to fail fast and avoid wasted subinterpreter spawning
        config_validation_failed: dict[str, list[str]] = {}
        for plugin_id in plugin_ids:
            errors = self.validate_plugin_config(plugin_id)
            if errors:
                config_validation_failed[plugin_id] = errors

        # Create early failures for invalid configs
        for plugin_id, errors in config_validation_failed.items():
            spec = self.specs.get(plugin_id)
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
            # Remove from ready queue - mark as having indegree -1 to prevent execution
            indegree[plugin_id] = -1

        with executor:
            while ready:
                wavefront: list[str] = []
                while ready:
                    _, plugin_id = heapq.heappop(ready)
                    # Skip plugins that failed config validation
                    if plugin_id in config_validation_failed:
                        continue
                    wavefront.append(plugin_id)

                if not wavefront:
                    break  # No more valid plugins to execute

                futures: dict[concurrent.futures.Future[PluginExecutionEnvelope], str] = {}
                snapshots_by_plugin: dict[str, PluginInputSnapshot] = {}
                for plugin_id in wavefront:
                    if trace_execution:
                        self._trace_event(event="plugin_start", stage=stage, phase=phase, plugin_id=plugin_id)

                    spec = self.specs[plugin_id]
                    # ADR 0097 PR2: Route based on execution_mode
                    if spec.execution_mode == "thread_legacy":
                        # Legacy path: direct execute_plugin() with context merge-back
                        result = self.execute_plugin(
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
                        self._mirror_context_into_pipeline_state(ctx, pipeline_state)
                        if trace_execution:
                            self._trace_event(
                                event="plugin_result",
                                stage=stage,
                                phase=phase,
                                plugin_id=plugin_id,
                                status=result.status,
                                message="thread_legacy compatibility path",
                            )
                        continue

                    try:
                        snapshot = self._build_input_snapshot(
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
                            self._trace_event(
                                event="plugin_result",
                                stage=stage,
                                phase=phase,
                                plugin_id=plugin_id,
                                status=failed.status,
                                message="snapshot-build failed",
                            )
                        continue

                    required_consume_diags = self._validate_required_consumes_snapshot(
                        spec=spec,
                        snapshot=snapshot,
                        stage=stage,
                        phase=phase,
                    )
                    if required_consume_diags:
                        failed = self._failed_result_with_diagnostics(
                            spec=spec,
                            stage=stage,
                            phase=phase,
                            diagnostics=required_consume_diags,
                        )
                        results_by_plugin[plugin_id] = failed
                        if trace_execution:
                            self._trace_event(
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
                    if spec.execution_mode == "subinterpreter" and HAS_REAL_SUBINTERPRETERS:
                        # Submit to real subinterpreter pool (ADR 0063 Phase 3: delegate to scheduler)
                        snapshots_by_plugin[plugin_id] = snapshot
                        serialized_spec = SerializablePluginSpec.from_plugin_spec(spec)
                        future = executor.submit(
                            execute_plugin_isolated,
                            snapshot.__dict__,
                            str(self.base_path),
                            serialized_spec.to_dict(),
                        )
                        futures[future] = plugin_id
                    elif spec.execution_mode == "main_interpreter" or HAS_REAL_SUBINTERPRETERS:
                        # Execute inline in main interpreter (ADR 0097 D1: main owns state)
                        # This includes: main_interpreter mode, or subinterpreter fallback on Py3.14+
                        envelope = self._execute_plugin_envelope_local(
                            plugin_id=plugin_id,
                            spec=spec,
                            stage=stage,
                            phase=phase,
                            snapshot=snapshot,
                            timeout=spec.timeout,
                        )
                        result = self._commit_envelope_result(
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
                            self._trace_event(
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
                            self._execute_plugin_envelope_local,
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
                    spec = self.specs.get(plugin_id)
                    if spec is None:
                        continue
                    try:
                        envelope = future.result(timeout=spec.timeout if HAS_REAL_SUBINTERPRETERS else None)
                        result = self._commit_envelope_result(
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
                            self._trace_event(
                                event="plugin_result",
                                stage=stage,
                                phase=phase,
                                plugin_id=plugin_id,
                                status=result.status,
                            )
                    except Exception as exc:
                        snapshot = snapshots_by_plugin.get(plugin_id)
                        if snapshot is not None and self._is_cross_interpreter_shareability_error(exc):
                            envelope = self._execute_plugin_envelope_local(
                                plugin_id=plugin_id,
                                spec=spec,
                                stage=stage,
                                phase=phase,
                                snapshot=snapshot,
                                timeout=spec.timeout,
                            )
                            result = self._commit_envelope_result(
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
                                self._trace_event(
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
                            self._trace_event(
                                event="plugin_result",
                                stage=stage,
                                phase=phase,
                                plugin_id=plugin_id,
                                status=failed.status,
                                message=str(exc),
                            )

                for plugin_id in sorted(wavefront, key=self._plugin_sort_key):
                    if plugin_id not in results_by_plugin:
                        continue
                    for dependent_id in dependents[plugin_id]:
                        indegree[dependent_id] -= 1
                        if indegree[dependent_id] == 0:
                            heapq.heappush(ready, self._plugin_sort_key(dependent_id))

        ordered_results = [results_by_plugin[plugin_id] for plugin_id in plugin_ids if plugin_id in results_by_plugin]
        self._results.extend(ordered_results)
        return ordered_results

    def load_plugin(self, plugin_id: str) -> PluginBase:
        """Load and instantiate a plugin by ID.

        Args:
            plugin_id: Plugin ID to load

        Returns:
            Instantiated plugin

        Raises:
            PluginLoadError: If plugin cannot be loaded
        """
        with self._instances_lock:
            if plugin_id in self.instances:
                return self.instances[plugin_id]

            if plugin_id not in self.specs:
                raise PluginLoadError(plugin_id, "Plugin not found in registry")

            spec = self.specs[plugin_id]

            # Validate config before loading
            config_errors = self.validate_plugin_config(plugin_id)
            if config_errors:
                raise PluginConfigError(plugin_id, "; ".join(config_errors))

            plugin_class = self._load_entry_point(spec)
            instance = plugin_class(plugin_id, spec.api_version)

            # Verify plugin kind matches spec
            if instance.kind != spec.kind:
                raise PluginLoadError(
                    plugin_id,
                    f"Plugin kind mismatch: spec declares {spec.kind.value}, class returns {instance.kind.value}",
                )

            self.instances[plugin_id] = instance
            return instance

    def _load_entry_point(self, spec: PluginSpec) -> Type[PluginBase]:
        """Load plugin class from entry point specification.

        Delegates to PluginLoader (ADR 0063 Phase 3).
        Entry format: "path/to/module.py:ClassName"
        """
        return self._plugin_loader._load_entry_point(spec)

    def execute_plugin(
        self,
        plugin_id: str,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase = Phase.RUN,
        timeout: Optional[float] = None,
        *,
        record_result: bool = True,
        contract_warnings: bool = False,
        contract_errors: bool = False,
    ) -> PluginResult:
        """Execute a single plugin with timeout and error handling.

        Args:
            plugin_id: Plugin ID to execute
            ctx: Execution context
            stage: Current pipeline stage
            timeout: Timeout in seconds (uses plugin spec timeout if None)

        Returns:
            PluginResult with execution status and diagnostics
        """
        if plugin_id not in self.specs:
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

        spec = self.specs[plugin_id]
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
            plugin = self.load_plugin(plugin_id)
        except (PluginLoadError, PluginConfigError) as e:
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
        required_consume_diags = self._validate_required_consumes_pre_run(
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
                self._results.append(failed)
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
                self._attach_data_bus_contract_diagnostics(
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
                    self._results.append(result)
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
                self._attach_data_bus_contract_diagnostics(
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
                    self._results.append(result)
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
            self._attach_data_bus_contract_diagnostics(
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
                self._results.append(result)
            return result
        finally:
            # Do not wait for timed-out plugins; this avoids blocking the pipeline
            # after we already returned TIMEOUT.
            executor.shutdown(wait=not timed_out, cancel_futures=True)
            ctx._clear_execution_scope(scope_token)

    def execute_stage(
        self,
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
            phase: self.get_execution_order(stage, profile, phase=phase) for phase in PHASE_ORDER
        }
        ordered_plugin_ids = [plugin_id for phase in PHASE_ORDER for plugin_id in phase_plugin_ids[phase]]

        if not ordered_plugin_ids:
            return results

        if trace_execution:
            self._trace_event(
                event="stage_start",
                stage=stage,
                message=f"plugins={len(ordered_plugin_ids)} parallel={parallel_plugins}",
            )

        invalidated_stage_local: list[str] = []
        try:
            pipeline_state = self._ensure_pipeline_state(ctx)
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
                spec = self.specs.get(plugin_id)
                if spec is None:
                    when_allowed_by_plugin[plugin_id] = False
                    continue
                when_allowed_by_plugin[plugin_id] = self._when_predicates_allow(spec, ctx)

            active_plugin_ids = [
                plugin_id for plugin_id in ordered_plugin_ids if when_allowed_by_plugin.get(plugin_id, False)
            ]

            # Model version validation (extracted method)
            model_version_diags = self._validate_model_versions(stage, ctx, active_plugin_ids)
            if model_version_diags:
                result = PluginResult.failed(
                    plugin_id="kernel.model_version_guard",
                    api_version=KERNEL_API_VERSION,
                    diagnostics=model_version_diags,
                )
                results.append(result)
                self._results.append(result)
                return results

            # Capability validation (extracted method)
            capability_diags = self._validate_required_capabilities(stage, ctx, profile, active_plugin_ids)
            if capability_diags:
                result = PluginResult.failed(
                    plugin_id="kernel.capability_guard",
                    api_version=KERNEL_API_VERSION,
                    diagnostics=capability_diags,
                )
                results.append(result)
                self._results.append(result)
                return results

            if parallel_plugins:
                self._preload_plugins(active_plugin_ids)

            fail_fast_triggered = False
            for phase in PHASE_ORDER:
                if fail_fast_triggered and phase is not Phase.FINALIZE:
                    continue

                if trace_execution:
                    self._trace_event(event="phase_start", stage=stage, phase=phase)

                phase_active_plugin_ids: list[str] = []
                for plugin_id in phase_plugin_ids[phase]:
                    spec = self.specs.get(plugin_id)
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
                        self._results.append(skipped)
                        if trace_execution:
                            self._trace_event(
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
                    phase_results = self._execute_phase_parallel(
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
                        self._trace_event(event="plugin_start", stage=stage, phase=phase, plugin_id=plugin_id)
                    spec = self.specs[plugin_id]
                    # ADR 0097 PR2: Route based on execution_mode
                    if spec.execution_mode == "thread_legacy":
                        # Legacy path: direct execute_plugin() with context merge-back
                        result = self.execute_plugin(
                            plugin_id,
                            ctx,
                            stage,
                            phase=phase,
                            contract_warnings=contract_warnings,
                            contract_errors=contract_errors,
                        )
                        self._mirror_context_into_pipeline_state(ctx, pipeline_state)
                    else:
                        # Envelope path: both subinterpreter and main_interpreter modes
                        try:
                            snapshot = self._build_input_snapshot(
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
                            required_consume_diags = self._validate_required_consumes_snapshot(
                                spec=spec,
                                snapshot=snapshot,
                                stage=stage,
                                phase=phase,
                            )
                            if required_consume_diags:
                                result = self._failed_result_with_diagnostics(
                                    spec=spec,
                                    stage=stage,
                                    phase=phase,
                                    diagnostics=required_consume_diags,
                                )
                            else:
                                envelope = self._execute_plugin_envelope_local(
                                    plugin_id=plugin_id,
                                    spec=spec,
                                    stage=stage,
                                    phase=phase,
                                    snapshot=snapshot,
                                    timeout=spec.timeout,
                                )
                                result = self._commit_envelope_result(
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
                        self._trace_event(
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
                self._sync_pipeline_state_to_context(ctx, pipeline_state)
            else:
                invalidated_stage_local = ctx.invalidate_stage_local_data(stage)
            if trace_execution:
                suffix = f"invalidated_stage_local={len(invalidated_stage_local)}"
                self._trace_event(event="stage_end", stage=stage, message=suffix)

    @staticmethod
    def _normalize_model_version(token: str) -> str | None:
        if not isinstance(token, str):
            return None
        candidate = token.strip()
        if not candidate:
            return None
        match = re.search(r"(\d+)\.(\d+)", candidate)
        if not match:
            return None
        return f"{int(match.group(1))}.{int(match.group(2))}"

    @classmethod
    def _is_model_version_compatible(cls, core_model_version: str) -> bool:
        normalized_core = cls._normalize_model_version(core_model_version)
        if normalized_core is None:
            return False
        supported = {
            normalized
            for normalized in (cls._normalize_model_version(item) for item in MODEL_VERSIONS)
            if normalized is not None
        }
        return normalized_core in supported

    @classmethod
    def _is_model_version_in_set(cls, core_model_version: str, allowed_versions: list[str]) -> bool:
        normalized_core = cls._normalize_model_version(core_model_version)
        if normalized_core is None:
            return False
        normalized_allowed = {
            normalized
            for normalized in (cls._normalize_model_version(item) for item in allowed_versions)
            if normalized is not None
        }
        return normalized_core in normalized_allowed

    def _validate_model_versions(
        self,
        stage: Stage,
        ctx: PluginContext,
        active_plugin_ids: list[str],
    ) -> list[PluginDiagnostic]:
        """Validate model version compatibility for active plugins.

        Returns list of diagnostics (empty if all pass).
        """
        diagnostics: list[PluginDiagnostic] = []
        core_model_version = ctx.model_lock.get("core_model_version") if isinstance(ctx.model_lock, dict) else None

        # Check kernel supports this model version
        if isinstance(core_model_version, str) and core_model_version:
            if not self._is_model_version_compatible(core_model_version):
                diagnostics.append(
                    PluginDiagnostic(
                        code="E4011",
                        severity="error",
                        stage=stage.value,
                        phase=Phase.RUN.value,
                        message=(
                            f"Unsupported core_model_version '{core_model_version}'. "
                            f"Kernel supports: {MODEL_VERSIONS}"
                        ),
                        path="model.lock:core_model_version",
                        plugin_id="kernel",
                    )
                )
                return diagnostics  # Early return - kernel incompatibility

        # Check per-plugin model_versions declarations
        for plugin_id in active_plugin_ids:
            spec = self.specs.get(plugin_id)
            if not isinstance(spec, PluginSpec):
                continue
            declared_model_versions = [item for item in spec.model_versions if isinstance(item, str) and item.strip()]
            if not declared_model_versions:
                continue
            if not isinstance(core_model_version, str) or not core_model_version:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E4012",
                        severity="error",
                        stage=stage.value,
                        phase=Phase.RUN.value,
                        message=(
                            f"Plugin '{plugin_id}' declares model_versions={declared_model_versions}, "
                            "but model.lock core_model_version is unavailable."
                        ),
                        path=f"plugin:{plugin_id}",
                        plugin_id="kernel",
                    )
                )
                continue
            if not self._is_model_version_in_set(core_model_version, declared_model_versions):
                diagnostics.append(
                    PluginDiagnostic(
                        code="E4011",
                        severity="error",
                        stage=stage.value,
                        phase=Phase.RUN.value,
                        message=(
                            f"Plugin '{plugin_id}' does not support core_model_version "
                            f"'{core_model_version}'. Supported by plugin: {declared_model_versions}"
                        ),
                        path=f"plugin:{plugin_id}",
                        plugin_id="kernel",
                    )
                )
        return diagnostics

    def _validate_required_capabilities(
        self,
        stage: Stage,
        ctx: PluginContext,
        profile: Optional[str],
        active_plugin_ids: list[str],
    ) -> list[PluginDiagnostic]:
        """Validate that all required capabilities are available.

        Returns list of diagnostics (empty if all pass).
        """
        # Collect available capabilities from active plugins
        available_capabilities: set[str] = set()
        for spec in self.specs.values():
            if not self._profile_allows_spec(spec, profile):
                continue
            if not self._when_predicates_allow(spec, ctx):
                continue
            for capability in spec.capabilities:
                if isinstance(capability, str) and capability:
                    available_capabilities.add(capability)

        # Check each plugin's requires_capabilities
        diagnostics: list[PluginDiagnostic] = []
        for plugin_id in active_plugin_ids:
            spec = self.specs.get(plugin_id)
            if not isinstance(spec, PluginSpec):
                continue
            missing = sorted(
                capability
                for capability in spec.requires_capabilities
                if isinstance(capability, str) and capability and capability not in available_capabilities
            )
            if missing:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E4010",
                        severity="error",
                        stage=stage.value,
                        message=(
                            f"Plugin '{plugin_id}' requires missing capabilities: {missing}. "
                            "Provide capability-producing plugins or adjust requires_capabilities."
                        ),
                        path=f"plugin:{plugin_id}",
                        plugin_id="kernel",
                    )
                )
        return diagnostics

    def get_load_errors(self) -> list[str]:
        """Return any errors encountered during manifest loading."""
        return self._load_errors.copy()

    def get_all_results(self) -> list[PluginResult]:
        """Return all plugin execution results."""
        return self._results.copy()

    def get_execution_trace(self) -> list[dict[str, Any]]:
        """Return execution trace events collected in trace mode."""
        with self._trace_lock:
            return [entry.copy() for entry in self._execution_trace]

    def reset_execution_trace(self) -> None:
        """Clear stored execution trace."""
        with self._trace_lock:
            self._execution_trace.clear()

    def get_stats(self) -> dict[str, Any]:
        """Return registry statistics."""
        by_kind: dict[str, int] = {}
        for spec in self.specs.values():
            kind = spec.kind.value
            by_kind[kind] = by_kind.get(kind, 0) + 1

        by_status: dict[str, int] = {}
        for result in self._results:
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "loaded": len(self.specs),
            "executed": len(self.instances),
            "failed": len(self._load_errors),
            "by_kind": by_kind,
            "by_status": by_status,
            "manifests": self.manifests,
            "execution_order": [r.plugin_id for r in self._results],
        }

    @staticmethod
    def get_kernel_info() -> dict[str, Any]:
        """Return kernel version and compatibility information."""
        return {
            "version": KERNEL_VERSION,
            "plugin_api_version": KERNEL_API_VERSION,
            "supported_api_versions": SUPPORTED_API_VERSIONS,
            "model_versions": MODEL_VERSIONS,
            "execution_profiles": EXECUTION_PROFILES,
            "default_timeout": DEFAULT_PLUGIN_TIMEOUT,
        }
