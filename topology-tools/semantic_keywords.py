"""Semantic keyword registry and resolution helpers (ADR0088)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml_loader import load_yaml_file


@dataclass(frozen=True)
class SemanticTokenSpec:
    token: str
    canonical: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class SemanticResolution:
    value: Any | None
    key: str | None
    present_keys: tuple[str, ...]

    @property
    def found(self) -> bool:
        return self.key is not None

    @property
    def has_collision(self) -> bool:
        return len(self.present_keys) > 1


class SemanticKeywordRegistry:
    """Context-scoped semantic key registry."""

    def __init__(
        self,
        *,
        specs: dict[str, SemanticTokenSpec],
        contexts: dict[str, set[str]],
    ) -> None:
        self._specs = specs
        self._contexts = contexts

    def get(self, token: str) -> SemanticTokenSpec:
        return self._specs[token]

    def allowed(self, *, context: str, token: str) -> bool:
        allowed_tokens = self._contexts.get(context)
        if allowed_tokens is None:
            return False
        return token in allowed_tokens


def _default_specs() -> dict[str, SemanticTokenSpec]:
    return {
        "schema_version": SemanticTokenSpec("schema_version", "@version", ("version",)),
        "class_id": SemanticTokenSpec("class_id", "@class", ("class",)),
        "object_id": SemanticTokenSpec("object_id", "@object", ("object",)),
        "instance_id": SemanticTokenSpec("instance_id", "@instance", ("instance",)),
        "parent_ref": SemanticTokenSpec("parent_ref", "@extends", ("extends",)),
        "entity_title": SemanticTokenSpec("entity_title", "@title", ("title",)),
        "entity_summary": SemanticTokenSpec("entity_summary", "@summary", ("summary",)),
        "entity_description": SemanticTokenSpec("entity_description", "@description", ("description",)),
        "entity_layer": SemanticTokenSpec("entity_layer", "@layer", ("layer",)),
        "capability_id": SemanticTokenSpec("capability_id", "@capability", ("capability", "id")),
        "capability_schema": SemanticTokenSpec("capability_schema", "@schema", ("schema",)),
    }


def _default_contexts() -> dict[str, set[str]]:
    return {
        "entity_manifest": {
            "schema_version",
            "class_id",
            "object_id",
            "instance_id",
            "parent_ref",
            "entity_title",
            "entity_summary",
            "entity_description",
            "entity_layer",
        },
        "capability_entry": {
            "capability_id",
            "capability_schema",
            "entity_title",
            "entity_summary",
        },
    }


def _normalize_spec(token: str, item: Any, fallback: SemanticTokenSpec) -> SemanticTokenSpec:
    if not isinstance(item, dict):
        return fallback
    canonical = item.get("canonical")
    aliases_raw = item.get("aliases")
    if not isinstance(canonical, str) or not canonical.strip():
        return fallback
    aliases: list[str] = []
    if isinstance(aliases_raw, list):
        for entry in aliases_raw:
            if isinstance(entry, str) and entry.strip():
                aliases.append(entry.strip())
    return SemanticTokenSpec(token=token, canonical=canonical.strip(), aliases=tuple(aliases))


def _normalize_contexts(payload: Any, defaults: dict[str, set[str]]) -> dict[str, set[str]]:
    if not isinstance(payload, dict):
        return defaults
    result = {name: set(tokens) for name, tokens in defaults.items()}
    for context_name, config in payload.items():
        if not isinstance(context_name, str) or not isinstance(config, dict):
            continue
        tokens_raw = config.get("tokens")
        if not isinstance(tokens_raw, list):
            continue
        tokens = {token for token in tokens_raw if isinstance(token, str) and token.strip()}
        if tokens:
            result[context_name] = tokens
    return result


def load_semantic_keyword_registry(path: Path | None) -> SemanticKeywordRegistry:
    defaults = _default_specs()
    contexts = _default_contexts()
    if path is None or not path.exists() or not path.is_file():
        return SemanticKeywordRegistry(specs=defaults, contexts=contexts)
    try:
        payload = load_yaml_file(path) or {}
    except (OSError, yaml.YAMLError):
        return SemanticKeywordRegistry(specs=defaults, contexts=contexts)
    if not isinstance(payload, dict):
        return SemanticKeywordRegistry(specs=defaults, contexts=contexts)
    registry_payload = payload.get("registry")
    if isinstance(registry_payload, dict):
        merged_specs: dict[str, SemanticTokenSpec] = {}
        for token, fallback in defaults.items():
            merged_specs[token] = _normalize_spec(token, registry_payload.get(token), fallback)
    else:
        merged_specs = defaults
    merged_contexts = _normalize_contexts(payload.get("contexts"), contexts)
    return SemanticKeywordRegistry(specs=merged_specs, contexts=merged_contexts)


def resolve_semantic_value(
    payload: dict[str, Any],
    *,
    registry: SemanticKeywordRegistry,
    context: str,
    token: str,
) -> SemanticResolution:
    if not registry.allowed(context=context, token=token):
        return SemanticResolution(value=None, key=None, present_keys=())
    spec = registry.get(token)
    ordered = (spec.canonical, *spec.aliases)
    present = [key for key in ordered if key in payload]
    if not present:
        return SemanticResolution(value=None, key=None, present_keys=())
    key = spec.canonical if spec.canonical in present else present[0]
    return SemanticResolution(value=payload.get(key), key=key, present_keys=tuple(present))
