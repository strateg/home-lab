"""Plugin registry submodules.

This package provides modular components for the plugin registry:

- manifest_loader: Load and validate plugin manifests
- spec_validator: Validate plugin specifications
- dependency_resolver: Resolve plugin dependency graph
- plugin_loader: Load plugin classes from entry points
- config_validator: Validate plugin configuration

Usage:
    from kernel.registry import ManifestLoader, SpecValidator
    # Or import from main plugin_registry for backwards compatibility
"""

from __future__ import annotations

# Re-exports for backwards compatibility
# These will be populated as modules are extracted

__all__ = [
    "ManifestLoader",
    "SpecValidator",
    "DependencyResolver",
    "PluginLoader",
    "ConfigValidator",
]

# Lazy imports - will be implemented as extraction proceeds
# For now, import from parent module for compatibility


def __getattr__(name: str):
    """Lazy import for backwards compatibility during migration."""
    if name in __all__:
        # During migration, classes remain in plugin_registry.py
        # This will be updated as extraction completes
        raise ImportError(
            f"{name} not yet extracted. Import from kernel.plugin_registry instead."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
