"""Plugin registry and loader for v5 topology compiler (ADR 0063).

This module handles:
- Loading plugin manifests from YAML files
- Resolving plugin entry points to Python classes
- Building the plugin dependency graph
- Determining execution order
- Managing plugin lifecycle
- Config validation against config_schema
- Timeout handling
- Error recovery with traceback capture
"""

from __future__ import annotations

import concurrent.futures
import heapq
import importlib.util
import json
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Type

import yaml

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from .plugin_base import PluginBase, PluginContext, PluginDiagnostic, PluginKind, PluginResult, PluginStatus, Stage

# Kernel version and compatibility matrix
KERNEL_VERSION = "0.5.0"
KERNEL_API_VERSION = "1.0"
SUPPORTED_API_VERSIONS = ["1.x"]
MODEL_VERSIONS = ["0062-1.0"]
EXECUTION_PROFILES = ["production", "modeled", "test-real"]

# Default timeout for plugin execution (seconds)
DEFAULT_PLUGIN_TIMEOUT = 30.0


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
    requires_capabilities: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    config_schema: Optional[dict[str, Any]] = None
    profile_restrictions: Optional[list[str]] = None
    model_versions: list[str] = field(default_factory=list)
    description: str = ""
    manifest_path: str = ""
    timeout: float = DEFAULT_PLUGIN_TIMEOUT

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
            requires_capabilities=data.get("requires_capabilities", []),
            config=data.get("config", {}),
            config_schema=data.get("config_schema"),
            profile_restrictions=data.get("profile_restrictions"),
            model_versions=data.get("model_versions", []),
            description=data.get("description", ""),
            manifest_path=manifest_path,
            timeout=data.get("timeout", DEFAULT_PLUGIN_TIMEOUT),
        )


@dataclass
class PluginManifest:
    """Parsed plugin manifest file."""

    schema_version: int
    plugins: list[PluginSpec]
    source_path: str

    @classmethod
    def from_data(cls, data: dict[str, Any], source_path: str) -> PluginManifest:
        """Load manifest from parsed dictionary."""
        if data.get("schema_version") != 1:
            raise ValueError(f"Unsupported manifest schema_version in {source_path}")

        plugins = [PluginSpec.from_dict(p, source_path) for p in data.get("plugins", [])]
        return cls(
            schema_version=data["schema_version"],
            plugins=plugins,
            source_path=source_path,
        )

    @classmethod
    def from_file(cls, path: Path) -> PluginManifest:
        """Load manifest from YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_data(data, str(path))


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


class PluginConfigError(Exception):
    """Plugin configuration validation error."""

    def __init__(self, plugin_id: str, message: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"Plugin '{plugin_id}' config error: {message}")


class PluginRegistry:
    """Registry for loading, resolving, and managing plugins."""

    def __init__(self, base_path: Path) -> None:
        """Initialize registry with base path for resolving plugin entries."""
        self.base_path = base_path
        self.manifest_schema_path = self.base_path / "schemas" / "plugin-manifest.schema.json"
        self._manifest_schema: Optional[dict[str, Any]] = None
        self.specs: dict[str, PluginSpec] = {}
        self.instances: dict[str, PluginBase] = {}
        self.manifests: list[str] = []
        self._load_errors: list[str] = []
        self._results: list[PluginResult] = []

    def _get_manifest_schema(self) -> dict[str, Any]:
        if self._manifest_schema is not None:
            return self._manifest_schema

        if not HAS_JSONSCHEMA:
            raise PluginLoadError(
                "manifest.schema",
                "jsonschema dependency is required for plugin manifest validation.",
            )
        if not self.manifest_schema_path.exists():
            raise PluginLoadError(
                "manifest.schema",
                f"Plugin manifest schema not found: {self.manifest_schema_path}",
            )
        try:
            self._manifest_schema = json.loads(self.manifest_schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginLoadError(
                "manifest.schema",
                f"Failed to load plugin manifest schema '{self.manifest_schema_path}': {exc}",
            ) from exc
        return self._manifest_schema

    def _validate_manifest_payload(self, payload: dict[str, Any], *, manifest_path: Path) -> None:
        schema = self._get_manifest_schema()
        try:
            jsonschema.validate(payload, schema)
        except jsonschema.ValidationError as exc:
            raise PluginLoadError(
                "manifest.schema",
                f"Manifest schema validation failed for {manifest_path}: {exc.message}",
            ) from exc

    def load_manifest(self, manifest_path: Path) -> None:
        """Load plugins from a manifest file."""
        try:
            with open(manifest_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise PluginLoadError("manifest.load", f"Failed to parse manifest '{manifest_path}': {exc}") from exc
        if not isinstance(payload, dict):
            raise PluginLoadError("manifest.load", f"Manifest root must be mapping/object: {manifest_path}")

        self._validate_manifest_payload(payload, manifest_path=manifest_path)
        manifest = PluginManifest.from_data(payload, str(manifest_path))
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
                f"Incompatible API version {spec.api_version}, kernel supports {SUPPORTED_API_VERSIONS}",
            )

    def _is_api_compatible(self, plugin_api: str) -> bool:
        """Check if plugin API version is compatible with kernel.

        A plugin with api_version "1.x" is compatible with kernel supporting "1.x".
        Major version must match.
        """
        plugin_major = plugin_api.split(".")[0]
        for supported in SUPPORTED_API_VERSIONS:
            kernel_major = supported.split(".")[0]
            if plugin_major == kernel_major:
                return True
        return False

    def validate_plugin_config(self, plugin_id: str) -> list[str]:
        """Validate plugin config against its config_schema.

        Returns list of validation errors (empty if valid).
        """
        if plugin_id not in self.specs:
            return [f"Plugin not found: {plugin_id}"]

        spec = self.specs[plugin_id]
        if not spec.config_schema:
            return []  # No schema to validate against

        if not HAS_JSONSCHEMA:
            return []  # Skip validation if jsonschema not available

        errors: list[str] = []
        try:
            jsonschema.validate(instance=spec.config, schema=spec.config_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Config validation failed: {e.message}")
        except jsonschema.SchemaError as e:
            errors.append(f"Invalid config_schema: {e.message}")

        return errors

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
        # Validate dependency graph globally (missing deps / cycles).
        # Ordering itself is then resolved stage-locally.
        self.resolve_dependencies()

        # Filter plugins for this stage
        stage_plugins = {
            spec.id: spec
            for spec in self.specs.values()
            if stage in spec.stages
            and (spec.profile_restrictions is None or profile is None or profile in spec.profile_restrictions)
        }
        if not stage_plugins:
            return []

        # Stage-local topological ordering with deterministic ready-queue policy:
        # depends_on -> order -> lexical id.
        indegree: dict[str, int] = {plugin_id: 0 for plugin_id in stage_plugins}
        outgoing: dict[str, list[str]] = {plugin_id: [] for plugin_id in stage_plugins}

        for plugin_id, spec in stage_plugins.items():
            for dep_id in spec.depends_on:
                if dep_id not in stage_plugins:
                    # Cross-stage dependency: already validated globally; not part of this stage DAG.
                    continue
                indegree[plugin_id] += 1
                outgoing[dep_id].append(plugin_id)

        ready: list[tuple[int, str]] = []
        for plugin_id, spec in stage_plugins.items():
            if indegree[plugin_id] == 0:
                heapq.heappush(ready, (spec.order, plugin_id))

        ordered: list[str] = []
        while ready:
            _, plugin_id = heapq.heappop(ready)
            ordered.append(plugin_id)
            for dependent_id in outgoing[plugin_id]:
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    dependent_spec = stage_plugins[dependent_id]
                    heapq.heappush(ready, (dependent_spec.order, dependent_id))

        if len(ordered) != len(stage_plugins):
            # Should not happen because global cycle check already ran, but keep defensive guard.
            remaining = sorted(plugin_id for plugin_id, degree in indegree.items() if degree > 0)
            raise PluginCycleError(remaining)

        return ordered

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

        # Validate config before loading
        config_errors = self.validate_plugin_config(plugin_id)
        if config_errors:
            raise PluginConfigError(plugin_id, "; ".join(config_errors))

        plugin_class = self._load_entry_point(spec)
        instance = plugin_class(plugin_id, spec.api_version)

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

    def execute_plugin(
        self,
        plugin_id: str,
        ctx: PluginContext,
        stage: Stage,
        timeout: Optional[float] = None,
    ) -> PluginResult:
        """Execute a single plugin with timeout and error handling.

        Args:
            plugin_id: Plugin ID to execute
            ctx: Execution context
            stage: Current pipeline stage
            timeout: Timeout in seconds (uses plugin spec timeout if None)

        Returns:
            PluginResult with execution status and diagnostics
        """
        if plugin_id not in self.specs:
            return PluginResult.failed(
                plugin_id=plugin_id,
                diagnostics=[
                    PluginDiagnostic(
                        code="E4004",
                        severity="error",
                        stage=stage.value,
                        message=f"Plugin not found: {plugin_id}",
                        path="kernel",
                        plugin_id="kernel",
                    )
                ],
            )

        spec = self.specs[plugin_id]
        effective_timeout = timeout if timeout is not None else spec.timeout

        # Merge plugin config defaults with runtime config.
        # Runtime values (already present in ctx.config) take precedence.
        base_config = ctx.config.copy()
        ctx.config = {**spec.config, **base_config}

        try:
            plugin = self.load_plugin(plugin_id)
        except (PluginLoadError, PluginConfigError) as e:
            ctx.config = base_config
            return PluginResult.failed(
                plugin_id=plugin_id,
                api_version=spec.api_version,
                diagnostics=[
                    PluginDiagnostic(
                        code="E4004",
                        severity="error",
                        stage=stage.value,
                        message=str(e),
                        path="kernel",
                        plugin_id="kernel",
                    )
                ],
            )

        # Set execution context for inter-plugin data exchange (ADR 0065)
        allowed_deps = set(spec.depends_on)
        ctx._set_execution_context(plugin_id, allowed_deps)
        execution_context_set = True

        # Execute with timeout
        start_time = time.perf_counter()
        timed_out = False
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        try:
            future = executor.submit(plugin.execute, ctx, stage)
            try:
                result = future.result(timeout=effective_timeout)
                duration_ms = (time.perf_counter() - start_time) * 1000
                # Update duration in result
                result.duration_ms = duration_ms
                self._results.append(result)
                return result
            except concurrent.futures.TimeoutError:
                timed_out = True
                future.cancel()
                duration_ms = (time.perf_counter() - start_time) * 1000
                result = PluginResult.timeout(
                    plugin_id=plugin_id,
                    api_version=spec.api_version,
                    duration_ms=duration_ms,
                )
                result.diagnostics.append(
                    PluginDiagnostic(
                        code="E4102",
                        severity="error",
                        stage=stage.value,
                        message=f"Plugin exceeded timeout of {effective_timeout}s",
                        path="kernel",
                        plugin_id="kernel",
                    )
                )
                self._results.append(result)
                return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            tb = traceback.format_exc()
            result = PluginResult.failed(
                plugin_id=plugin_id,
                api_version=spec.api_version,
                duration_ms=duration_ms,
                error_traceback=tb,
                diagnostics=[
                    PluginDiagnostic(
                        code="E4102",
                        severity="error",
                        stage=stage.value,
                        message=f"Plugin crashed: {e}",
                        path="kernel",
                        plugin_id="kernel",
                    )
                ],
            )
            self._results.append(result)
            return result
        finally:
            # Do not wait for timed-out plugins; this avoids blocking the pipeline
            # after we already returned TIMEOUT.
            executor.shutdown(wait=not timed_out, cancel_futures=True)
            if execution_context_set:
                ctx._clear_execution_context()
            ctx.config = base_config

    def execute_stage(
        self,
        stage: Stage,
        ctx: PluginContext,
        profile: Optional[str] = None,
        fail_fast: bool = False,
    ) -> list[PluginResult]:
        """Execute all plugins for a stage.

        Args:
            stage: Pipeline stage to execute
            ctx: Execution context
            profile: Current execution profile
            fail_fast: Stop on first failure

        Returns:
            List of PluginResult for each executed plugin
        """
        results: list[PluginResult] = []
        plugin_ids = self.get_execution_order(stage, profile)
        core_model_version = ctx.model_lock.get("core_model_version") if isinstance(ctx.model_lock, dict) else None
        if isinstance(core_model_version, str) and core_model_version:
            if not self._is_model_version_compatible(core_model_version):
                result = PluginResult.failed(
                    plugin_id="kernel.model_version_guard",
                    api_version=KERNEL_API_VERSION,
                    diagnostics=[
                        PluginDiagnostic(
                            code="E4011",
                            severity="error",
                            stage=stage.value,
                            message=(
                                f"Unsupported core_model_version '{core_model_version}'. "
                                f"Kernel supports: {MODEL_VERSIONS}"
                            ),
                            path="model.lock:core_model_version",
                            plugin_id="kernel",
                        )
                    ],
                )
                results.append(result)
                self._results.append(result)
                return results
        model_version_diags: list[PluginDiagnostic] = []
        for plugin_id in plugin_ids:
            spec = self.specs.get(plugin_id)
            if not isinstance(spec, PluginSpec):
                continue
            declared_model_versions = [item for item in spec.model_versions if isinstance(item, str) and item.strip()]
            if not declared_model_versions:
                continue
            if not isinstance(core_model_version, str) or not core_model_version:
                model_version_diags.append(
                    PluginDiagnostic(
                        code="E4012",
                        severity="error",
                        stage=stage.value,
                        message=(
                            f"Plugin '{plugin_id}' declares model_versions={declared_model_versions}, "
                            "but model.lock core_model_version is unavailable."
                        ),
                        path=f"plugin:{plugin_id}",
                        plugin_id="kernel",
                    )
                )
                continue
            if not self._is_model_version_in_set(core_model_version, declared_model_versions):
                model_version_diags.append(
                    PluginDiagnostic(
                        code="E4011",
                        severity="error",
                        stage=stage.value,
                        message=(
                            f"Plugin '{plugin_id}' does not support core_model_version "
                            f"'{core_model_version}'. Supported by plugin: {declared_model_versions}"
                        ),
                        path=f"plugin:{plugin_id}",
                        plugin_id="kernel",
                    )
                )
        if model_version_diags:
            result = PluginResult.failed(
                plugin_id="kernel.model_version_guard",
                api_version=KERNEL_API_VERSION,
                diagnostics=model_version_diags,
            )
            results.append(result)
            self._results.append(result)
            return results

        available_capabilities: set[str] = set()
        for spec in self.specs.values():
            if (
                spec.profile_restrictions is not None
                and profile is not None
                and profile not in spec.profile_restrictions
            ):
                continue
            for capability in spec.capabilities:
                if isinstance(capability, str) and capability:
                    available_capabilities.add(capability)

        preflight_diags: list[PluginDiagnostic] = []
        for plugin_id in plugin_ids:
            spec = self.specs.get(plugin_id)
            if not isinstance(spec, PluginSpec):
                continue
            missing = sorted(
                capability
                for capability in spec.requires_capabilities
                if isinstance(capability, str) and capability and capability not in available_capabilities
            )
            if missing:
                preflight_diags.append(
                    PluginDiagnostic(
                        code="E4010",
                        severity="error",
                        stage=stage.value,
                        message=(
                            f"Plugin '{plugin_id}' requires missing capabilities: {missing}. "
                            "Provide capability-producing plugins or adjust requires_capabilities."
                        ),
                        path=f"plugin:{plugin_id}",
                        plugin_id="kernel",
                    )
                )
        if preflight_diags:
            result = PluginResult.failed(
                plugin_id="kernel.capability_guard",
                api_version=KERNEL_API_VERSION,
                diagnostics=preflight_diags,
            )
            results.append(result)
            self._results.append(result)
            return results

        for plugin_id in plugin_ids:
            result = self.execute_plugin(plugin_id, ctx, stage)
            results.append(result)

            if fail_fast and result.status in (PluginStatus.FAILED, PluginStatus.TIMEOUT):
                break

        return results

    @staticmethod
    def _normalize_model_version(token: str) -> str | None:
        if not isinstance(token, str):
            return None
        candidate = token.strip()
        if not candidate:
            return None
        match = re.search(r"(\d+)\.(\d+)", candidate)
        if not match:
            return None
        return f"{int(match.group(1))}.{int(match.group(2))}"

    @classmethod
    def _is_model_version_compatible(cls, core_model_version: str) -> bool:
        normalized_core = cls._normalize_model_version(core_model_version)
        if normalized_core is None:
            return False
        supported = {
            normalized
            for normalized in (cls._normalize_model_version(item) for item in MODEL_VERSIONS)
            if normalized is not None
        }
        return normalized_core in supported

    @classmethod
    def _is_model_version_in_set(cls, core_model_version: str, allowed_versions: list[str]) -> bool:
        normalized_core = cls._normalize_model_version(core_model_version)
        if normalized_core is None:
            return False
        normalized_allowed = {
            normalized
            for normalized in (cls._normalize_model_version(item) for item in allowed_versions)
            if normalized is not None
        }
        return normalized_core in normalized_allowed

    def get_load_errors(self) -> list[str]:
        """Return any errors encountered during manifest loading."""
        return self._load_errors.copy()

    def get_all_results(self) -> list[PluginResult]:
        """Return all plugin execution results."""
        return self._results.copy()

    def get_stats(self) -> dict[str, Any]:
        """Return registry statistics."""
        by_kind: dict[str, int] = {}
        for spec in self.specs.values():
            kind = spec.kind.value
            by_kind[kind] = by_kind.get(kind, 0) + 1

        by_status: dict[str, int] = {}
        for result in self._results:
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "loaded": len(self.specs),
            "executed": len(self.instances),
            "failed": len(self._load_errors),
            "by_kind": by_kind,
            "by_status": by_status,
            "manifests": self.manifests,
            "execution_order": [r.plugin_id for r in self._results],
        }

    @staticmethod
    def get_kernel_info() -> dict[str, Any]:
        """Return kernel version and compatibility information."""
        return {
            "version": KERNEL_VERSION,
            "plugin_api_version": KERNEL_API_VERSION,
            "supported_api_versions": SUPPORTED_API_VERSIONS,
            "model_versions": MODEL_VERSIONS,
            "execution_profiles": EXECUTION_PROFILES,
            "default_timeout": DEFAULT_PLUGIN_TIMEOUT,
        }
