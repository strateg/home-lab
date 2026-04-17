"""v5 Topology Compiler Kernel - Plugin Microkernel Architecture (ADR 0063).

This package provides the plugin microkernel for the v5 topology compiler.
It handles plugin loading, dependency resolution, execution with timeout,
and diagnostics aggregation.
"""

from __future__ import annotations

__version__ = "0.5.0"
__api_version__ = "1.0"

from .plugin_base import (  # Legacy alias
    AssemblerPlugin,
    BuilderPlugin,
    CompilerPlugin,
    Diagnostic,
    DiscovererPlugin,
    EmittedEvent,
    GeneratorPlugin,
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
    PublishedMessage,
    Stage,
    SubscriptionValue,
    ValidatorJsonPlugin,
    ValidatorYamlPlugin,
)
from .pipeline_runtime import PipelineState
from .plugin_runner import run_plugin_once
from .plugin_registry import (
    DEFAULT_PLUGIN_TIMEOUT,
    KERNEL_API_VERSION,
    KERNEL_VERSION,
    STAGE_ORDER,
    SUPPORTED_API_VERSIONS,
    PluginConfigError,
    PluginCycleError,
    PluginLoadError,
    PluginManifest,
    PluginRegistry,
    PluginSpec,
)

__all__ = [
    # Version info
    "__version__",
    "__api_version__",
    # Plugin base classes
    "PluginBase",
    "PluginKind",
    "PluginStatus",
    "PluginContext",
    "PluginExecutionScope",
    "PluginResult",
    "PluginDiagnostic",
    "PluginDataExchangeError",
    "PluginInputSnapshot",
    "SubscriptionValue",
    "PublishedMessage",
    "EmittedEvent",
    "PluginExecutionEnvelope",
    "Stage",
    "Phase",
    # Plugin type classes
    "CompilerPlugin",
    "DiscovererPlugin",
    "ValidatorYamlPlugin",
    "ValidatorJsonPlugin",
    "GeneratorPlugin",
    "AssemblerPlugin",
    "BuilderPlugin",
    # Registry
    "PluginRegistry",
    "PluginManifest",
    "PluginSpec",
    "PipelineState",
    "run_plugin_once",
    # Exceptions
    "PluginLoadError",
    "PluginCycleError",
    "PluginConfigError",
    # Constants
    "KERNEL_VERSION",
    "KERNEL_API_VERSION",
    "SUPPORTED_API_VERSIONS",
    "DEFAULT_PLUGIN_TIMEOUT",
    "STAGE_ORDER",
    # Legacy
    "Diagnostic",
]
