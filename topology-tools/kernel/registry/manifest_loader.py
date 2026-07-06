"""Plugin manifest loader (ADR 0063 registry decomposition).

This module handles loading and parsing plugin manifests from YAML files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from yaml_loader import load_yaml_file

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

if TYPE_CHECKING:
    from ..plugin_registry import PluginSpec

__all__ = ["ManifestLoader", "PluginManifest", "ManifestLoadError"]


class ManifestLoadError(Exception):
    """Error loading a plugin manifest."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"Manifest '{source}': {message}")


@dataclass
class PluginManifest:
    """Parsed plugin manifest file."""

    schema_version: int
    plugins: list[PluginSpec]
    source_path: str

    @classmethod
    def from_data(cls, data: dict[str, Any], source_path: str, spec_factory: Any) -> PluginManifest:
        """Load manifest from parsed dictionary.

        Args:
            data: Parsed YAML data
            source_path: Path to manifest file
            spec_factory: Callable to create PluginSpec from dict (PluginSpec.from_dict)
        """
        if data.get("schema_version") != 1:
            raise ValueError(f"Unsupported manifest schema_version in {source_path}")

        plugins = [spec_factory(p, source_path) for p in data.get("plugins", [])]
        return cls(
            schema_version=data["schema_version"],
            plugins=plugins,
            source_path=source_path,
        )

    @classmethod
    def from_file(cls, path: Path, spec_factory: Any) -> PluginManifest:
        """Load manifest from YAML file."""
        data = load_yaml_file(path) or {}
        return cls.from_data(data, str(path), spec_factory)


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
        self._load_errors: list[str] = []

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
    ) -> PluginManifest:
        """Load plugins from a manifest file.

        Args:
            manifest_path: Path to manifest YAML file
            spec_factory: Callable to create PluginSpec from dict
            on_spec: Optional callback(spec) for each loaded spec

        Returns:
            Loaded PluginManifest
        """
        try:
            payload = load_yaml_file(manifest_path) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ManifestLoadError(str(manifest_path), f"Failed to parse: {exc}") from exc

        if not isinstance(payload, dict):
            raise ManifestLoadError(str(manifest_path), "Manifest root must be mapping/object")

        self.validate_payload(payload, manifest_path)
        manifest = PluginManifest.from_data(payload, str(manifest_path), spec_factory)

        if on_spec:
            for spec in manifest.plugins:
                on_spec(spec)

        return manifest

    def load_manifests_from_dir(
        self,
        search_dir: Path,
        spec_factory: Any,
        on_spec: Any = None,
        pattern: str = "plugins.yaml",
    ) -> list[PluginManifest]:
        """Recursively load all plugin manifests from a directory.

        Args:
            search_dir: Directory to search
            spec_factory: Callable to create PluginSpec from dict
            on_spec: Optional callback(spec) for each loaded spec
            pattern: Glob pattern for manifest files

        Returns:
            List of loaded manifests
        """
        manifests = []
        for manifest_path in search_dir.rglob(pattern):
            try:
                manifest = self.load_manifest(manifest_path, spec_factory, on_spec)
                manifests.append(manifest)
            except Exception as e:
                self._load_errors.append(f"Error loading {manifest_path}: {e}")
        return manifests
