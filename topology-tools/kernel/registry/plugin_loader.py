"""Plugin class loader (ADR 0063 registry decomposition).

This module handles loading plugin classes from entry point specifications.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Type

from ..plugin_base import PluginBase

if TYPE_CHECKING:
    from ..specs import PluginSpec

__all__ = ["PluginLoader", "PluginLoadError"]


class PluginLoadError(Exception):
    """Error loading a plugin."""

    def __init__(self, plugin_id: str, message: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"Plugin '{plugin_id}': {message}")


class PluginLoader:
    """Load plugin classes from entry point specifications."""

    def __init__(self, base_path: Path) -> None:
        """Initialize loader.

        Args:
            base_path: Base path for resolving plugin entry points
        """
        self.base_path = base_path
        self._instances: dict[str, PluginBase] = {}
        self._classes: dict[str, Type[PluginBase]] = {}
        self._lock = threading.Lock()
        self._import_paths: set[str] = set()

    @property
    def instances(self) -> dict[str, PluginBase]:
        """Return loaded plugin instances."""
        return self._instances

    def get_instance(self, plugin_id: str) -> PluginBase | None:
        """Get cached plugin instance if exists."""
        return self._instances.get(plugin_id)

    def load(
        self,
        spec: PluginSpec,
        config_validator: Any = None,
    ) -> PluginBase:
        """Load and instantiate a plugin.

        Args:
            spec: Plugin specification
            config_validator: Optional callable to validate config before loading

        Returns:
            Instantiated plugin

        Raises:
            PluginLoadError: If plugin cannot be loaded
        """
        with self._lock:
            if spec.id in self._instances:
                return self._instances[spec.id]

            # Validate config if validator provided
            if config_validator:
                config_errors = config_validator(spec.id)
                if config_errors:
                    from .config_validator import ConfigValidationError

                    raise ConfigValidationError(spec.id, "; ".join(config_errors))

            plugin_class = self._load_entry_point(spec)
            instance = plugin_class(spec.id, spec.api_version)

            # Verify plugin kind matches spec
            if instance.kind != spec.kind:
                raise PluginLoadError(
                    spec.id,
                    f"Plugin kind mismatch: spec declares {spec.kind.value}, " f"class returns {instance.kind.value}",
                )

            self._instances[spec.id] = instance
            return instance

    def _load_entry_point(self, spec: PluginSpec) -> Type[PluginBase]:
        """Load plugin class from entry point specification.

        Entry format: "path/to/module.py:ClassName"
        """
        # Check cache first
        if spec.id in self._classes:
            return self._classes[spec.id]

        try:
            module_path, class_name = spec.entry.rsplit(":", 1)
        except ValueError:
            raise PluginLoadError(spec.id, f"Invalid entry format: {spec.entry}")

        # Resolve module path relative to manifest location
        manifest_dir = Path(spec.manifest_path).parent
        full_module_path = manifest_dir / module_path

        if not full_module_path.exists():
            # Try relative to base_path
            full_module_path = self.base_path / module_path
            if not full_module_path.exists():
                raise PluginLoadError(spec.id, f"Module not found: {module_path}")

        # Module-level plugins may import sibling helpers; keep module directory importable
        self._ensure_import_path(full_module_path.parent)

        # Load module dynamically
        module_name = f"_plugin_{spec.id.replace('.', '_')}"
        spec_obj = importlib.util.spec_from_file_location(module_name, full_module_path)
        if spec_obj is None or spec_obj.loader is None:
            raise PluginLoadError(spec.id, f"Cannot load module: {full_module_path}")

        module = importlib.util.module_from_spec(spec_obj)
        sys.modules[module_name] = module
        spec_obj.loader.exec_module(module)

        # Get class from module
        if not hasattr(module, class_name):
            raise PluginLoadError(spec.id, f"Class '{class_name}' not found in {module_path}")

        plugin_class = getattr(module, class_name)
        if not isinstance(plugin_class, type) or not issubclass(plugin_class, PluginBase):
            raise PluginLoadError(spec.id, f"'{class_name}' is not a PluginBase subclass")

        self._classes[spec.id] = plugin_class
        return plugin_class

    def _ensure_import_path(self, path: Path) -> None:
        """Add directory to import path if not already present."""
        path_str = str(path.resolve())
        if path_str in self._import_paths:
            return
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
        self._import_paths.add(path_str)

    def preload(self, specs: list[PluginSpec]) -> None:
        """Preload plugin classes (without instantiation).

        Args:
            specs: List of plugin specs to preload
        """
        for spec in specs:
            if spec.id not in self._classes:
                try:
                    self._load_entry_point(spec)
                except PluginLoadError:
                    pass  # Will be raised again when load() is called

    def clear_instances(self) -> None:
        """Clear all cached instances (for testing)."""
        with self._lock:
            self._instances.clear()
