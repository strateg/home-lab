"""Base plugin interfaces for v5 topology compiler (ADR 0063).

This module defines the plugin contract that all v5 plugins must implement.
Plugins are the primary extension mechanism for the compiler pipeline.

Updated to match ADR 0063 expanded specification:
- PluginStatus enum (SUCCESS|PARTIAL|FAILED|TIMEOUT|SKIPPED)
- PluginResult with duration_ms, error_traceback, output_data
- Stage enum (validate|compile|generate)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, MutableMapping
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from types import MappingProxyType
from typing import Any, Callable, Optional


class PluginKind(str, Enum):
    """Plugin kind determining execution context."""

    COMPILER = "compiler"
    VALIDATOR_YAML = "validator_yaml"
    VALIDATOR_JSON = "validator_json"
    GENERATOR = "generator"
    ASSEMBLER = "assembler"
    BUILDER = "builder"


class Stage(str, Enum):
    """Pipeline stages where plugins can execute."""

    DISCOVER = "discover"
    COMPILE = "compile"
    VALIDATE = "validate"
    GENERATE = "generate"
    ASSEMBLE = "assemble"
    BUILD = "build"


class Phase(str, Enum):
    """Lifecycle phases within each stage."""

    INIT = "init"
    PRE = "pre"
    RUN = "run"
    POST = "post"
    VERIFY = "verify"
    FINALIZE = "finalize"


@dataclass(frozen=True)
class PublishedDataMeta:
    """Metadata for published values used by lifecycle enforcement."""

    stage: Stage
    phase: Phase
    scope: str


@dataclass(frozen=True)
class PublishEvent:
    """Runtime publish event for produces/consumes transitional enforcement."""

    plugin_id: str
    key: str
    stage: Stage
    phase: Phase


@dataclass(frozen=True)
class SubscribeEvent:
    """Runtime subscribe event for produces/consumes transitional enforcement."""

    plugin_id: str
    from_plugin: str
    key: str
    stage: Stage
    phase: Phase


@dataclass(frozen=True)
class PluginExecutionScope:
    """Per-invocation immutable execution scope."""

    plugin_id: str
    allowed_dependencies: frozenset[str]
    phase: Phase
    config: Mapping[str, Any]
    stage: Stage = Stage.VALIDATE
    produced_key_scopes: Mapping[str, str] = field(default_factory=dict)


_EXECUTION_SCOPE: ContextVar[PluginExecutionScope | None] = ContextVar("plugin_execution_scope", default=None)


class PluginStatus(str, Enum):
    """Plugin execution status."""

    SUCCESS = "SUCCESS"  # All checks passed, no errors
    PARTIAL = "PARTIAL"  # Some checks passed, some warnings
    FAILED = "FAILED"  # Plugin execution failed with errors
    TIMEOUT = "TIMEOUT"  # Plugin exceeded timeout limit
    SKIPPED = "SKIPPED"  # Plugin skipped (dependency failed, config invalid)


@dataclass
class PluginDiagnostic:
    """Single diagnostic message emitted by a plugin."""

    code: str
    severity: str  # "error" | "warning" | "info"
    stage: str
    message: str
    path: str
    plugin_id: str
    phase: Optional[str] = None
    confidence: float = 1.0
    hint: Optional[str] = None
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    source_column: Optional[int] = None
    related: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "path": self.path,
            "plugin_id": self.plugin_id,
            "confidence": self.confidence,
        }
        if self.phase:
            result["phase"] = self.phase
        if self.hint:
            result["hint"] = self.hint
        if self.source_file:
            source: dict[str, Any] = {"file": self.source_file}
            if self.source_line:
                source["line"] = self.source_line
            if self.source_column:
                source["column"] = self.source_column
            result["source"] = source
        if self.related:
            result["related"] = self.related
        return result


@dataclass
class PluginResult:
    """Result of plugin execution (ADR 0063 compliant).

    Attributes:
        plugin_id: ID of the plugin that produced this result
        api_version: Plugin API version
        status: Execution status (SUCCESS|PARTIAL|FAILED|TIMEOUT|SKIPPED)
        duration_ms: Execution time in milliseconds
        diagnostics: List of diagnostic messages
        output_data: Transformed model or generated files metadata
        error_traceback: Full exception traceback if crashed
    """

    plugin_id: str
    api_version: str
    status: PluginStatus
    duration_ms: float = 0.0
    diagnostics: list[PluginDiagnostic] = field(default_factory=list)
    output_data: Optional[dict[str, Any]] = None
    error_traceback: Optional[str] = None

    @classmethod
    def success(
        cls,
        plugin_id: str,
        api_version: str = "1.x",
        duration_ms: float = 0.0,
        diagnostics: Optional[list[PluginDiagnostic]] = None,
        output_data: Optional[dict[str, Any]] = None,
    ) -> PluginResult:
        """Create successful result."""
        return cls(
            plugin_id=plugin_id,
            api_version=api_version,
            status=PluginStatus.SUCCESS,
            duration_ms=duration_ms,
            diagnostics=diagnostics or [],
            output_data=output_data,
        )

    @classmethod
    def partial(
        cls,
        plugin_id: str,
        api_version: str = "1.x",
        duration_ms: float = 0.0,
        diagnostics: Optional[list[PluginDiagnostic]] = None,
        output_data: Optional[dict[str, Any]] = None,
    ) -> PluginResult:
        """Create partial success result (warnings but no errors)."""
        return cls(
            plugin_id=plugin_id,
            api_version=api_version,
            status=PluginStatus.PARTIAL,
            duration_ms=duration_ms,
            diagnostics=diagnostics or [],
            output_data=output_data,
        )

    @classmethod
    def failed(
        cls,
        plugin_id: str,
        api_version: str = "1.x",
        duration_ms: float = 0.0,
        diagnostics: Optional[list[PluginDiagnostic]] = None,
        error_traceback: Optional[str] = None,
    ) -> PluginResult:
        """Create failed result."""
        return cls(
            plugin_id=plugin_id,
            api_version=api_version,
            status=PluginStatus.FAILED,
            duration_ms=duration_ms,
            diagnostics=diagnostics or [],
            error_traceback=error_traceback,
        )

    @classmethod
    def timeout(
        cls,
        plugin_id: str,
        api_version: str = "1.x",
        duration_ms: float = 0.0,
    ) -> PluginResult:
        """Create timeout result."""
        return cls(
            plugin_id=plugin_id,
            api_version=api_version,
            status=PluginStatus.TIMEOUT,
            duration_ms=duration_ms,
        )

    @classmethod
    def skipped(
        cls,
        plugin_id: str,
        api_version: str = "1.x",
        reason: str = "",
    ) -> PluginResult:
        """Create skipped result."""
        return cls(
            plugin_id=plugin_id,
            api_version=api_version,
            status=PluginStatus.SKIPPED,
            output_data={"skip_reason": reason} if reason else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "plugin_id": self.plugin_id,
            "api_version": self.api_version,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
        if self.output_data is not None:
            result["output_data"] = self.output_data
        if self.error_traceback is not None:
            result["error_traceback"] = self.error_traceback
        return result

    @property
    def has_errors(self) -> bool:
        """Check if result contains any error diagnostics."""
        return any(d.severity == "error" for d in self.diagnostics)

    @property
    def has_warnings(self) -> bool:
        """Check if result contains any warning diagnostics."""
        return any(d.severity == "warning" for d in self.diagnostics)


class PluginDataExchangeError(Exception):
    """Raised when plugin data exchange fails."""

    pass


class ContextAwareConfig(MutableMapping[str, Any]):
    """Context-local config view with backward-compatible dict semantics."""

    def __init__(
        self,
        base_data: Optional[dict[str, Any]] = None,
        scope_provider: Optional[Callable[[], PluginExecutionScope | None]] = None,
    ) -> None:
        self._base_data: dict[str, Any] = dict(base_data or {})
        self._scope_provider = scope_provider

    def bind_scope_provider(self, scope_provider: Callable[[], PluginExecutionScope | None]) -> None:
        self._scope_provider = scope_provider

    def _scoped_mapping(self) -> Mapping[str, Any] | None:
        if self._scope_provider is None:
            return None
        scope = self._scope_provider()
        if scope is None:
            return None
        return scope.config

    def __getitem__(self, key: str) -> Any:
        scoped = self._scoped_mapping()
        if scoped is not None and key in scoped:
            return scoped[key]
        return self._base_data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._base_data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._base_data[key]

    def __iter__(self) -> Iterator[str]:
        scoped = self._scoped_mapping()
        if scoped is None:
            return iter(self._base_data)
        merged = dict(self._base_data)
        merged.update(scoped)
        return iter(merged)

    def __len__(self) -> int:
        scoped = self._scoped_mapping()
        if scoped is None:
            return len(self._base_data)
        merged = dict(self._base_data)
        merged.update(scoped)
        return len(merged)

    def copy(self) -> dict[str, Any]:
        scoped = self._scoped_mapping()
        merged = dict(self._base_data)
        if scoped is not None:
            merged.update(scoped)
        return merged


@dataclass
class PluginContext:
    """Execution context passed to plugins.

    Contains all data needed for plugin execution, including:
    - Raw YAML data (for validator_yaml plugins)
    - Compiled JSON data (for validator_json and generator plugins)
    - Model lock and profile information
    - Plugin configuration
    - Output directory for generators

    Inter-Plugin Data Exchange (ADR 0065):
    - publish(key, value): Store data for dependent plugins to access
    - subscribe(plugin_id, key): Retrieve data from a plugin in depends_on list
    """

    # Core data
    topology_path: str
    profile: str
    model_lock: dict[str, Any]

    # Stage-specific data (populated as pipeline progresses)
    raw_yaml: dict[str, Any] = field(default_factory=dict)
    instance_bindings: dict[str, Any] = field(default_factory=dict)
    compiled_json: dict[str, Any] = field(default_factory=dict)

    # Module data
    classes: dict[str, Any] = field(default_factory=dict)
    objects: dict[str, Any] = field(default_factory=dict)
    capability_catalog: dict[str, Any] = field(default_factory=dict)

    # Derived data (populated by compile stage)
    effective_capabilities: dict[str, list[str]] = field(default_factory=dict)
    effective_software: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Plugin configuration (injected from manifest config)
    config: ContextAwareConfig | dict[str, Any] = field(default_factory=dict)

    # Output directory for generators
    output_dir: str = ""

    # Additional roots and release metadata for later lifecycle stages
    workspace_root: str = ""
    dist_root: str = ""
    assembly_manifest: dict[str, Any] = field(default_factory=dict)
    changed_input_scopes: list[str] | None = None
    signing_backend: str = ""
    release_tag: str = ""
    sbom_output_dir: str = ""

    # Error catalog for standardized messages
    error_catalog: dict[str, Any] = field(default_factory=dict)

    # Source file path (for validator_yaml plugins)
    source_file: str = ""

    # Compiled file path (for validator_json plugins)
    compiled_file: str = ""

    # Inter-plugin data exchange (ADR 0065)
    _published_data: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _published_meta: dict[tuple[str, str], PublishedDataMeta] = field(default_factory=dict, repr=False)
    _publish_events: list[PublishEvent] = field(default_factory=list, repr=False)
    _subscribe_events: list[SubscribeEvent] = field(default_factory=list, repr=False)
    _published_data_lock: Lock = field(default_factory=Lock, repr=False)
    _legacy_execution_tokens: list[Token[PluginExecutionScope | None]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.config, ContextAwareConfig):
            self.config.bind_scope_provider(self._get_execution_scope)
        else:
            self.config = ContextAwareConfig(dict(self.config), self._get_execution_scope)

    def _get_execution_scope(self) -> PluginExecutionScope | None:
        return _EXECUTION_SCOPE.get()

    @property
    def active_config(self) -> Mapping[str, Any]:
        scope = self._get_execution_scope()
        if scope is not None:
            return MappingProxyType(dict(scope.config))
        return MappingProxyType(self.config.copy())

    def _require_execution_scope(self) -> PluginExecutionScope:
        scope = self._get_execution_scope()
        if scope is None:
            raise PluginDataExchangeError(
                "no current plugin context: execution scope is not active. "
                "Ensure plugin is executing through registry."
            )
        return scope

    def publish(self, key: str, value: Any) -> None:
        """Publish data for dependent plugins to access.

        Args:
            key: Data key (namespaced under current plugin_id)
            value: Data value (must be JSON-serializable)

        Raises:
            PluginDataExchangeError: If no current plugin context is set
        """
        scope = self._require_execution_scope()
        with self._published_data_lock:
            if scope.plugin_id not in self._published_data:
                self._published_data[scope.plugin_id] = {}
            self._published_data[scope.plugin_id][key] = value
            declared_scope = scope.produced_key_scopes.get(key, "pipeline_shared")
            if declared_scope not in {"stage_local", "pipeline_shared"}:
                declared_scope = "pipeline_shared"
            self._published_meta[(scope.plugin_id, key)] = PublishedDataMeta(
                stage=scope.stage,
                phase=scope.phase,
                scope=declared_scope,
            )
            self._publish_events.append(
                PublishEvent(
                    plugin_id=scope.plugin_id,
                    key=key,
                    stage=scope.stage,
                    phase=scope.phase,
                )
            )

    def subscribe(self, plugin_id: str, key: str) -> Any:
        """Retrieve data published by another plugin.

        Args:
            plugin_id: ID of the plugin that published the data
            key: Data key to retrieve

        Returns:
            The published value

        Raises:
            PluginDataExchangeError: If dependency not allowed or data not found
        """
        scope = self._require_execution_scope()
        if plugin_id not in scope.allowed_dependencies:
            raise PluginDataExchangeError(
                f"Plugin '{scope.plugin_id}' cannot subscribe to '{plugin_id}': "
                f"not in depends_on list. Allowed: {sorted(scope.allowed_dependencies)}"
            )
        with self._published_data_lock:
            if plugin_id not in self._published_data:
                raise PluginDataExchangeError(
                    f"Plugin '{plugin_id}' has not published any data. " f"Ensure it runs before '{scope.plugin_id}'."
                )
            plugin_data = self._published_data[plugin_id]
            if key not in plugin_data:
                raise PluginDataExchangeError(
                    f"Plugin '{plugin_id}' has not published key '{key}'. "
                    f"Available keys: {sorted(plugin_data.keys())}"
                )
            meta = self._published_meta.get((plugin_id, key))
            if meta is not None and meta.scope == "stage_local" and meta.stage != scope.stage:
                raise PluginDataExchangeError(
                    f"Plugin '{scope.plugin_id}' cannot subscribe to stage_local key '{plugin_id}.{key}' "
                    f"from stage '{meta.stage.value}' while executing stage '{scope.stage.value}'."
                )
            self._subscribe_events.append(
                SubscribeEvent(
                    plugin_id=scope.plugin_id,
                    from_plugin=plugin_id,
                    key=key,
                    stage=scope.stage,
                    phase=scope.phase,
                )
            )
            return plugin_data[key]

    def get_published_keys(self, plugin_id: str) -> list[str]:
        """Get list of keys published by a plugin.

        Args:
            plugin_id: ID of the plugin

        Returns:
            List of published keys, or empty list if none
        """
        with self._published_data_lock:
            return list(self._published_data.get(plugin_id, {}).keys())

    def get_published_data(self) -> dict[str, dict[str, Any]]:
        """Return published data map for orchestrator/runtime consumers."""
        with self._published_data_lock:
            return {plugin_id: payload.copy() for plugin_id, payload in self._published_data.items()}

    def _get_publish_event_count(self) -> int:
        with self._published_data_lock:
            return len(self._publish_events)

    def _get_subscribe_event_count(self) -> int:
        with self._published_data_lock:
            return len(self._subscribe_events)

    def _get_publish_events_since(
        self,
        start_index: int,
        *,
        plugin_id: str,
        stage: Stage,
        phase: Phase,
    ) -> list[PublishEvent]:
        with self._published_data_lock:
            return [
                event
                for event in self._publish_events[start_index:]
                if event.plugin_id == plugin_id and event.stage == stage and event.phase == phase
            ]

    def _get_subscribe_events_since(
        self,
        start_index: int,
        *,
        plugin_id: str,
        stage: Stage,
        phase: Phase,
    ) -> list[SubscribeEvent]:
        with self._published_data_lock:
            return [
                event
                for event in self._subscribe_events[start_index:]
                if event.plugin_id == plugin_id and event.stage == stage and event.phase == phase
            ]

    def invalidate_stage_local_data(self, stage: Stage) -> list[str]:
        """Remove all keys declared as stage_local for the completed stage."""
        removed: list[str] = []
        with self._published_data_lock:
            for (plugin_id, key), meta in list(self._published_meta.items()):
                if meta.scope != "stage_local" or meta.stage != stage:
                    continue
                plugin_payload = self._published_data.get(plugin_id)
                if plugin_payload is not None and key in plugin_payload:
                    del plugin_payload[key]
                    if not plugin_payload:
                        del self._published_data[plugin_id]
                del self._published_meta[(plugin_id, key)]
                removed.append(f"{plugin_id}.{key}")
        return removed

    def _set_execution_scope(self, scope: PluginExecutionScope) -> Token[PluginExecutionScope | None]:
        """Bind per-invocation execution scope to the current worker context."""
        return _EXECUTION_SCOPE.set(scope)

    def _clear_execution_scope(self, token: Token[PluginExecutionScope | None]) -> None:
        """Reset worker-local execution scope after plugin completes."""
        _EXECUTION_SCOPE.reset(token)

    def _set_execution_context(
        self,
        plugin_id: str,
        allowed_dependencies: set[str],
        stage: Stage = Stage.VALIDATE,
        phase: Phase = Phase.RUN,
    ) -> None:
        """Legacy helper kept for test harnesses and direct plugin invocations."""
        allowed = frozenset(dep for dep in allowed_dependencies if isinstance(dep, str) and dep)
        scope = PluginExecutionScope(
            plugin_id=plugin_id,
            allowed_dependencies=allowed,
            phase=phase,
            stage=stage,
            config=self.config.copy(),
            produced_key_scopes={},
        )
        token = self._set_execution_scope(scope)
        self._legacy_execution_tokens.append(token)

    def _clear_execution_context(self) -> None:
        """Legacy counterpart to _set_execution_context()."""
        if not self._legacy_execution_tokens:
            return
        token = self._legacy_execution_tokens.pop()
        self._clear_execution_scope(token)


class PluginBase(ABC):
    """Base class for all v5 plugins.

    All plugins must inherit from this class and implement the execute() method.
    The plugin lifecycle is:
    1. Plugin class is loaded from entry point
    2. Plugin instance is created with plugin_id and api_version
    3. Config is validated against config_schema (if provided)
    4. execute() is called with PluginContext
    5. Plugin returns PluginResult with diagnostics and/or data
    """

    def __init__(self, plugin_id: str, api_version: str = "1.x") -> None:
        """Initialize plugin with its ID and API version."""
        self.plugin_id = plugin_id
        self.api_version = api_version

    @property
    @abstractmethod
    def kind(self) -> PluginKind:
        """Return the plugin kind."""
        ...

    @abstractmethod
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Execute the plugin for the given stage.

        Args:
            ctx: Plugin execution context with all required data
            stage: Current pipeline stage

        Returns:
            PluginResult with status, diagnostics, and optional output_data
        """
        ...

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return PluginResult.skipped(self.plugin_id, self.api_version, reason="phase 'init' not implemented")

    def on_pre(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return PluginResult.skipped(self.plugin_id, self.api_version, reason="phase 'pre' not implemented")

    def on_run(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

    def on_post(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return PluginResult.skipped(self.plugin_id, self.api_version, reason="phase 'post' not implemented")

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return PluginResult.skipped(self.plugin_id, self.api_version, reason="phase 'verify' not implemented")

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return PluginResult.skipped(self.plugin_id, self.api_version, reason="phase 'finalize' not implemented")

    def execute_phase(self, ctx: PluginContext, stage: Stage, phase: Phase) -> PluginResult:
        """Dispatch to a phase handler while keeping legacy execute() intact."""
        handler_name = f"on_{phase.value}"
        handler = getattr(self, handler_name, None)
        if callable(handler):
            return handler(ctx, stage)
        if phase == Phase.RUN:
            return self.execute(ctx, stage)
        return PluginResult.skipped(self.plugin_id, self.api_version, reason=f"phase '{phase.value}' not implemented")

    def emit_diagnostic(
        self,
        code: str,
        severity: str,
        stage: Stage,
        message: str,
        path: str,
        *,
        phase: Optional[Phase] = None,
        hint: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
        source_column: Optional[int] = None,
        confidence: float = 1.0,
    ) -> PluginDiagnostic:
        """Create a diagnostic message with plugin attribution."""
        return PluginDiagnostic(
            code=code,
            severity=severity,
            stage=stage.value,
            phase=phase.value if phase is not None else None,
            message=message,
            path=path,
            plugin_id=self.plugin_id,
            hint=hint,
            source_file=source_file,
            source_line=source_line,
            source_column=source_column,
            confidence=confidence,
        )

    def make_result(
        self,
        diagnostics: list[PluginDiagnostic],
        duration_ms: float = 0.0,
        output_data: Optional[dict[str, Any]] = None,
    ) -> PluginResult:
        """Create PluginResult based on diagnostics content."""
        has_errors = any(d.severity == "error" for d in diagnostics)
        has_warnings = any(d.severity == "warning" for d in diagnostics)

        if has_errors:
            status = PluginStatus.FAILED
        elif has_warnings:
            status = PluginStatus.PARTIAL
        else:
            status = PluginStatus.SUCCESS

        return PluginResult(
            plugin_id=self.plugin_id,
            api_version=self.api_version,
            status=status,
            duration_ms=duration_ms,
            diagnostics=diagnostics,
            output_data=output_data,
        )


class CompilerPlugin(PluginBase):
    """Plugin for transform/resolve hooks in compiler pipeline.

    Input: dict (parsed YAML Object Model)
    Output: dict (transformed Object Model in output_data)
    Runs in: compile stage
    Contract: Must not mutate input, return valid Object Model structure
    """

    @property
    def kind(self) -> PluginKind:
        return PluginKind.COMPILER


class ValidatorYamlPlugin(PluginBase):
    """Plugin for YAML source validation.

    Input: dict (parsed YAML), str (source file path via ctx.source_file)
    Output: List[PluginDiagnostic] (validation issues)
    Runs in: validate stage
    Contract: Must provide source location (line/column) when available
    """

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_YAML


class ValidatorJsonPlugin(PluginBase):
    """Plugin for compiled JSON contract validation.

    Input: dict (compiled JSON), str (compiled file path via ctx.compiled_file)
    Output: List[PluginDiagnostic] (consistency issues)
    Runs in: validate stage
    Contract: Should reference compiler data via ctx.subscribe(plugin_id, key)
    """

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON


class GeneratorPlugin(PluginBase):
    """Plugin for artifact generation/emission.

    Input: dict (compiled JSON), Path (output directory via ctx.output_dir)
    Output: File listing and metadata in output_data
    Runs in: generate stage
    Contract: Must create output_dir if not exists, support incremental generation
    """

    @property
    def kind(self) -> PluginKind:
        return PluginKind.GENERATOR


class AssemblerPlugin(PluginBase):
    """Plugin for execution-root assembly."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.ASSEMBLER


class BuilderPlugin(PluginBase):
    """Plugin for packaging and trust verification."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.BUILDER


# Legacy aliases for backward compatibility
Diagnostic = PluginDiagnostic
