"""Base plugin interfaces for v5 topology compiler (ADR 0063).

This module defines the plugin contract that all v5 plugins must implement.
Plugins are the primary extension mechanism for the compiler pipeline.
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

    LOAD = "load"
    NORMALIZE = "normalize"
    RESOLVE = "resolve"
    VALIDATE = "validate"
    EMIT = "emit"


@dataclass
class Diagnostic:
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
            result["source"] = source
        if self.related:
            result["related"] = self.related
        return result


@dataclass
class PluginResult:
    """Result of plugin execution."""

    success: bool
    diagnostics: list[Diagnostic] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    @classmethod
    def ok(cls, diagnostics: Optional[list[Diagnostic]] = None, data: Optional[dict[str, Any]] = None) -> PluginResult:
        """Create successful result."""
        return cls(success=True, diagnostics=diagnostics or [], data=data or {})

    @classmethod
    def fail(cls, message: str, diagnostics: Optional[list[Diagnostic]] = None) -> PluginResult:
        """Create failed result."""
        return cls(success=False, diagnostics=diagnostics or [], error_message=message)


@dataclass
class PluginContext:
    """Execution context passed to plugins.

    Contains all data needed for plugin execution, including:
    - Raw YAML data (for validator_yaml plugins)
    - Compiled JSON data (for validator_json and generator plugins)
    - Model lock and profile information
    - Diagnostics collector
    - Plugin configuration
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

    # Derived data (populated by resolve stage)
    effective_capabilities: dict[str, list[str]] = field(default_factory=dict)
    effective_software: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Plugin configuration
    config: dict[str, Any] = field(default_factory=dict)

    # Output directory for generators
    output_dir: str = ""

    # Error catalog for standardized messages
    error_catalog: dict[str, Any] = field(default_factory=dict)


class PluginBase(ABC):
    """Base class for all v5 plugins.

    All plugins must inherit from this class and implement the execute() method.
    The plugin lifecycle is:
    1. Plugin class is loaded from entry point
    2. Plugin instance is created with plugin_id
    3. execute() is called with PluginContext
    4. Plugin returns PluginResult with diagnostics and/or data
    """

    def __init__(self, plugin_id: str) -> None:
        """Initialize plugin with its ID."""
        self.plugin_id = plugin_id

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
            PluginResult with success status, diagnostics, and optional data
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
        confidence: float = 1.0,
    ) -> Diagnostic:
        """Create a diagnostic message with plugin attribution."""
        return Diagnostic(
            code=code,
            severity=severity,
            stage=stage.value,
            message=message,
            path=path,
            plugin_id=self.plugin_id,
            hint=hint,
            source_file=source_file,
            source_line=source_line,
            confidence=confidence,
        )


class CompilerPlugin(PluginBase):
    """Plugin for transform/resolve hooks in compiler pipeline."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.COMPILER


class ValidatorYamlPlugin(PluginBase):
    """Plugin for YAML source validation."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_YAML


class ValidatorJsonPlugin(PluginBase):
    """Plugin for compiled JSON contract validation."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.VALIDATOR_JSON


class GeneratorPlugin(PluginBase):
    """Plugin for artifact generation/emission."""

    @property
    def kind(self) -> PluginKind:
        return PluginKind.GENERATOR
