"""v5 Topology Compiler Kernel - Plugin Microkernel Architecture (ADR 0063)."""

from __future__ import annotations

__version__ = "1.0.0"
__api_version__ = "1.x"

from .plugin_base import (
    PluginBase,
    PluginKind,
    PluginContext,
    PluginResult,
    CompilerPlugin,
    ValidatorYamlPlugin,
    ValidatorJsonPlugin,
    GeneratorPlugin,
)
from .plugin_registry import PluginRegistry, PluginManifest, PluginSpec

__all__ = [
    "__version__",
    "__api_version__",
    "PluginBase",
    "PluginKind",
    "PluginContext",
    "PluginResult",
    "CompilerPlugin",
    "ValidatorYamlPlugin",
    "ValidatorJsonPlugin",
    "GeneratorPlugin",
    "PluginRegistry",
    "PluginManifest",
    "PluginSpec",
]
