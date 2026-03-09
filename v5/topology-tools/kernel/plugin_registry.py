"""Plugin registry and loader for v5 topology compiler (ADR 0063).

This module handles:
- Loading plugin manifests from YAML files
- Resolving plugin entry points to Python classes
- Building the plugin dependency graph
- Determining execution order
- Managing plugin lifecycle
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Type

import yaml

from .plugin_base import PluginBase, PluginKind, Stage

# Kernel API version - plugins must be compatible
KERNEL_API_VERSION = "1.x"


@dataclass
class PluginSpec:
    """Specification for a single plugin from manifest."""

    id: str
    kind: PluginKind
    entry: str
    api_version: str
    stages: list[Stage]
    order: int
    depends_on: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    config_schema: Optional[dict[str, Any]] = None
    profile_restrictions: Optional[list[str]] = None
    description: str = ""
    manifest_path: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], manifest_path: str = "") -> PluginSpec:
        """Create PluginSpec from manifest dictionary."""
        return cls(
            id=data["id"],
            kind=PluginKind(data["kind"]),
            entry=data["entry"],
            api_version=data["api_version"],
            stages=[Stage(s) for s in data["stages"]],
            order=data["order"],
            depends_on=data.get("depends_on", []),
            capabilities=data.get("capabilities", []),
            config_schema=data.get("config_schema"),
            profile_restrictions=data.get("profile_restrictions"),
            description=data.get("description", ""),
            manifest_path=manifest_path,
        )


@dataclass
class PluginManifest:
    """Parsed plugin manifest file."""

    schema_version: int
    plugins: list[PluginSpec]
    source_path: str

    @classmethod
    def from_file(cls, path: Path) -> PluginManifest:
        """Load manifest from YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if data.get("schema_version") != 1:
            raise ValueError(f"Unsupported manifest schema_version in {path}")

        plugins = [PluginSpec.from_dict(p, str(path)) for p in data.get("plugins", [])]
        return cls(
            schema_version=data["schema_version"],
            plugins=plugins,
            source_path=str(path),
        )


class PluginLoadError(Exception):
    """Error loading a plugin."""

    def __init__(self, plugin_id: str, message: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"Plugin '{plugin_id}': {message}")


class PluginCycleError(Exception):
    """Circular dependency detected in plugins."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(f"Circular plugin dependency: {' -> '.join(cycle)}")


class PluginRegistry:
    """Registry for loading, resolving, and managing plugins."""

    def __init__(self, base_path: Path) -> None:
        """Initialize registry with base path for resolving plugin entries."""
        self.base_path = base_path
        self.specs: dict[str, PluginSpec] = {}
        self.instances: dict[str, PluginBase] = {}
        self.manifests: list[str] = []
        self._load_errors: list[str] = []

    def load_manifest(self, manifest_path: Path) -> None:
        """Load plugins from a manifest file."""
        manifest = PluginManifest.from_file(manifest_path)
        self.manifests.append(str(manifest_path))

        for spec in manifest.plugins:
            if spec.id in self.specs:
                self._load_errors.append(f"Duplicate plugin ID: {spec.id}")
                continue
            self._validate_spec(spec)
            self.specs[spec.id] = spec

    def load_manifests_from_dir(self, search_dir: Path, pattern: str = "plugins.yaml") -> None:
        """Recursively load all plugin manifests from a directory."""
        for manifest_path in search_dir.rglob(pattern):
            try:
                self.load_manifest(manifest_path)
            except Exception as e:
                self._load_errors.append(f"Error loading {manifest_path}: {e}")

    def _validate_spec(self, spec: PluginSpec) -> None:
        """Validate plugin specification."""
        # Check API version compatibility
        if not self._is_api_compatible(spec.api_version):
            raise PluginLoadError(
                spec.id,
                f"Incompatible API version {spec.api_version}, kernel requires {KERNEL_API_VERSION}",
            )

    def _is_api_compatible(self, plugin_api: str) -> bool:
        """Check if plugin API version is compatible with kernel."""
        # Simple major version check: "1.x" is compatible with "1.x"
        kernel_major = KERNEL_API_VERSION.split(".")[0]
        plugin_major = plugin_api.split(".")[0]
        return kernel_major == plugin_major

    def resolve_dependencies(self) -> list[str]:
        """Resolve plugin dependencies and return execution order.

        Returns:
            List of plugin IDs in execution order

        Raises:
            PluginCycleError: If circular dependency detected
            PluginLoadError: If dependency not found
        """
        # Check all dependencies exist
        for spec in self.specs.values():
            for dep_id in spec.depends_on:
                if dep_id not in self.specs:
                    raise PluginLoadError(spec.id, f"Missing dependency: {dep_id}")

        # Topological sort with cycle detection
        visited: set[str] = set()
        in_stack: set[str] = set()
        order: list[str] = []

        def visit(plugin_id: str, path: list[str]) -> None:
            if plugin_id in in_stack:
                cycle_start = path.index(plugin_id)
                raise PluginCycleError(path[cycle_start:] + [plugin_id])

            if plugin_id in visited:
                return

            in_stack.add(plugin_id)
            path.append(plugin_id)

            for dep_id in self.specs[plugin_id].depends_on:
                visit(dep_id, path)

            path.pop()
            in_stack.remove(plugin_id)
            visited.add(plugin_id)
            order.append(plugin_id)

        for plugin_id in self.specs:
            if plugin_id not in visited:
                visit(plugin_id, [])

        return order

    def get_execution_order(self, stage: Stage, profile: Optional[str] = None) -> list[str]:
        """Get plugins to execute for a stage, in order.

        Args:
            stage: Pipeline stage
            profile: Current execution profile (for filtering)

        Returns:
            List of plugin IDs in execution order
        """
        # Filter plugins for this stage
        stage_plugins = [
            spec
            for spec in self.specs.values()
            if stage in spec.stages
            and (spec.profile_restrictions is None or profile is None or profile in spec.profile_restrictions)
        ]

        # Sort by: dependency order, then numeric order, then ID (for stability)
        dep_order = {pid: idx for idx, pid in enumerate(self.resolve_dependencies())}

        def sort_key(spec: PluginSpec) -> tuple[int, int, str]:
            return (dep_order.get(spec.id, 9999), spec.order, spec.id)

        stage_plugins.sort(key=sort_key)
        return [spec.id for spec in stage_plugins]

    def load_plugin(self, plugin_id: str) -> PluginBase:
        """Load and instantiate a plugin by ID.

        Args:
            plugin_id: Plugin ID to load

        Returns:
            Instantiated plugin

        Raises:
            PluginLoadError: If plugin cannot be loaded
        """
        if plugin_id in self.instances:
            return self.instances[plugin_id]

        if plugin_id not in self.specs:
            raise PluginLoadError(plugin_id, "Plugin not found in registry")

        spec = self.specs[plugin_id]
        plugin_class = self._load_entry_point(spec)
        instance = plugin_class(plugin_id)

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

        Entry format: "path/to/module.py:ClassName"
        """
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

        return plugin_class

    def get_load_errors(self) -> list[str]:
        """Return any errors encountered during manifest loading."""
        return self._load_errors.copy()

    def get_stats(self) -> dict[str, Any]:
        """Return registry statistics."""
        by_kind: dict[str, int] = {}
        for spec in self.specs.values():
            kind = spec.kind.value
            by_kind[kind] = by_kind.get(kind, 0) + 1

        return {
            "loaded": len(self.specs),
            "executed": len(self.instances),
            "failed": len(self._load_errors),
            "by_kind": by_kind,
            "manifests": self.manifests,
        }
