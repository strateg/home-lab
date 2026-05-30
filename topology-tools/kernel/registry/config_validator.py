"""Plugin configuration validator (ADR 0063 registry decomposition).

This module handles plugin configuration validation against JSON schemas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

if TYPE_CHECKING:
    from ..plugin_registry import PluginSpec

__all__ = ["ConfigValidator", "ConfigValidationError"]


class ConfigValidationError(Exception):
    """Plugin configuration validation error."""

    def __init__(self, plugin_id: str, message: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"Plugin '{plugin_id}' config error: {message}")


class ConfigValidator:
    """Validate plugin configurations against JSON schemas."""

    def __init__(self, base_path: Path) -> None:
        """Initialize validator.

        Args:
            base_path: Base path for resolving schema paths
        """
        self.base_path = base_path
        self._schema_cache: dict[str, dict[str, Any]] = {}

    def validate(self, spec: PluginSpec) -> list[str]:
        """Validate plugin config against its config_schema.

        Args:
            spec: Plugin specification

        Returns:
            List of validation errors (empty if valid)
        """
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

    def resolve_schema_path(self, spec: PluginSpec, schema_ref: str) -> Path | None:
        """Resolve schema_ref to actual file path.

        Args:
            spec: Plugin specification
            schema_ref: Schema reference (relative or absolute path)

        Returns:
            Resolved path or None if not found
        """
        raw = schema_ref.strip()
        if not raw:
            return None

        candidate = Path(raw)
        if candidate.is_absolute():
            return candidate if candidate.exists() else None

        # Try relative to manifest
        manifest_relative = Path(spec.manifest_path).parent / raw
        if manifest_relative.exists():
            return manifest_relative

        # Try relative to base_path
        base_relative = self.base_path / raw
        if base_relative.exists():
            return base_relative

        return None

    def load_payload_schema(
        self, spec: PluginSpec, schema_ref: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Load and validate a payload schema.

        Args:
            spec: Plugin specification
            schema_ref: Schema reference

        Returns:
            Tuple of (schema dict or None, error message or None)
        """
        if not HAS_JSONSCHEMA:
            return None, "jsonschema dependency is required for schema_ref validation."

        schema_path = self.resolve_schema_path(spec, schema_ref)
        if schema_path is None:
            return None, f"schema_ref '{schema_ref}' cannot be resolved for plugin '{spec.id}'."

        cache_key = str(schema_path.resolve())
        cached = self._schema_cache.get(cache_key)
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

        self._schema_cache[cache_key] = schema
        return schema, None

    def schema_ref_by_produced_key(self, spec: PluginSpec) -> dict[str, str]:
        """Extract schema_ref for each produced key.

        Args:
            spec: Plugin specification

        Returns:
            Dict mapping key -> schema_ref
        """
        refs: dict[str, str] = {}
        for entry in spec.produces:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            schema_ref = entry.get("schema_ref")
            if (
                isinstance(key, str)
                and key
                and isinstance(schema_ref, str)
                and schema_ref.strip()
            ):
                refs[key] = schema_ref.strip()
        return refs

    def schema_ref_by_consumed_key(
        self, spec: PluginSpec
    ) -> dict[tuple[str, str], str]:
        """Extract schema_ref for each consumed key.

        Args:
            spec: Plugin specification

        Returns:
            Dict mapping (from_plugin, key) -> schema_ref
        """
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

    def validate_payload(
        self,
        payload: Any,
        schema: dict[str, Any],
    ) -> list[str]:
        """Validate payload against schema.

        Args:
            payload: Data to validate
            schema: JSON schema

        Returns:
            List of validation errors (empty if valid)
        """
        if not HAS_JSONSCHEMA:
            return []

        errors: list[str] = []
        try:
            jsonschema.validate(instance=payload, schema=schema)
        except jsonschema.ValidationError as e:
            errors.append(e.message)

        return errors
