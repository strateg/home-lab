"""Plugin input snapshot builder (ADR 0063 registry decomposition).

This module handles building immutable input snapshots for plugin execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..pipeline_runtime import PipelineState
from ..plugin_base import (
    Phase,
    PluginContext,
    PluginDataExchangeError,
    PluginInputSnapshot,
    Stage,
)

if TYPE_CHECKING:
    from ..plugin_registry import PluginSpec

__all__ = ["SnapshotBuilder", "SerializablePluginSpec"]


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
    def from_plugin_spec(cls, spec: PluginSpec) -> SerializablePluginSpec:
        """Create minimal serializable spec from full PluginSpec.

        Uses JSON round-trip for proper deep copying of nested structures.
        """
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
    def from_dict(cls, data: dict[str, Any]) -> SerializablePluginSpec:
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


class SnapshotBuilder:
    """Build immutable input snapshots for plugin execution."""

    def __init__(
        self,
        specs: dict[str, PluginSpec],
        metadata_provider: Any = None,
    ) -> None:
        """Initialize builder.

        Args:
            specs: Dictionary of plugin ID -> PluginSpec
            metadata_provider: Optional callable for injecting additional metadata
        """
        self._specs = specs
        self._metadata_provider = metadata_provider

    def build(
        self,
        plugin_id: str,
        stage: Stage,
        phase: Phase,
        ctx: PluginContext,
        pipeline_state: PipelineState | None = None,
    ) -> PluginInputSnapshot:
        """Build immutable plugin input for envelope-model execution.

        Args:
            plugin_id: Plugin ID
            stage: Current stage
            phase: Current phase
            ctx: Execution context
            pipeline_state: Optional pipeline state for subscriptions

        Returns:
            Immutable PluginInputSnapshot
        """
        spec = self._specs[plugin_id]
        base_config = ctx.config.copy()
        scoped_config = {**spec.config, **base_config}

        # Inject metadata if provider available
        if self._metadata_provider:
            scoped_config = self._metadata_provider(plugin_id, scoped_config)

        produced_key_scopes = spec.declared_produced_scopes()

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
            changed_input_scopes=(list(ctx.changed_input_scopes) if ctx.changed_input_scopes else None),
            signing_backend=ctx.signing_backend,
            release_tag=ctx.release_tag,
            sbom_output_dir=ctx.sbom_output_dir,
            error_catalog=dict(ctx.error_catalog),
            source_file=ctx.source_file,
            compiled_file=ctx.compiled_file,
            subscriptions=subscriptions,
            allowed_dependencies=frozenset(spec.declared_dependency_ids()),
            produced_key_scopes=produced_key_scopes,
        )

    @staticmethod
    def _declared_consumes(spec: PluginSpec) -> set[tuple[str, str]]:
        """Extract declared (from_plugin, key) pairs."""
        result: set[tuple[str, str]] = set()
        for entry in spec.consumes:
            if not isinstance(entry, dict):
                continue
            from_plugin = entry.get("from_plugin")
            key = entry.get("key")
            if isinstance(from_plugin, str) and from_plugin and isinstance(key, str) and key:
                result.add((from_plugin, key))
        return result
