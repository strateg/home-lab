"""Kernel plugin specification types and version constants (ADR 0063).

Leaf module of the kernel runtime decomposition: holds the shared data
types (`PluginSpec`, `PluginManifest`) and kernel version/compatibility
constants. Depends only on `kernel.plugin_base` (and yaml_loader for
manifest file parsing). Both `kernel.registry` and `kernel.scheduler`
import types from here; the `kernel.plugin_registry` facade re-exports
them for backwards compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from yaml_loader import load_yaml_file

from .plugin_base import (
    CompiledJsonView,
    InputViewSpec,
    MapFilterView,
    Phase,
    PluginKind,
    Stage,
    SubscriptionProjection,
)

__all__ = [
    "KERNEL_VERSION",
    "KERNEL_API_VERSION",
    "SUPPORTED_API_VERSIONS",
    "MODEL_VERSIONS",
    "EXECUTION_PROFILES",
    "DEFAULT_PLUGIN_TIMEOUT",
    "PluginSpec",
    "PluginManifest",
]

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
    execution_mode: str = "main_interpreter"  # ADR 0097 PR2: subinterpreter | main_interpreter | thread_legacy
    input_view: InputViewSpec | None = None  # ADR 0097 P4.2: snapshot filtering specification

    @classmethod
    def from_dict(cls, data: dict[str, Any], manifest_path: str = "") -> PluginSpec:
        """Create PluginSpec from manifest dictionary."""
        # Normalize entry path if it contains ../ and we have a manifest_path
        entry = data["entry"]
        if manifest_path and "../" in entry and ":" in entry:
            module_path, class_name = entry.rsplit(":", 1)
            manifest_dir = Path(manifest_path).parent
            normalized_module_path = (manifest_dir / module_path).resolve()
            # The entry should just be the normalized path as posix
            entry = f"{normalized_module_path.as_posix()}:{class_name}"

        return cls(
            id=data["id"],
            kind=PluginKind(data["kind"]),
            entry=entry,
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
            execution_mode=cls._resolve_execution_mode(data),
            input_view=cls._parse_input_view(data.get("input_view")),
        )

    @staticmethod
    def _parse_input_view(raw: dict[str, Any] | None) -> InputViewSpec | None:
        """Parse input_view manifest section into InputViewSpec.

        Supports the following manifest structure:
            input_view:
              compiled_json:
                include: ["$.instances[*].network"]
                exclude: []
              raw_yaml: false
              subscriptions:
                - from_plugin: base.compiler.instance_rows
                  key: normalized_rows
                  projection: "$.rows[?(@.layer=='L2')]"
              object_map:
                include_refs: ["network.*"]
              class_map:
                include_refs: ["network.*"]
        """
        if raw is None:
            return None
        if not isinstance(raw, dict):
            return None

        compiled_json_raw = raw.get("compiled_json")
        compiled_json = None
        if isinstance(compiled_json_raw, dict):
            compiled_json = CompiledJsonView(
                include=tuple(compiled_json_raw.get("include", [])),
                exclude=tuple(compiled_json_raw.get("exclude", [])),
            )

        raw_yaml = raw.get("raw_yaml", True)
        if not isinstance(raw_yaml, bool):
            raw_yaml = True

        subscriptions_raw = raw.get("subscriptions", [])
        subscriptions = []
        if isinstance(subscriptions_raw, list):
            for sub in subscriptions_raw:
                if isinstance(sub, dict) and all(k in sub for k in ("from_plugin", "key", "projection")):
                    subscriptions.append(
                        SubscriptionProjection(
                            from_plugin=str(sub["from_plugin"]),
                            key=str(sub["key"]),
                            projection=str(sub["projection"]),
                        )
                    )

        object_map_raw = raw.get("object_map")
        object_map = None
        if isinstance(object_map_raw, dict):
            object_map = MapFilterView(
                include_refs=tuple(object_map_raw.get("include_refs", [])),
                exclude_refs=tuple(object_map_raw.get("exclude_refs", [])),
            )

        class_map_raw = raw.get("class_map")
        class_map = None
        if isinstance(class_map_raw, dict):
            class_map = MapFilterView(
                include_refs=tuple(class_map_raw.get("include_refs", [])),
                exclude_refs=tuple(class_map_raw.get("exclude_refs", [])),
            )

        return InputViewSpec(
            compiled_json=compiled_json,
            raw_yaml=raw_yaml,
            subscriptions=tuple(subscriptions),
            object_map=object_map,
            class_map=class_map,
        )

    @staticmethod
    def _resolve_execution_mode(data: dict[str, Any]) -> str:
        """Resolve execution_mode from manifest data.

        ADR 0097 PR2: execution_mode is the primary routing field.
        Valid values: 'subinterpreter', 'main_interpreter', 'thread_legacy'.
        Default: 'main_interpreter' (envelope path in main interpreter).
        """
        explicit_mode = data.get("execution_mode")
        if explicit_mode is not None:
            if explicit_mode not in ("subinterpreter", "main_interpreter", "thread_legacy"):
                raise ValueError(
                    f"Invalid execution_mode '{explicit_mode}'. "
                    "Must be 'subinterpreter', 'main_interpreter', or 'thread_legacy'."
                )
            return explicit_mode

        # Default: main_interpreter (envelope path in main interpreter)
        return "main_interpreter"

    def declared_produced_scopes(self) -> dict[str, str]:
        """Extract declared produced keys and their scopes.

        Returns a mapping of key -> scope for all entries in self.produces.
        Handles both legacy string format and dict format:
          - String: "key_name" -> scope defaults to "pipeline_shared"
          - Dict: {"key": "key_name", "scope": "stage_local"} -> uses specified scope

        Returns:
            dict mapping key names to scope strings ("pipeline_shared" or "stage_local")
        """
        result: dict[str, str] = {}
        for item in self.produces:
            if isinstance(item, str):
                result[item] = "pipeline_shared"
            elif isinstance(item, dict):
                key = item.get("key")
                if isinstance(key, str) and key:
                    result[key] = item.get("scope", "pipeline_shared")
        return result

    def declared_dependency_ids(self) -> set[str]:
        """Return all explicitly declared upstream plugin IDs.

        Runtime subscribe authorization must cover both execution dependencies and
        consumes-declared data-bus producers. Some bootstrap-safe base-manifest
        plugins can only name later-discovered producers under consumes because
        those producer manifests are loaded after discover-stage bootstrap.
        """
        result = {item.strip() for item in self.depends_on if isinstance(item, str) and item.strip()}
        for item in self.consumes:
            if not isinstance(item, dict):
                continue
            from_plugin = item.get("from_plugin")
            if isinstance(from_plugin, str) and from_plugin.strip():
                result.add(from_plugin.strip())
        return result


@dataclass
class PluginManifest:
    """Parsed plugin manifest file."""

    schema_version: int
    plugins: list[PluginSpec]
    source_path: str

    @classmethod
    def from_data(cls, data: dict[str, Any], source_path: str, spec_factory: Any = None) -> PluginManifest:
        """Load manifest from parsed dictionary.

        Args:
            data: Parsed YAML data
            source_path: Path to manifest file
            spec_factory: Callable to create PluginSpec from dict
                          (defaults to PluginSpec.from_dict)
        """
        if data.get("schema_version") != 1:
            raise ValueError(f"Unsupported manifest schema_version in {source_path}")

        factory = spec_factory or PluginSpec.from_dict
        plugins = [factory(p, source_path) for p in data.get("plugins", [])]
        return cls(
            schema_version=data["schema_version"],
            plugins=plugins,
            source_path=source_path,
        )

    @classmethod
    def from_file(cls, path: Path, spec_factory: Any = None) -> PluginManifest:
        """Load manifest from YAML file."""
        data = load_yaml_file(path) or {}
        return cls.from_data(data, str(path), spec_factory)
