"""Plugin registry submodules (ADR 0063 decomposition).

This package provides modular components for the plugin registry:

- manifest_loader: Load and validate plugin manifests
- spec_validator: Validate plugin specifications
- dependency_resolver: Resolve plugin dependency graph
- plugin_loader: Load plugin classes from entry points
- config_validator: Validate plugin configuration
- envelope_validator: Validate plugin execution envelopes

Usage:
    from kernel.registry import ManifestLoader, SpecValidator
    from kernel.registry import DependencyResolver, PluginLoader
    from kernel.registry import ConfigValidator, EnvelopeValidator
"""

from __future__ import annotations

from .config_validator import ConfigValidationError, ConfigValidator
from .dependency_resolver import DependencyError, DependencyResolver, PluginCycleError
from .envelope_validator import EnvelopeValidator
from .manifest_loader import ManifestLoadError, ManifestLoader, PluginManifest
from .plugin_loader import PluginLoadError, PluginLoader
from .spec_validator import (
    ENTRY_FAMILIES,
    KIND_ENTRY_FAMILY,
    KIND_STAGE_AFFINITY,
    PHASE_ORDER,
    STAGE_ORDER,
    STAGE_ORDER_RANGES,
    SUPPORTED_API_VERSIONS,
    SpecValidationError,
    SpecValidator,
)

__all__ = [
    # manifest_loader
    "ManifestLoader",
    "ManifestLoadError",
    "PluginManifest",
    # spec_validator
    "SpecValidator",
    "SpecValidationError",
    "SUPPORTED_API_VERSIONS",
    "STAGE_ORDER",
    "PHASE_ORDER",
    "STAGE_ORDER_RANGES",
    "KIND_STAGE_AFFINITY",
    "KIND_ENTRY_FAMILY",
    "ENTRY_FAMILIES",
    # dependency_resolver
    "DependencyResolver",
    "DependencyError",
    "PluginCycleError",
    # plugin_loader
    "PluginLoader",
    "PluginLoadError",
    # config_validator
    "ConfigValidator",
    "ConfigValidationError",
    # envelope_validator
    "EnvelopeValidator",
]
