"""Plugin manifest loader (ADR 0063 registry decomposition).

This module handles loading and parsing plugin manifests from YAML files.
"""

from __future__ import annotations

import json
from collections.abc import Container
from pathlib import Path
from typing import Any

import yaml
from yaml_loader import load_yaml_file

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# PluginManifest is defined in kernel.specs (leaf types module) and
# re-exported here for backwards compatibility (ADR 0063 decomposition).
from ..specs import PluginManifest

__all__ = ["ManifestLoader", "PluginManifest", "ManifestLoadError"]


class ManifestLoadError(Exception):
    """Error loading a plugin manifest."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        self.message = message
        super().__init__(f"Manifest '{source}': {message}")


class ManifestLoader:
    """Load and validate plugin manifests from YAML files."""

    def __init__(self, schema_path: Path | None = None) -> None:
        """Initialize manifest loader.

        Args:
            schema_path: Path to JSON schema for manifest validation.
                         If None, schema validation is skipped.
        """
        self.schema_path = schema_path
        self._schema: dict[str, Any] | None = None
        # Append order of both lists is observable API: the registry facade
        # aliases them and compile-topology.py reads slices of load errors.
        self._load_errors: list[str] = []
        self.manifests: list[str] = []

    @property
    def load_errors(self) -> list[str]:
        """Return accumulated load errors."""
        return list(self._load_errors)

    def _get_schema(self) -> dict[str, Any]:
        """Load and cache manifest JSON schema."""
        if self._schema is not None:
            return self._schema

        if not HAS_JSONSCHEMA:
            raise ManifestLoadError(
                "manifest.schema",
                "jsonschema dependency is required for plugin manifest validation.",
            )
        if self.schema_path is None:
            raise ManifestLoadError(
                "manifest.schema",
                "No schema path configured for manifest validation.",
            )
        if not self.schema_path.exists():
            raise ManifestLoadError(
                "manifest.schema",
                f"Plugin manifest schema not found: {self.schema_path}",
            )
        try:
            self._schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestLoadError(
                "manifest.schema",
                f"Failed to load plugin manifest schema '{self.schema_path}': {exc}",
            ) from exc
        return self._schema

    def validate_payload(self, payload: dict[str, Any], manifest_path: Path) -> None:
        """Validate manifest payload against JSON schema."""
        if self.schema_path is None:
            return  # Skip validation if no schema configured
        schema = self._get_schema()
        try:
            jsonschema.validate(payload, schema)
        except jsonschema.ValidationError as exc:
            raise ManifestLoadError(
                str(manifest_path),
                f"Schema validation failed: {exc.message}",
            ) from exc

    def load_manifest(
        self,
        manifest_path: Path,
        spec_factory: Any,
        on_spec: Any = None,
        *,
        existing_ids: Container[str] | None = None,
        _loaded_paths: set[Path] | None = None,
    ) -> PluginManifest | None:
        """Load plugins from a manifest file.

        Supports 'includes' key for manifest sharding: include paths are
        resolved relative to the manifest file directory and loaded first.
        Duplicate plugin IDs (membership test against existing_ids) are
        recorded in load_errors and skipped.

        Args:
            manifest_path: Path to manifest YAML file
            spec_factory: Callable to create PluginSpec from dict
            on_spec: Optional callback(spec) for each non-duplicate spec
                     (the registry facade validates and registers specs here)
            existing_ids: Container of already-registered plugin IDs
            _loaded_paths: Internal set for circular include protection

        Returns:
            Loaded PluginManifest, or None if manifest_path was already
            loaded in this traversal (circular include protection)
        """
        if _loaded_paths is None:
            _loaded_paths = set()

        resolved_path = manifest_path.resolve()
        if resolved_path in _loaded_paths:
            return None  # Skip already-loaded manifests (circular include protection)
        _loaded_paths.add(resolved_path)

        try:
            payload = load_yaml_file(manifest_path) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ManifestLoadError("manifest.load", f"Failed to parse manifest '{manifest_path}': {exc}") from exc
        if not isinstance(payload, dict):
            raise ManifestLoadError("manifest.load", f"Manifest root must be mapping/object: {manifest_path}")

        # Process includes first (allows sharding into stage-specific manifests)
        includes = payload.get("includes", [])
        if isinstance(includes, list):
            manifest_dir = manifest_path.parent
            for include_path in includes:
                if isinstance(include_path, str) and include_path.strip():
                    include_resolved = (manifest_dir / include_path.strip()).resolve()
                    if include_resolved.exists():
                        try:
                            self.load_manifest(
                                include_resolved,
                                spec_factory,
                                on_spec,
                                existing_ids=existing_ids,
                                _loaded_paths=_loaded_paths,
                            )
                        except Exception as e:
                            self._load_errors.append(f"Error loading included manifest {include_path}: {e}")
                    else:
                        self._load_errors.append(f"Included manifest not found: {include_path}")

        self.validate_payload(payload, manifest_path)
        manifest = PluginManifest.from_data(payload, str(manifest_path), spec_factory)
        self.manifests.append(str(manifest_path))

        for spec in manifest.plugins:
            if existing_ids is not None and spec.id in existing_ids:
                self._load_errors.append(f"Duplicate plugin ID: {spec.id}")
                continue
            if on_spec:
                on_spec(spec)

        return manifest

    def load_manifests_from_dir(
        self,
        search_dir: Path,
        spec_factory: Any,
        on_spec: Any = None,
        *,
        existing_ids: Container[str] | None = None,
        pattern: str = "plugins.yaml",
    ) -> None:
        """Recursively load all plugin manifests from a directory.

        Load failures are recorded in load_errors (append-only order is
        observable API) instead of being raised.

        Args:
            search_dir: Directory to search
            spec_factory: Callable to create PluginSpec from dict
            on_spec: Optional callback(spec) for each non-duplicate spec
            existing_ids: Container of already-registered plugin IDs
            pattern: Glob pattern for manifest files
        """
        for manifest_path in search_dir.rglob(pattern):
            try:
                self.load_manifest(
                    manifest_path,
                    spec_factory,
                    on_spec,
                    existing_ids=existing_ids,
                )
            except Exception as e:
                self._load_errors.append(f"Error loading {manifest_path}: {e}")
