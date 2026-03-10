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
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class PluginKind(str, Enum):
    """Plugin kind determining execution context."""

    COMPILER = "compiler"
    VALIDATOR_YAML = "validator_yaml"
    VALIDATOR_JSON = "validator_json"
    GENERATOR = "generator"


class Stage(str, Enum):
    """Pipeline stages where plugins can execute."""

    VALIDATE = "validate"
    COMPILE = "compile"
    GENERATE = "generate"


class PluginStatus(str, Enum):
    """Plugin execution status."""

    SUCCESS = "SUCCESS"    # All checks passed, no errors
    PARTIAL = "PARTIAL"    # Some checks passed, some warnings
    FAILED = "FAILED"      # Plugin execution failed with errors
    TIMEOUT = "TIMEOUT"    # Plugin exceeded timeout limit
    SKIPPED = "SKIPPED"    # Plugin skipped (dependency failed, config invalid)


@dataclass
class PluginDiagnostic:
    """Single diagnostic message emitted by a plugin."""

    code: str
    severity: str  # "error" | "warning" | "info"
    stage: str
    message: str
    path: str
    plugin_id: str
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
    config: dict[str, Any] = field(default_factory=dict)

    # Output directory for generators
    output_dir: str = ""

    # Error catalog for standardized messages
    error_catalog: dict[str, Any] = field(default_factory=dict)

    # Source file path (for validator_yaml plugins)
    source_file: str = ""

    # Compiled file path (for validator_json plugins)
    compiled_file: str = ""

    # Previous plugin outputs (for inter-plugin communication) - legacy
    plugin_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Inter-plugin data exchange (ADR 0065)
    # Set by registry before plugin execution
    _current_plugin_id: str = field(default="", repr=False)
    _allowed_dependencies: set[str] = field(default_factory=set, repr=False)
    _published_data: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    def publish(self, key: str, value: Any) -> None:
        """Publish data for dependent plugins to access.

        Args:
            key: Data key (namespaced under current plugin_id)
            value: Data value (must be JSON-serializable)

        Raises:
            PluginDataExchangeError: If no current plugin context is set
        """
        if not self._current_plugin_id:
            raise PluginDataExchangeError(
                "Cannot publish: no current plugin context. "
                "Ensure plugin is executing through registry."
            )
        if self._current_plugin_id not in self._published_data:
            self._published_data[self._current_plugin_id] = {}
        self._published_data[self._current_plugin_id][key] = value

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
        if not self._current_plugin_id:
            raise PluginDataExchangeError(
                "Cannot subscribe: no current plugin context. "
                "Ensure plugin is executing through registry."
            )
        if plugin_id not in self._allowed_dependencies:
            raise PluginDataExchangeError(
                f"Plugin '{self._current_plugin_id}' cannot subscribe to '{plugin_id}': "
                f"not in depends_on list. Allowed: {sorted(self._allowed_dependencies)}"
            )
        if plugin_id not in self._published_data:
            raise PluginDataExchangeError(
                f"Plugin '{plugin_id}' has not published any data. "
                f"Ensure it runs before '{self._current_plugin_id}'."
            )
        plugin_data = self._published_data[plugin_id]
        if key not in plugin_data:
            raise PluginDataExchangeError(
                f"Plugin '{plugin_id}' has not published key '{key}'. "
                f"Available keys: {sorted(plugin_data.keys())}"
            )
        return plugin_data[key]

    def get_published_keys(self, plugin_id: str) -> list[str]:
        """Get list of keys published by a plugin.

        Args:
            plugin_id: ID of the plugin

        Returns:
            List of published keys, or empty list if none
        """
        return list(self._published_data.get(plugin_id, {}).keys())

    def _set_execution_context(
        self,
        plugin_id: str,
        allowed_dependencies: set[str],
    ) -> None:
        """Set execution context for a plugin (called by registry).

        Args:
            plugin_id: ID of the plugin about to execute
            allowed_dependencies: Set of plugin IDs this plugin can subscribe to
        """
        self._current_plugin_id = plugin_id
        self._allowed_dependencies = allowed_dependencies

    def _clear_execution_context(self) -> None:
        """Clear execution context after plugin completes (called by registry)."""
        self._current_plugin_id = ""
        self._allowed_dependencies = set()


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

    def emit_diagnostic(
        self,
        code: str,
        severity: str,
        stage: Stage,
        message: str,
        path: str,
        *,
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
    Contract: May reference outputs from compiler plugins via ctx.plugin_outputs
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


# Legacy aliases for backward compatibility
Diagnostic = PluginDiagnostic
