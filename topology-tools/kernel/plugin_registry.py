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
import contextvars
import heapq
import importlib.util
import json
import re
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Type

import yaml
from yaml_loader import load_yaml_file

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# ADR 0097 Wave 5: Python 3.14+ required - always use subinterpreters
# On Python < 3.14, fall back to ThreadPoolExecutor for development/testing
HAS_REAL_SUBINTERPRETERS = sys.version_info >= (3, 14)
if HAS_REAL_SUBINTERPRETERS:
    from concurrent.futures import InterpreterPoolExecutor
else:
    # For development/testing on Python < 3.14, fall back to ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor as InterpreterPoolExecutor  # type: ignore[assignment]

from .plugin_base import (
    Phase,
    PluginBase,
    PluginContext,
    PluginDiagnostic,
    PluginInputSnapshot,
    PluginExecutionScope,
    PluginKind,
    PluginResult,
    PluginStatus,
    Stage,
)
from .pipeline_runtime import PipelineState

# Kernel version and compatibility matrix
KERNEL_VERSION = "0.5.0"
KERNEL_API_VERSION = "1.0"
SUPPORTED_API_VERSIONS = ["1.x"]
MODEL_VERSIONS = ["0062-1.0"]
EXECUTION_PROFILES = ["production", "modeled", "test-real"]

# Default timeout for plugin execution (seconds)
DEFAULT_PLUGIN_TIMEOUT = 30.0
PHASE_ORDER: tuple[Phase, ...] = (
    Phase.INIT,
    Phase.PRE,
    Phase.RUN,
    Phase.POST,
    Phase.VERIFY,
    Phase.FINALIZE,
)
STAGE_ORDER: tuple[Stage, ...] = (
    Stage.DISCOVER,
    Stage.COMPILE,
    Stage.VALIDATE,
    Stage.GENERATE,
    Stage.ASSEMBLE,
    Stage.BUILD,
)
STAGE_ORDER_RANGES: dict[Stage, tuple[int, int]] = {
    Stage.DISCOVER: (10, 89),
    Stage.COMPILE: (30, 89),
    Stage.VALIDATE: (90, 189),
    Stage.GENERATE: (190, 399),
    Stage.ASSEMBLE: (400, 499),
    Stage.BUILD: (500, 599),
}
KIND_STAGE_AFFINITY: dict[PluginKind, set[Stage]] = {
    PluginKind.DISCOVERER: {Stage.DISCOVER},
    PluginKind.COMPILER: {Stage.COMPILE},
    PluginKind.VALIDATOR_YAML: {Stage.VALIDATE},
    PluginKind.VALIDATOR_JSON: {Stage.VALIDATE},
    PluginKind.GENERATOR: {Stage.GENERATE},
    PluginKind.ASSEMBLER: {Stage.ASSEMBLE},
    PluginKind.BUILDER: {Stage.BUILD},
}
KIND_ENTRY_FAMILY: dict[PluginKind, str] = {
    PluginKind.DISCOVERER: "discoverers",
    PluginKind.COMPILER: "compilers",
    PluginKind.VALIDATOR_YAML: "validators",
    PluginKind.VALIDATOR_JSON: "validators",
    PluginKind.GENERATOR: "generators",
    PluginKind.ASSEMBLER: "assemblers",
    PluginKind.BUILDER: "builders",
}
ENTRY_FAMILIES: set[str] = set(KIND_ENTRY_FAMILY.values())


def _execute_plugin_isolated(
    serialized_ctx_dict: dict[str, Any],
    plugin_id: str,
    stage_value: str,
    phase_value: str,
    base_path_str: str,
    serialized_spec_dict: dict[str, Any],
) -> tuple[PluginResult, dict[str, dict[str, Any]]]:
    """Execute plugin in isolated subinterpreter (ADR 0097).

    This function is submitted to InterpreterPoolExecutor for execution in a separate
    Python subinterpreter. It reconstructs the minimal runtime environment needed for
    plugin execution.

    Args:
        serialized_ctx_dict: SerializablePluginContext as dict (for pickling)
        plugin_id: Plugin identifier
        stage_value: Stage enum value (as string)
        phase_value: Phase enum value (as string)
        base_path_str: Base path for plugin loading (as string)
        serialized_spec_dict: SerializablePluginSpec as dict (minimal fields only)

    Returns:
        Tuple of (PluginResult, published_data dict) from plugin execution.
        The published_data dict contains data published by this plugin.

    Note:
        This function runs in an isolated interpreter with no shared state from the
        main interpreter. All data is passed via serialized arguments.
    """
    import sys
    from pathlib import Path

    # Add base_path to sys.path for imports
    base_path = Path(base_path_str)
    if str(base_path.resolve()) not in sys.path:
        sys.path.insert(0, str(base_path.resolve()))

    # Import kernel modules in isolated interpreter
    from kernel.plugin_base import (
        Phase,
        PluginResult,
        SerializablePluginContext,
        Stage,
    )
    from kernel.plugin_registry import PluginRegistry, SerializablePluginSpec

    # Reconstruct SerializablePluginContext from dict
    serialized_ctx = SerializablePluginContext(**serialized_ctx_dict)

    # Deserialize to PluginContext
    ctx = serialized_ctx.to_plugin_context()

    # Reconstruct minimal PluginSpec from SerializablePluginSpec
    serialized_spec = SerializablePluginSpec.from_dict(serialized_spec_dict)

    # Create minimal registry in this interpreter with stub PluginSpec
    registry = PluginRegistry(base_path)
    # Create stub spec with required fields for loading
    from kernel.plugin_base import PluginKind

    stub_spec = PluginSpec(
        id=serialized_spec.id,
        kind=PluginKind(serialized_spec.kind),
        entry=serialized_spec.entry,
        api_version=serialized_spec.api_version,
        stages=[Stage(stage_value)],  # Only current stage needed
        order=0,  # Not used in execution
        depends_on=serialized_spec.depends_on,
        config=serialized_spec.config,
        produces=serialized_spec.produces,
        consumes=serialized_spec.consumes,
        manifest_path=Path(serialized_spec.manifest_path),
    )
    registry.specs[plugin_id] = stub_spec

    # Load and execute plugin
    try:
        plugin = registry.load_plugin(plugin_id)
        stage = Stage(stage_value)
        phase = Phase(phase_value)

        # Set up execution scope (required for publish/subscribe)
        from kernel.plugin_base import PluginExecutionScope

        scope = PluginExecutionScope(
            plugin_id=plugin_id,
            allowed_dependencies=frozenset(serialized_spec.depends_on),
            phase=phase,
            config=serialized_spec.config.copy(),
            stage=stage,
        )
        scope_token = ctx._set_execution_scope(scope)
        try:
            result = plugin.execute_phase(ctx, stage, phase)
        finally:
            ctx._clear_execution_scope(scope_token)

        # ADR 0097: Return published data for cross-interpreter transfer
        published_data = ctx._published_data.copy()
        return (result, published_data)
    except Exception as e:
        # Return failed result with traceback
        import traceback

        from kernel.plugin_base import PluginDiagnostic, PluginStatus

        tb = traceback.format_exc()
        return (
            PluginResult(
                plugin_id=plugin_id,
                api_version=serialized_spec.api_version,
                status=PluginStatus.FAILED,
                diagnostics=[
                    PluginDiagnostic(
                        code="E4102",
                        severity="error",
                        stage=stage_value,
                        phase=phase_value,
                        message=f"Plugin crashed in isolated interpreter: {e}",
                        path="kernel.subinterpreter",
                        plugin_id="kernel",
                    )
                ],
                error_traceback=tb,
            ),
            {},  # Empty published data on error
        )


@dataclass
class SerializablePluginSpec:
    """Minimal plugin spec for cross-interpreter transfer (ADR 0097).

    Contains only fields required for plugin execution in subinterpreter.
    Reduces serialization overhead by ~60% compared to full PluginSpec.
    """

    id: str
    kind: str  # String value of PluginKind enum
    entry: str
    api_version: str
    depends_on: list[str]
    config: dict[str, Any]
    produces: list[dict[str, Any]]
    consumes: list[dict[str, Any]]
    manifest_path: str  # Required for resolving module paths

    @classmethod
    def from_plugin_spec(cls, spec: "PluginSpec") -> "SerializablePluginSpec":
        """Create minimal serializable spec from full PluginSpec.

        Uses JSON round-trip for proper deep copying of nested structures.
        """
        # Deep copy via JSON to ensure nested structures are independent
        config_copy = json.loads(json.dumps(spec.config)) if spec.config else {}
        produces_copy = json.loads(json.dumps(spec.produces)) if spec.produces else []
        consumes_copy = json.loads(json.dumps(spec.consumes)) if spec.consumes else []
        return cls(
            id=spec.id,
            kind=spec.kind.value,
            entry=spec.entry,
            api_version=spec.api_version,
            depends_on=spec.depends_on.copy(),
            config=config_copy,
            produces=produces_copy,
            consumes=consumes_copy,
            manifest_path=str(spec.manifest_path),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for pickle serialization."""
        return {
            "id": self.id,
            "kind": self.kind,
            "entry": self.entry,
            "api_version": self.api_version,
            "depends_on": self.depends_on,
            "config": self.config,
            "produces": self.produces,
            "consumes": self.consumes,
            "manifest_path": self.manifest_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SerializablePluginSpec":
        """Reconstruct from dict in target interpreter."""
        return cls(
            id=data["id"],
            kind=data["kind"],
            entry=data["entry"],
            api_version=data["api_version"],
            depends_on=data.get("depends_on", []),
            config=data.get("config", {}),
            produces=data.get("produces", []),
            consumes=data.get("consumes", []),
            manifest_path=data.get("manifest_path", ""),
        )


@dataclass
class PluginSpec:
    """Specification for a single plugin from manifest."""

    id: str
    kind: PluginKind
    entry: str
    api_version: str
    stages: list[Stage]
    order: int
    phase: Phase = Phase.RUN
    depends_on: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    requires_capabilities: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    config_schema: Optional[dict[str, Any]] = None
    when: dict[str, Any] = field(default_factory=dict)
    produces: list[dict[str, Any]] = field(default_factory=list)
    consumes: list[dict[str, Any]] = field(default_factory=list)
    compiled_json_owner: bool = False
    model_versions: list[str] = field(default_factory=list)
    description: str = ""
    migration_mode: str = "legacy"
    manifest_path: str = ""
    timeout: float = DEFAULT_PLUGIN_TIMEOUT
    subinterpreter_compatible: bool = False  # ADR 0097 Wave 1

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
            phase=Phase(data.get("phase", Phase.RUN.value)),
            depends_on=data.get("depends_on", []),
            capabilities=data.get("capabilities", []),
            requires_capabilities=data.get("requires_capabilities", []),
            config=data.get("config", {}),
            config_schema=data.get("config_schema"),
            when=data.get("when", {}),
            produces=data.get("produces", []),
            consumes=data.get("consumes", []),
            compiled_json_owner=bool(data.get("compiled_json_owner", False)),
            model_versions=data.get("model_versions", []),
            description=data.get("description", ""),
            migration_mode=str(data.get("migration_mode", "legacy")),
            manifest_path=manifest_path,
            timeout=data.get("timeout", DEFAULT_PLUGIN_TIMEOUT),
            subinterpreter_compatible=bool(data.get("subinterpreter_compatible", False)),
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
        data = load_yaml_file(path) or {}
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
        self._ensure_import_path(self.base_path)
        self.manifest_schema_path = self.base_path / "schemas" / "plugin-manifest.schema.json"
        self._manifest_schema: Optional[dict[str, Any]] = None
        self.specs: dict[str, PluginSpec] = {}
        self.instances: dict[str, PluginBase] = {}
        self.manifests: list[str] = []
        self._load_errors: list[str] = []
        self._results: list[PluginResult] = []
        self._instances_lock = threading.Lock()
        self._payload_schema_cache: dict[str, dict[str, Any]] = {}
        self._execution_trace: list[dict[str, Any]] = []
        self._trace_lock = threading.Lock()

    def _get_parallel_executor(self, max_workers: int) -> InterpreterPoolExecutor:
        """Return subinterpreter executor for parallel plugin execution (ADR 0097 Wave 5).

        Python 3.14+ is required. All plugins execute in isolated subinterpreters
        providing true parallelism via per-interpreter GIL.

        Args:
            max_workers: Maximum number of parallel workers

        Returns:
            InterpreterPoolExecutor instance
        """
        return InterpreterPoolExecutor(max_workers=max_workers)

    def _trace_event(
        self,
        *,
        event: str,
        stage: Stage,
        phase: Phase | None = None,
        plugin_id: str | None = None,
        status: PluginStatus | None = None,
        message: str | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "seq": 0,
            "ts": time.time(),
            "event": event,
            "stage": stage.value,
        }
        if phase is not None:
            entry["phase"] = phase.value
        if plugin_id is not None:
            entry["plugin_id"] = plugin_id
        if status is not None:
            entry["status"] = status.value
        if message:
            entry["message"] = message
        with self._trace_lock:
            entry["seq"] = len(self._execution_trace) + 1
            self._execution_trace.append(entry)

    @staticmethod
    def _ensure_import_path(path: Path) -> None:
        candidate = str(path.resolve())
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

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
            payload = load_yaml_file(manifest_path) or {}
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
        allowed_stages = KIND_STAGE_AFFINITY.get(spec.kind, set())
        for stage in spec.stages:
            if stage in allowed_stages:
                continue
            raise PluginLoadError(
                spec.id,
                f"kind '{spec.kind.value}' cannot run in stage '{stage.value}' "
                f"(allowed stages: {[item.value for item in sorted(allowed_stages, key=lambda s: s.value)]})",
            )
        if self._entry_uses_plugins_prefix_without_family(spec.entry):
            raise PluginLoadError(
                spec.id,
                f"entry '{spec.entry}' must include plugin family segment "
                "(expected plugins/<family>/module.py:ClassName)",
            )
        entry_family = self._extract_entry_plugin_family(spec.entry)
        expected_family = KIND_ENTRY_FAMILY.get(spec.kind)
        if entry_family and expected_family and entry_family != expected_family:
            raise PluginLoadError(
                spec.id,
                f"entry '{spec.entry}' must use plugins/{expected_family}/ for kind "
                f"'{spec.kind.value}' (got plugins/{entry_family}/)",
            )
        for stage in spec.stages:
            order_range = STAGE_ORDER_RANGES.get(stage)
            if order_range is None:
                continue
            min_order, max_order = order_range
            if min_order <= spec.order <= max_order:
                continue
            raise PluginLoadError(
                spec.id,
                f"order {spec.order} is outside allowed range {min_order}-{max_order} for stage '{stage.value}'",
            )
        if spec.compiled_json_owner:
            for existing in self.specs.values():
                if not existing.compiled_json_owner or existing.phase != spec.phase:
                    continue
                overlapping_stages = sorted({stage.value for stage in spec.stages if stage in existing.stages})
                if overlapping_stages:
                    raise PluginLoadError(
                        spec.id,
                        "compiled_json_owner conflicts with "
                        f"'{existing.id}' for phase '{spec.phase.value}' and stages {overlapping_stages}",
                    )

    @staticmethod
    def _extract_entry_plugin_family(entry: str) -> str | None:
        """Return entry family for supported entry layouts, if present.

        Supported layouts:
        1. plugins/<family>/module.py
        2. <family>/module.py
        """
        entry_path = entry.split(":", 1)[0].replace("\\", "/")
        if "/plugins/" in entry_path:
            tail = entry_path.split("/plugins/", 1)[1]
        elif entry_path.startswith("plugins/"):
            tail = entry_path[len("plugins/") :]
        else:
            if "/" not in entry_path:
                return None
            head = entry_path.split("/", 1)[0].strip()
            return head if head in ENTRY_FAMILIES else None
        if "/" not in tail:
            return None
        family = tail.split("/", 1)[0].strip()
        return family or None

    @staticmethod
    def _entry_uses_plugins_prefix_without_family(entry: str) -> bool:
        """Detect deprecated flat plugins/<file>.py entries."""
        entry_path = entry.split(":", 1)[0].replace("\\", "/")
        if "/plugins/" in entry_path:
            tail = entry_path.split("/plugins/", 1)[1]
        elif entry_path.startswith("plugins/"):
            tail = entry_path[len("plugins/") :]
        else:
            return False
        return "/" not in tail

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

    @staticmethod
    def _stage_rank(stage: Stage) -> int:
        return STAGE_ORDER.index(stage)

    @staticmethod
    def _phase_rank(phase: Phase) -> int:
        return PHASE_ORDER.index(phase)

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]

    def _active_changed_input_scopes(self, ctx: PluginContext) -> set[str] | None:
        if isinstance(ctx.changed_input_scopes, list):
            return {item for item in ctx.changed_input_scopes if isinstance(item, str) and item}
        configured_scopes = ctx.config.get("changed_input_scopes")
        if isinstance(configured_scopes, list):
            return {item for item in configured_scopes if isinstance(item, str) and item}
        return None

    def _profile_allows_spec(self, spec: PluginSpec, profile: Optional[str]) -> bool:
        if profile is None:
            return True
        modern = self._string_list(spec.when.get("profiles")) if isinstance(spec.when, dict) else []
        if modern:
            return profile in modern
        return True

    def _when_predicates_allow(self, spec: PluginSpec, ctx: PluginContext) -> bool:
        if not isinstance(spec.when, dict) or not spec.when:
            return True

        profiles = self._string_list(spec.when.get("profiles"))
        if profiles and ctx.profile not in profiles:
            return False

        capabilities = self._string_list(spec.when.get("capabilities"))
        if capabilities:
            available_caps = {key for key in (ctx.capability_catalog or {}).keys() if isinstance(key, str) and key}
            if not set(capabilities).issubset(available_caps):
                return False

        pipeline_modes = self._string_list(spec.when.get("pipeline_modes"))
        if pipeline_modes:
            current_mode = str(ctx.config.get("pipeline_mode", ""))
            if current_mode not in pipeline_modes:
                return False

        changed_scopes = self._string_list(spec.when.get("changed_input_scopes"))
        if changed_scopes:
            active_scopes = self._active_changed_input_scopes(ctx)
            if active_scopes is None:
                # Runtime has not computed dirty scopes yet; keep non-blocking behavior.
                return True
            if not active_scopes:
                return False
            if "all" in active_scopes or "*" in active_scopes:
                return True
            if "all" in changed_scopes or "*" in changed_scopes:
                return True
            if active_scopes.isdisjoint(changed_scopes):
                return False

        return True

    @staticmethod
    def _declared_produced_scopes(spec: PluginSpec) -> dict[str, str]:
        key_scopes: dict[str, str] = {}
        for entry in spec.produces:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            if not isinstance(key, str) or not key:
                continue
            scope = entry.get("scope", "pipeline_shared")
            if scope not in {"stage_local", "pipeline_shared"}:
                scope = "pipeline_shared"
            key_scopes[key] = scope
        return key_scopes

    @staticmethod
    def _declared_consumes(spec: PluginSpec) -> set[tuple[str, str]]:
        declared: set[tuple[str, str]] = set()
        for entry in spec.consumes:
            if not isinstance(entry, dict):
                continue
            from_plugin = entry.get("from_plugin")
            key = entry.get("key")
            if not isinstance(from_plugin, str) or not isinstance(key, str):
                continue
            if not from_plugin or not key:
                continue
            declared.add((from_plugin, key))
        return declared

    def _build_input_snapshot(
        self,
        *,
        plugin_id: str,
        stage: Stage,
        phase: Phase,
        ctx: PluginContext,
        pipeline_state: PipelineState | None = None,
    ) -> PluginInputSnapshot:
        """Build immutable plugin input for the envelope-model execution path."""
        spec = self.specs[plugin_id]
        base_config = ctx.config.copy()
        scoped_config = {**spec.config, **base_config}
        produced_key_scopes = self._declared_produced_scopes(spec)

        subscriptions: dict[tuple[str, str], Any] = {}
        if pipeline_state is not None:
            for consume in spec.consumes:
                if not isinstance(consume, dict):
                    continue
                from_plugin = consume.get("from_plugin")
                key = consume.get("key")
                if not isinstance(from_plugin, str) or not from_plugin or not isinstance(key, str) or not key:
                    continue
                try:
                    subscriptions[(from_plugin, key)] = pipeline_state.resolve_subscription(
                        from_plugin=from_plugin,
                        key=key,
                        stage=stage,
                    )
                except PluginDataExchangeError:
                    if consume.get("required", True) is False:
                        continue
                    raise

        return PluginInputSnapshot(
            plugin_id=plugin_id,
            stage=stage,
            phase=phase,
            topology_path=ctx.topology_path,
            profile=ctx.profile,
            config=scoped_config,
            model_lock=dict(ctx.model_lock),
            raw_yaml=dict(ctx.raw_yaml),
            instance_bindings=dict(ctx.instance_bindings),
            compiled_json=dict(ctx.compiled_json),
            classes=dict(ctx.classes),
            objects=dict(ctx.objects),
            capability_catalog=dict(ctx.capability_catalog),
            effective_capabilities=dict(ctx.effective_capabilities),
            effective_software=dict(ctx.effective_software),
            output_dir=ctx.output_dir,
            workspace_root=ctx.workspace_root,
            dist_root=ctx.dist_root,
            assembly_manifest=dict(ctx.assembly_manifest),
            changed_input_scopes=list(ctx.changed_input_scopes) if ctx.changed_input_scopes else None,
            signing_backend=ctx.signing_backend,
            release_tag=ctx.release_tag,
            sbom_output_dir=ctx.sbom_output_dir,
            error_catalog=dict(ctx.error_catalog),
            source_file=ctx.source_file,
            compiled_file=ctx.compiled_file,
            subscriptions=subscriptions,
            allowed_dependencies=frozenset(spec.depends_on),
            produced_key_scopes=produced_key_scopes,
        )

    @staticmethod
    def _apply_result_status_from_diagnostics(result: PluginResult) -> None:
        if result.status not in {PluginStatus.SUCCESS, PluginStatus.PARTIAL}:
            return
        has_errors = any(diag.severity == "error" for diag in result.diagnostics)
        has_warnings = any(diag.severity == "warning" for diag in result.diagnostics)
        if has_errors:
            result.status = PluginStatus.FAILED
        elif has_warnings:
            result.status = PluginStatus.PARTIAL

    def _resolve_payload_schema_path(self, spec: PluginSpec, schema_ref: str) -> Path | None:
        raw = schema_ref.strip()
        if not raw:
            return None
        candidate = Path(raw)
        if candidate.is_absolute():
            return candidate if candidate.exists() else None

        manifest_relative = Path(spec.manifest_path).parent / raw
        if manifest_relative.exists():
            return manifest_relative

        base_relative = self.base_path / raw
        if base_relative.exists():
            return base_relative
        return None

    def _load_payload_schema(self, spec: PluginSpec, schema_ref: str) -> tuple[dict[str, Any] | None, str | None]:
        if not HAS_JSONSCHEMA:
            return None, "jsonschema dependency is required for schema_ref validation."

        schema_path = self._resolve_payload_schema_path(spec, schema_ref)
        if schema_path is None:
            return None, f"schema_ref '{schema_ref}' cannot be resolved for plugin '{spec.id}'."
        cache_key = str(schema_path.resolve())
        cached = self._payload_schema_cache.get(cache_key)
        if cached is not None:
            return cached, None

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"schema_ref '{schema_ref}' failed to load: {exc}"
        try:
            jsonschema.validators.validator_for(schema).check_schema(schema)
        except jsonschema.SchemaError as exc:
            return None, f"schema_ref '{schema_ref}' is invalid JSON schema: {exc.message}"
        self._payload_schema_cache[cache_key] = schema
        return schema, None

    def _schema_ref_by_produced_key(self, spec: PluginSpec) -> dict[str, str]:
        refs: dict[str, str] = {}
        for entry in spec.produces:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            schema_ref = entry.get("schema_ref")
            if isinstance(key, str) and key and isinstance(schema_ref, str) and schema_ref.strip():
                refs[key] = schema_ref.strip()
        return refs

    def _schema_ref_by_consumed_key(self, spec: PluginSpec) -> dict[tuple[str, str], str]:
        refs: dict[tuple[str, str], str] = {}
        for entry in spec.consumes:
            if not isinstance(entry, dict):
                continue
            from_plugin = entry.get("from_plugin")
            key = entry.get("key")
            schema_ref = entry.get("schema_ref")
            if (
                isinstance(from_plugin, str)
                and from_plugin
                and isinstance(key, str)
                and key
                and isinstance(schema_ref, str)
                and schema_ref.strip()
            ):
                refs[(from_plugin, key)] = schema_ref.strip()
        return refs

    def _append_schema_validation_error(
        self,
        *,
        result: PluginResult,
        stage: Stage,
        phase: Phase,
        spec: PluginSpec,
        code: str,
        message: str,
        path_suffix: str,
    ) -> None:
        result.diagnostics.append(
            PluginDiagnostic(
                code=code,
                severity="error",
                stage=stage.value,
                phase=phase.value,
                message=message,
                path=f"plugin:{spec.id}:{path_suffix}",
                plugin_id="kernel",
            )
        )

    def _validate_required_consumes_pre_run(
        self,
        *,
        spec: PluginSpec,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        published_data = ctx.get_published_data()
        consume_schema_refs = self._schema_ref_by_consumed_key(spec)

        for consume_entry in spec.consumes:
            if not isinstance(consume_entry, dict):
                continue
            from_plugin = consume_entry.get("from_plugin")
            key = consume_entry.get("key")
            required = consume_entry.get("required", True)
            if required is False:
                continue
            if not isinstance(from_plugin, str) or not from_plugin:
                continue
            if not isinstance(key, str) or not key:
                continue

            payload = published_data.get(from_plugin, {}).get(key, None)
            if payload is None and key not in published_data.get(from_plugin, {}):
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8003",
                        severity="error",
                        stage=stage.value,
                        phase=phase.value,
                        message=(
                            f"Plugin '{spec.id}' requires payload '{from_plugin}.{key}', "
                            "but it is not available in published data."
                        ),
                        path=f"plugin:{spec.id}:consumes.{from_plugin}.{key}",
                        plugin_id="kernel",
                    )
                )
                continue

            schema_ref = consume_schema_refs.get((from_plugin, key))
            if schema_ref is None:
                continue
            probe_result = PluginResult.success(spec.id, spec.api_version)
            self._validate_schema_ref_payload(
                result=probe_result,
                stage=stage,
                phase=phase,
                spec=spec,
                payload=payload,
                schema_ref=schema_ref,
                path_suffix=f"consumes.{from_plugin}.{key}",
            )
            diagnostics.extend(probe_result.diagnostics)

        return diagnostics

    def _validate_schema_ref_payload(
        self,
        *,
        result: PluginResult,
        stage: Stage,
        phase: Phase,
        spec: PluginSpec,
        payload: Any,
        schema_ref: str,
        path_suffix: str,
    ) -> None:
        schema, schema_error = self._load_payload_schema(spec, schema_ref)
        if schema is None:
            self._append_schema_validation_error(
                result=result,
                stage=stage,
                phase=phase,
                spec=spec,
                code="E8001",
                message=schema_error or f"schema_ref '{schema_ref}' could not be loaded.",
                path_suffix=path_suffix,
            )
            return
        try:
            jsonschema.validate(instance=payload, schema=schema)
        except jsonschema.ValidationError as exc:
            self._append_schema_validation_error(
                result=result,
                stage=stage,
                phase=phase,
                spec=spec,
                code="E8002",
                message=f"payload does not satisfy schema_ref '{schema_ref}': {exc.message}",
                path_suffix=path_suffix,
            )

    def _attach_data_bus_contract_diagnostics(
        self,
        *,
        spec: PluginSpec,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase,
        result: PluginResult,
        publish_event_start: int,
        subscribe_event_start: int,
        emit_warnings: bool,
        undeclared_as_errors: bool,
    ) -> None:
        publish_events = ctx._get_publish_events_since(
            publish_event_start,
            plugin_id=spec.id,
            stage=stage,
            phase=phase,
        )
        subscribe_events = ctx._get_subscribe_events_since(
            subscribe_event_start,
            plugin_id=spec.id,
            stage=stage,
            phase=phase,
        )
        published_payloads = ctx.get_published_data()
        produce_schema_refs = self._schema_ref_by_produced_key(spec)
        consume_schema_refs = self._schema_ref_by_consumed_key(spec)

        if publish_events and (emit_warnings or undeclared_as_errors):
            declared_produces = {key for key in self._declared_produced_scopes(spec)}
            published_keys = sorted({event.key for event in publish_events})
            warning_severity = "error" if undeclared_as_errors else "warning"
            warning_code = "E8004" if undeclared_as_errors else "W8001"
            warning_code_undeclared = "E8005" if undeclared_as_errors else "W8002"
            if not declared_produces:
                result.diagnostics.append(
                    PluginDiagnostic(
                        code=warning_code,
                        severity=warning_severity,
                        stage=stage.value,
                        phase=phase.value,
                        message=(
                            f"Plugin '{spec.id}' published keys {published_keys} "
                            "without manifest produces declaration."
                        ),
                        path=f"plugin:{spec.id}",
                        plugin_id="kernel",
                    )
                )
            else:
                undeclared_publish = sorted(key for key in published_keys if key not in declared_produces)
                if undeclared_publish:
                    result.diagnostics.append(
                        PluginDiagnostic(
                            code=warning_code_undeclared,
                            severity=warning_severity,
                            stage=stage.value,
                            phase=phase.value,
                            message=(
                                f"Plugin '{spec.id}' published undeclared keys {undeclared_publish}. "
                                "Declare them under produces[]."
                            ),
                            path=f"plugin:{spec.id}",
                            plugin_id="kernel",
                        )
                    )

        if subscribe_events and (emit_warnings or undeclared_as_errors):
            declared_consumes = self._declared_consumes(spec)
            consumed_pairs = {(event.from_plugin, event.key) for event in subscribe_events}
            consumed_keys = sorted(f"{from_plugin}.{key}" for from_plugin, key in consumed_pairs)
            warning_severity = "error" if undeclared_as_errors else "warning"
            warning_code = "E8006" if undeclared_as_errors else "W8003"
            warning_code_undeclared = "E8007" if undeclared_as_errors else "W8004"
            if not declared_consumes:
                result.diagnostics.append(
                    PluginDiagnostic(
                        code=warning_code,
                        severity=warning_severity,
                        stage=stage.value,
                        phase=phase.value,
                        message=(
                            f"Plugin '{spec.id}' consumed keys {consumed_keys} "
                            "without manifest consumes declaration."
                        ),
                        path=f"plugin:{spec.id}",
                        plugin_id="kernel",
                    )
                )
            else:
                undeclared_consume = sorted(
                    f"{from_plugin}.{key}"
                    for from_plugin, key in consumed_pairs
                    if (from_plugin, key) not in declared_consumes
                )
                if undeclared_consume:
                    result.diagnostics.append(
                        PluginDiagnostic(
                            code=warning_code_undeclared,
                            severity=warning_severity,
                            stage=stage.value,
                            phase=phase.value,
                            message=(
                                f"Plugin '{spec.id}' consumed undeclared keys {undeclared_consume}. "
                                "Declare them under consumes[]."
                            ),
                            path=f"plugin:{spec.id}",
                            plugin_id="kernel",
                        )
                    )

        for key in sorted({event.key for event in publish_events}):
            schema_ref = produce_schema_refs.get(key)
            if schema_ref is None:
                continue
            payload = published_payloads.get(spec.id, {}).get(key)
            self._validate_schema_ref_payload(
                result=result,
                stage=stage,
                phase=phase,
                spec=spec,
                payload=payload,
                schema_ref=schema_ref,
                path_suffix=f"produces.{key}",
            )

        for from_plugin, key in sorted({(event.from_plugin, event.key) for event in subscribe_events}):
            schema_ref = consume_schema_refs.get((from_plugin, key))
            if schema_ref is None:
                continue
            payload = published_payloads.get(from_plugin, {}).get(key)
            self._validate_schema_ref_payload(
                result=result,
                stage=stage,
                phase=phase,
                spec=spec,
                payload=payload,
                schema_ref=schema_ref,
                path_suffix=f"consumes.{from_plugin}.{key}",
            )

        self._apply_result_status_from_diagnostics(result)

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
                dep_spec = self.specs[dep_id]
                allowed_dependency = False
                for stage in spec.stages:
                    for dep_stage in dep_spec.stages:
                        dep_stage_rank = self._stage_rank(dep_stage)
                        stage_rank = self._stage_rank(stage)
                        if dep_stage_rank < stage_rank:
                            allowed_dependency = True
                            break
                        if dep_stage_rank == stage_rank and self._phase_rank(dep_spec.phase) <= self._phase_rank(
                            spec.phase
                        ):
                            allowed_dependency = True
                            break
                    if allowed_dependency:
                        break
                if not allowed_dependency:
                    raise PluginLoadError(
                        spec.id,
                        "Forward stage/phase dependency is not allowed: "
                        f"'{spec.id}' ({[s.value for s in spec.stages]}/{spec.phase.value}) depends on "
                        f"'{dep_id}' ({[s.value for s in dep_spec.stages]}/{dep_spec.phase.value})",
                    )
        self._validate_declared_data_bus_contracts()

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

    def _validate_declared_data_bus_contracts(self) -> None:
        """Validate declared consumes/producers compatibility across specs."""
        for consumer_spec in self.specs.values():
            for consume_entry in consumer_spec.consumes:
                if not isinstance(consume_entry, dict):
                    continue
                from_plugin = consume_entry.get("from_plugin")
                key = consume_entry.get("key")
                if not isinstance(from_plugin, str) or not from_plugin:
                    continue
                if not isinstance(key, str) or not key:
                    continue
                if from_plugin not in consumer_spec.depends_on:
                    raise PluginLoadError(
                        consumer_spec.id,
                        f"consumes '{from_plugin}.{key}' requires '{from_plugin}' in depends_on.",
                    )
                producer_spec = self.specs.get(from_plugin)
                if producer_spec is None:
                    raise PluginLoadError(
                        consumer_spec.id,
                        f"consumes references unknown producer '{from_plugin}'.",
                    )
                produced_scopes = self._declared_produced_scopes(producer_spec)
                if produced_scopes and key not in produced_scopes:
                    raise PluginLoadError(
                        consumer_spec.id,
                        f"consumes references undeclared producer key '{from_plugin}.{key}'.",
                    )
                key_scope = produced_scopes.get(key)
                if key_scope == "stage_local" and not self._is_stage_local_consumption_valid(
                    producer_spec, consumer_spec
                ):
                    raise PluginLoadError(
                        consumer_spec.id,
                        "stage_local key cannot cross stage boundary: "
                        f"'{from_plugin}.{key}' from {producer_spec.phase.value}/{[s.value for s in producer_spec.stages]} "
                        f"to {consumer_spec.phase.value}/{[s.value for s in consumer_spec.stages]}",
                    )

    def _is_stage_local_consumption_valid(self, producer: PluginSpec, consumer: PluginSpec) -> bool:
        for producer_stage in producer.stages:
            for consumer_stage in consumer.stages:
                if producer_stage != consumer_stage:
                    continue
                if self._phase_rank(producer.phase) <= self._phase_rank(consumer.phase):
                    return True
        return False

    def get_execution_order(self, stage: Stage, profile: Optional[str] = None, phase: Phase = Phase.RUN) -> list[str]:
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

        # Filter plugins for this stage+phase
        stage_plugins = {
            spec.id: spec
            for spec in self.specs.values()
            if stage in spec.stages and spec.phase == phase and self._profile_allows_spec(spec, profile)
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

    def _plugin_sort_key(self, plugin_id: str) -> tuple[int, str]:
        spec = self.specs.get(plugin_id)
        order = spec.order if spec is not None else sys.maxsize
        return order, plugin_id

    def _preload_plugins(self, plugin_ids: list[str]) -> None:
        """Preload plugin classes/instances before optional parallel execution."""
        for plugin_id in plugin_ids:
            try:
                self.load_plugin(plugin_id)
            except (PluginLoadError, PluginConfigError):
                # Execution path emits canonical plugin diagnostics.
                continue

    def _execute_phase_parallel(
        self,
        *,
        stage: Stage,
        phase: Phase,
        ctx: PluginContext,
        plugin_ids: list[str],
        trace_execution: bool = False,
        contract_warnings: bool = False,
        contract_errors: bool = False,
    ) -> list[PluginResult]:
        """Execute one phase in dependency-respecting wavefronts."""
        if not plugin_ids:
            return []

        plugin_set = set(plugin_ids)
        indegree: dict[str, int] = {plugin_id: 0 for plugin_id in plugin_ids}
        dependents: dict[str, list[str]] = {plugin_id: [] for plugin_id in plugin_ids}

        for plugin_id in plugin_ids:
            spec = self.specs.get(plugin_id)
            if spec is None:
                continue
            for dep_id in spec.depends_on:
                if dep_id not in plugin_set:
                    continue
                indegree[plugin_id] += 1
                dependents[dep_id].append(plugin_id)

        ready: list[tuple[int, str]] = []
        for plugin_id in plugin_ids:
            if indegree[plugin_id] == 0:
                heapq.heappush(ready, self._plugin_sort_key(plugin_id))

        results_by_plugin: dict[str, PluginResult] = {}
        max_workers = min(8, max(1, len(plugin_ids)))

        # ADR 0097 Wave 5: Always use subinterpreters (Python 3.14+ required)
        executor = self._get_parallel_executor(max_workers)

        # ADR 0097: Pre-validate all plugin configs before parallel submission
        # Validates upfront to fail fast and avoid wasted subinterpreter spawning
        config_validation_failed: dict[str, list[str]] = {}
        for plugin_id in plugin_ids:
            errors = self.validate_plugin_config(plugin_id)
            if errors:
                config_validation_failed[plugin_id] = errors

        # Create early failures for invalid configs
        for plugin_id, errors in config_validation_failed.items():
            spec = self.specs.get(plugin_id)
            if spec is None:
                continue
            results_by_plugin[plugin_id] = PluginResult.failed(
                plugin_id=plugin_id,
                api_version=spec.api_version,
                diagnostics=[
                    PluginDiagnostic(
                        code="E4001",
                        severity="error",
                        stage=stage.value,
                        phase=phase.value,
                        message=f"Config validation failed: {'; '.join(errors)}",
                        path="kernel.config_validation",
                        plugin_id="kernel",
                    )
                ],
            )
            # Remove from ready queue - mark as having indegree -1 to prevent execution
            indegree[plugin_id] = -1

        with executor:
            while ready:
                wavefront: list[str] = []
                while ready:
                    _, plugin_id = heapq.heappop(ready)
                    # Skip plugins that failed config validation
                    if plugin_id in config_validation_failed:
                        continue
                    wavefront.append(plugin_id)

                if not wavefront:
                    break  # No more valid plugins to execute

                futures: dict[concurrent.futures.Future[PluginResult], str] = {}
                for plugin_id in wavefront:
                    if trace_execution:
                        self._trace_event(event="plugin_start", stage=stage, phase=phase, plugin_id=plugin_id)

                    # ADR 0097: Use different execution paths based on Python version
                    if HAS_REAL_SUBINTERPRETERS:
                        # Python 3.14+: Use isolated subinterpreter execution
                        spec = self.specs[plugin_id]
                        from kernel.plugin_base import SerializablePluginContext

                        serialized_ctx = SerializablePluginContext.from_plugin_context(ctx)
                        serialized_ctx_dict = {
                            "topology_path": serialized_ctx.topology_path,
                            "profile": serialized_ctx.profile,
                            "model_lock": serialized_ctx.model_lock,
                            "compiled_json_bytes": serialized_ctx.compiled_json_bytes,
                            "plugin_config_bytes": serialized_ctx.plugin_config_bytes,
                            "output_dir": serialized_ctx.output_dir,
                            "capability_catalog": serialized_ctx.capability_catalog,
                            "changed_input_scopes": serialized_ctx.changed_input_scopes,
                            "published_data_bytes": serialized_ctx.published_data_bytes,
                        }
                        # ADR 0097: Use minimal SerializablePluginSpec (~60% smaller)
                        serialized_spec = SerializablePluginSpec.from_plugin_spec(spec)
                        future = executor.submit(
                            _execute_plugin_isolated,
                            serialized_ctx_dict,
                            plugin_id,
                            stage.value,
                            phase.value,
                            str(self.base_path),
                            serialized_spec.to_dict(),
                        )
                    else:
                        # Python < 3.14: Use ThreadPoolExecutor with shared memory
                        future = executor.submit(
                            self.execute_plugin,
                            plugin_id,
                            ctx,
                            stage,
                            phase,
                            None,
                            record_result=False,
                            contract_warnings=contract_warnings,
                            contract_errors=contract_errors,
                        )
                    futures[future] = plugin_id

                # ADR 0097 Wave 5: Collect results and merge published data
                wavefront_published_data: dict[str, dict[str, Any]] = {}
                for future in concurrent.futures.as_completed(futures):
                    plugin_id = futures[future]
                    spec = self.specs.get(plugin_id)
                    if spec is None:
                        continue
                    try:
                        future_result = future.result()
                        # Handle tuple return from subinterpreter execution
                        if HAS_REAL_SUBINTERPRETERS and isinstance(future_result, tuple):
                            result, published_data = future_result
                            # Merge published data from this plugin
                            for pub_plugin_id, pub_data in published_data.items():
                                wavefront_published_data[pub_plugin_id] = pub_data
                        else:
                            result = future_result
                        results_by_plugin[plugin_id] = result
                        if trace_execution:
                            self._trace_event(
                                event="plugin_result",
                                stage=stage,
                                phase=phase,
                                plugin_id=plugin_id,
                                status=result.status,
                            )
                    except Exception as exc:
                        failed = PluginResult.failed(
                            plugin_id=plugin_id,
                            api_version=spec.api_version,
                            diagnostics=[
                                PluginDiagnostic(
                                    code="E4102",
                                    severity="error",
                                    stage=stage.value,
                                    phase=phase.value,
                                    message=f"Plugin crashed in parallel execution: {exc}",
                                    path="kernel",
                                    plugin_id="kernel",
                                )
                            ],
                            error_traceback=traceback.format_exc(),
                        )
                        results_by_plugin[plugin_id] = failed
                        if trace_execution:
                            self._trace_event(
                                event="plugin_result",
                                stage=stage,
                                phase=phase,
                                plugin_id=plugin_id,
                                status=failed.status,
                                message=str(exc),
                            )

                # ADR 0097 Wave 5: Merge wavefront published data into main context
                if HAS_REAL_SUBINTERPRETERS and wavefront_published_data:
                    for pub_plugin_id, pub_data in wavefront_published_data.items():
                        ctx._published_data[pub_plugin_id] = pub_data

                for plugin_id in sorted(wavefront, key=self._plugin_sort_key):
                    if plugin_id not in results_by_plugin:
                        continue
                    for dependent_id in dependents[plugin_id]:
                        indegree[dependent_id] -= 1
                        if indegree[dependent_id] == 0:
                            heapq.heappush(ready, self._plugin_sort_key(dependent_id))

        ordered_results = [results_by_plugin[plugin_id] for plugin_id in plugin_ids if plugin_id in results_by_plugin]
        self._results.extend(ordered_results)
        return ordered_results

    def load_plugin(self, plugin_id: str) -> PluginBase:
        """Load and instantiate a plugin by ID.

        Args:
            plugin_id: Plugin ID to load

        Returns:
            Instantiated plugin

        Raises:
            PluginLoadError: If plugin cannot be loaded
        """
        with self._instances_lock:
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

        # Module-level plugins may import sibling helpers; keep module directory importable.
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

        return plugin_class

    def execute_plugin(
        self,
        plugin_id: str,
        ctx: PluginContext,
        stage: Stage,
        phase: Phase = Phase.RUN,
        timeout: Optional[float] = None,
        *,
        record_result: bool = True,
        contract_warnings: bool = False,
        contract_errors: bool = False,
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
                        phase=phase.value,
                        message=f"Plugin not found: {plugin_id}",
                        path="kernel",
                        plugin_id="kernel",
                    )
                ],
            )

        spec = self.specs[plugin_id]
        effective_timeout = timeout if timeout is not None else spec.timeout

        # Runtime config already present in ctx.config takes precedence over manifest defaults.
        base_config = ctx.config.copy()
        scoped_config = {**spec.config, **base_config}
        produced_key_scopes = self._declared_produced_scopes(spec)
        scope = PluginExecutionScope(
            plugin_id=plugin_id,
            allowed_dependencies=frozenset(spec.depends_on),
            phase=phase,
            config=scoped_config,
            stage=stage,
            produced_key_scopes=produced_key_scopes,
        )

        try:
            plugin = self.load_plugin(plugin_id)
        except (PluginLoadError, PluginConfigError) as e:
            return PluginResult.failed(
                plugin_id=plugin_id,
                api_version=spec.api_version,
                diagnostics=[
                    PluginDiagnostic(
                        code="E4004",
                        severity="error",
                        stage=stage.value,
                        phase=phase.value,
                        message=str(e),
                        path="kernel",
                        plugin_id="kernel",
                    )
                ],
            )

        scope_token = ctx._set_execution_scope(scope)
        execution_context = contextvars.copy_context()
        publish_event_start = ctx._get_publish_event_count()
        subscribe_event_start = ctx._get_subscribe_event_count()
        required_consume_diags = self._validate_required_consumes_pre_run(
            spec=spec,
            ctx=ctx,
            stage=stage,
            phase=phase,
        )
        if required_consume_diags:
            failed = PluginResult.failed(
                plugin_id=plugin_id,
                api_version=spec.api_version,
                diagnostics=required_consume_diags,
            )
            if record_result:
                self._results.append(failed)
            ctx._clear_execution_scope(scope_token)
            return failed

        # Execute with timeout
        start_time = time.perf_counter()
        timed_out = False
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        try:
            future = executor.submit(execution_context.run, plugin.execute_phase, ctx, stage, phase)
            try:
                result = future.result(timeout=effective_timeout)
                duration_ms = (time.perf_counter() - start_time) * 1000
                # Update duration in result
                result.duration_ms = duration_ms
                self._attach_data_bus_contract_diagnostics(
                    spec=spec,
                    ctx=ctx,
                    stage=stage,
                    phase=phase,
                    result=result,
                    publish_event_start=publish_event_start,
                    subscribe_event_start=subscribe_event_start,
                    emit_warnings=contract_warnings,
                    undeclared_as_errors=contract_errors,
                )
                if record_result:
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
                        phase=phase.value,
                        message=f"Plugin exceeded timeout of {effective_timeout}s",
                        path="kernel",
                        plugin_id="kernel",
                    )
                )
                self._attach_data_bus_contract_diagnostics(
                    spec=spec,
                    ctx=ctx,
                    stage=stage,
                    phase=phase,
                    result=result,
                    publish_event_start=publish_event_start,
                    subscribe_event_start=subscribe_event_start,
                    emit_warnings=contract_warnings,
                    undeclared_as_errors=contract_errors,
                )
                if record_result:
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
                        phase=phase.value,
                        message=f"Plugin crashed: {e}",
                        path="kernel",
                        plugin_id="kernel",
                    )
                ],
            )
            self._attach_data_bus_contract_diagnostics(
                spec=spec,
                ctx=ctx,
                stage=stage,
                phase=phase,
                result=result,
                publish_event_start=publish_event_start,
                subscribe_event_start=subscribe_event_start,
                emit_warnings=contract_warnings,
                undeclared_as_errors=contract_errors,
            )
            if record_result:
                self._results.append(result)
            return result
        finally:
            # Do not wait for timed-out plugins; this avoids blocking the pipeline
            # after we already returned TIMEOUT.
            executor.shutdown(wait=not timed_out, cancel_futures=True)
            ctx._clear_execution_scope(scope_token)

    def execute_stage(
        self,
        stage: Stage,
        ctx: PluginContext,
        profile: Optional[str] = None,
        fail_fast: bool = False,
        parallel_plugins: bool = False,
        trace_execution: bool = False,
        contract_warnings: bool = False,
        contract_errors: bool = False,
    ) -> list[PluginResult]:
        """Execute all plugins for a stage.

        Args:
            stage: Pipeline stage to execute
            ctx: Execution context
            profile: Current execution profile
            fail_fast: Stop on first failure
            parallel_plugins: Enable parallel execution within each stage/phase
            trace_execution: Record stage/phase/plugin execution trace events
            contract_warnings: Emit transitional W800x warnings for undeclared produces/consumes
            contract_errors: Treat undeclared produces/consumes as hard errors (Wave H style)

        Returns:
            List of PluginResult for each executed plugin
        """
        results: list[PluginResult] = []
        phase_plugin_ids: dict[Phase, list[str]] = {
            phase: self.get_execution_order(stage, profile, phase=phase) for phase in PHASE_ORDER
        }
        ordered_plugin_ids = [plugin_id for phase in PHASE_ORDER for plugin_id in phase_plugin_ids[phase]]

        if not ordered_plugin_ids:
            return results

        if trace_execution:
            self._trace_event(
                event="stage_start",
                stage=stage,
                message=f"plugins={len(ordered_plugin_ids)} parallel={parallel_plugins}",
            )

        invalidated_stage_local: list[str] = []
        try:
            stage_failure_context: list[dict[str, Any]] = []
            ctx.config["stage_failure_context"] = stage_failure_context

            def _record_stage_failure(result: PluginResult, *, phase: Phase) -> None:
                if result.status not in {PluginStatus.FAILED, PluginStatus.TIMEOUT}:
                    return
                diagnostics_payload: list[dict[str, Any]] = []
                diag_codes = [
                    diag.code
                    for diag in result.diagnostics
                    if isinstance(diag, PluginDiagnostic) and isinstance(diag.code, str) and diag.code
                ]
                for diag in result.diagnostics:
                    if not isinstance(diag, PluginDiagnostic):
                        continue
                    diagnostics_payload.append(
                        {
                            "code": diag.code,
                            "severity": diag.severity,
                            "phase": diag.phase,
                            "message": diag.message,
                            "path": diag.path,
                            "plugin_id": diag.plugin_id,
                        }
                    )
                stage_failure_context.append(
                    {
                        "plugin_id": result.plugin_id,
                        "status": result.status.value,
                        "phase": phase.value,
                        "diagnostic_codes": diag_codes,
                        "diagnostics": diagnostics_payload,
                    }
                )

            when_allowed_by_plugin: dict[str, bool] = {}
            for plugin_id in ordered_plugin_ids:
                spec = self.specs.get(plugin_id)
                if spec is None:
                    when_allowed_by_plugin[plugin_id] = False
                    continue
                when_allowed_by_plugin[plugin_id] = self._when_predicates_allow(spec, ctx)

            active_plugin_ids = [
                plugin_id for plugin_id in ordered_plugin_ids if when_allowed_by_plugin.get(plugin_id, False)
            ]
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
                                phase=Phase.RUN.value,
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
            for plugin_id in active_plugin_ids:
                spec = self.specs.get(plugin_id)
                if not isinstance(spec, PluginSpec):
                    continue
                declared_model_versions = [
                    item for item in spec.model_versions if isinstance(item, str) and item.strip()
                ]
                if not declared_model_versions:
                    continue
                if not isinstance(core_model_version, str) or not core_model_version:
                    model_version_diags.append(
                        PluginDiagnostic(
                            code="E4012",
                            severity="error",
                            stage=stage.value,
                            phase=Phase.RUN.value,
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
                            phase=Phase.RUN.value,
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
                if not self._profile_allows_spec(spec, profile):
                    continue
                if not self._when_predicates_allow(spec, ctx):
                    continue
                for capability in spec.capabilities:
                    if isinstance(capability, str) and capability:
                        available_capabilities.add(capability)

            preflight_diags: list[PluginDiagnostic] = []
            for plugin_id in active_plugin_ids:
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

            if parallel_plugins:
                self._preload_plugins(active_plugin_ids)

            fail_fast_triggered = False
            for phase in PHASE_ORDER:
                if fail_fast_triggered and phase is not Phase.FINALIZE:
                    continue

                if trace_execution:
                    self._trace_event(event="phase_start", stage=stage, phase=phase)

                phase_active_plugin_ids: list[str] = []
                for plugin_id in phase_plugin_ids[phase]:
                    spec = self.specs.get(plugin_id)
                    if spec is None:
                        continue

                    if not when_allowed_by_plugin.get(plugin_id, False):
                        skipped = PluginResult.skipped(
                            plugin_id=plugin_id,
                            api_version=spec.api_version,
                            reason=f"when predicate evaluated to false for phase '{phase.value}'",
                        )
                        skipped.diagnostics.append(
                            PluginDiagnostic(
                                code="I4013",
                                severity="info",
                                stage=stage.value,
                                phase=phase.value,
                                message=f"Plugin '{plugin_id}' skipped by when predicates.",
                                path=f"plugin:{plugin_id}",
                                plugin_id="kernel",
                            )
                        )
                        results.append(skipped)
                        self._results.append(skipped)
                        if trace_execution:
                            self._trace_event(
                                event="plugin_result",
                                stage=stage,
                                phase=phase,
                                plugin_id=plugin_id,
                                status=skipped.status,
                                message="when=false",
                            )
                        continue

                    phase_active_plugin_ids.append(plugin_id)

                if not phase_active_plugin_ids:
                    continue

                use_parallel_phase_executor = parallel_plugins and not fail_fast and len(phase_active_plugin_ids) > 1
                if use_parallel_phase_executor:
                    phase_results = self._execute_phase_parallel(
                        stage=stage,
                        phase=phase,
                        ctx=ctx,
                        plugin_ids=phase_active_plugin_ids,
                        trace_execution=trace_execution,
                        contract_warnings=contract_warnings,
                        contract_errors=contract_errors,
                    )
                    results.extend(phase_results)
                    for phase_result in phase_results:
                        _record_stage_failure(phase_result, phase=phase)
                    continue

                for plugin_id in phase_active_plugin_ids:
                    if trace_execution:
                        self._trace_event(event="plugin_start", stage=stage, phase=phase, plugin_id=plugin_id)
                    result = self.execute_plugin(
                        plugin_id,
                        ctx,
                        stage,
                        phase=phase,
                        contract_warnings=contract_warnings,
                        contract_errors=contract_errors,
                    )
                    results.append(result)
                    _record_stage_failure(result, phase=phase)
                    if trace_execution:
                        self._trace_event(
                            event="plugin_result",
                            stage=stage,
                            phase=phase,
                            plugin_id=plugin_id,
                            status=result.status,
                        )

                    if (
                        fail_fast
                        and phase is not Phase.FINALIZE
                        and result.status in (PluginStatus.FAILED, PluginStatus.TIMEOUT)
                    ):
                        fail_fast_triggered = True
                        break

            return results
        finally:
            invalidated_stage_local = ctx.invalidate_stage_local_data(stage)
            if trace_execution:
                suffix = f"invalidated_stage_local={len(invalidated_stage_local)}"
                self._trace_event(event="stage_end", stage=stage, message=suffix)

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

    def get_execution_trace(self) -> list[dict[str, Any]]:
        """Return execution trace events collected in trace mode."""
        with self._trace_lock:
            return [entry.copy() for entry in self._execution_trace]

    def reset_execution_trace(self) -> None:
        """Clear stored execution trace."""
        with self._trace_lock:
            self._execution_trace.clear()

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
