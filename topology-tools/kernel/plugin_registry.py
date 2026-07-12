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
    PlanningError,
    SerializablePluginSpec,
    SnapshotBuilder,
    execute_plugin_isolated,
    get_parallel_executor,
)
from .scheduler import context_bridge as _context_bridge
from .scheduler import envelope_pipeline as _envelope_pipeline
from .scheduler import phase_executor as _phase_executor
from .scheduler import preflight as _preflight
from .scheduler import stage_executor as _stage_executor

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
        """Delegate to scheduler.parallel_executor (S5 decomposition)."""
        return get_parallel_executor(max_workers)

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
        """Delegate to scheduler.phase_executor (S5 decomposition).

        HAS_REAL_SUBINTERPRETERS and execute_plugin_isolated are resolved from
        this module's globals at call time (observable patch points).
        """
        ordered_results = _phase_executor.execute_phase_parallel(
            host=self,
            stage=stage,
            phase=phase,
            ctx=ctx,
            plugin_ids=plugin_ids,
            trace_execution=trace_execution,
            contract_warnings=contract_warnings,
            contract_errors=contract_errors,
            has_real_subinterpreters=HAS_REAL_SUBINTERPRETERS,
            isolated_worker=execute_plugin_isolated,
        )
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
        return _stage_executor.execute_stage(
            host=self,
            stage=stage,
            ctx=ctx,
            profile=profile,
            fail_fast=fail_fast,
            parallel_plugins=parallel_plugins,
            trace_execution=trace_execution,
            contract_warnings=contract_warnings,
            contract_errors=contract_errors,
        )

    @staticmethod
    def _normalize_model_version(token: str) -> str | None:
        """Delegate to scheduler.preflight (S6 decomposition)."""
        return _preflight.normalize_model_version(token)

    @classmethod
    def _is_model_version_compatible(cls, core_model_version: str) -> bool:
        """Delegate to scheduler.preflight (S6 decomposition)."""
        return _preflight.is_model_version_compatible(core_model_version)

    @classmethod
    def _is_model_version_in_set(cls, core_model_version: str, allowed_versions: list[str]) -> bool:
        """Delegate to scheduler.preflight (S6 decomposition)."""
        return _preflight.is_model_version_in_set(core_model_version, allowed_versions)

    def _validate_model_versions(
        self,
        stage: Stage,
        ctx: PluginContext,
        active_plugin_ids: list[str],
    ) -> list[PluginDiagnostic]:
        """Delegate to scheduler.preflight (S6 decomposition)."""
        return _preflight.validate_model_versions(
            stage=stage,
            ctx=ctx,
            active_plugin_ids=active_plugin_ids,
            specs=self.specs,
        )

    def _validate_required_capabilities(
        self,
        stage: Stage,
        ctx: PluginContext,
        profile: Optional[str],
        active_plugin_ids: list[str],
    ) -> list[PluginDiagnostic]:
        """Delegate to scheduler.preflight (S6 decomposition)."""
        return _preflight.validate_required_capabilities(
            stage=stage,
            ctx=ctx,
            profile=profile,
            active_plugin_ids=active_plugin_ids,
            specs=self.specs,
            profile_allows=self._profile_allows_spec,
            when_allows=self._when_predicates_allow,
        )

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
