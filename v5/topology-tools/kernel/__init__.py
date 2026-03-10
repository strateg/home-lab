"""v5 Topology Compiler Kernel - Plugin Microkernel Architecture (ADR 0063).

This package provides the plugin microkernel for the v5 topology compiler.
It handles plugin loading, dependency resolution, execution with timeout,
and diagnostics aggregation.
"""

from __future__ import annotations

__version__ = "0.5.0"
__api_version__ = "1.0"

from .plugin_base import (
    PluginBase,
    PluginKind,
    PluginStatus,
    PluginContext,
    PluginResult,
    PluginDiagnostic,
    PluginDataExchangeError,
    Stage,
    CompilerPlugin,
    ValidatorYamlPlugin,
    ValidatorJsonPlugin,
    GeneratorPlugin,
    # Legacy alias
    Diagnostic,
)
from .plugin_registry import (
    PluginRegistry,
    PluginManifest,
    PluginSpec,
    PluginLoadError,
    PluginCycleError,
    PluginConfigError,
    KERNEL_VERSION,
    KERNEL_API_VERSION,
    SUPPORTED_API_VERSIONS,
    DEFAULT_PLUGIN_TIMEOUT,
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
    "PluginResult",
    "PluginDiagnostic",
    "PluginDataExchangeError",
    "Stage",
    # Plugin type classes
    "CompilerPlugin",
    "ValidatorYamlPlugin",
    "ValidatorJsonPlugin",
    "GeneratorPlugin",
    # Registry
    "PluginRegistry",
    "PluginManifest",
    "PluginSpec",
    # Exceptions
    "PluginLoadError",
    "PluginCycleError",
    "PluginConfigError",
    # Constants
    "KERNEL_VERSION",
    "KERNEL_API_VERSION",
    "SUPPORTED_API_VERSIONS",
    "DEFAULT_PLUGIN_TIMEOUT",
    # Legacy
    "Diagnostic",
]
