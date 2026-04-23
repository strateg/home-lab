"""Shared layer-derivation helpers for class -> object -> instance semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from semantic_keywords import SemanticKeywordRegistry, resolve_semantic_value
from yaml_loader import load_yaml_file


def _iter_yaml_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.yaml") if path.is_file())


def load_class_layer_map(
    *,
    class_modules_root: Path,
    semantic_registry: SemanticKeywordRegistry,
) -> dict[str, str]:
    class_layer_map: dict[str, str] = {}
    for class_file in _iter_yaml_files(class_modules_root):
        try:
            class_payload = load_yaml_file(class_file) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(class_payload, dict):
            continue
        class_resolution = resolve_semantic_value(
            class_payload,
            registry=semantic_registry,
            context="entity_manifest",
            token="class_id",
        )
        layer_resolution = resolve_semantic_value(
            class_payload,
            registry=semantic_registry,
            context="entity_manifest",
            token="entity_layer",
        )
        class_id = class_resolution.value if class_resolution.found else None
        class_layer = layer_resolution.value if layer_resolution.found else None
        if isinstance(class_id, str) and class_id and isinstance(class_layer, str) and class_layer:
            class_layer_map[class_id] = class_layer
    return class_layer_map


def load_object_layer_map(
    *,
    object_modules_root: Path,
    semantic_registry: SemanticKeywordRegistry,
    class_layer_map: dict[str, str] | None = None,
) -> dict[str, str]:
    object_layer_map: dict[str, str] = {}
    class_layers = class_layer_map or {}
    for object_file in _iter_yaml_files(object_modules_root):
        try:
            object_payload = load_yaml_file(object_file) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(object_payload, dict):
            continue
        object_resolution = resolve_semantic_value(
            object_payload,
            registry=semantic_registry,
            context="entity_manifest",
            token="object_id",
        )
        class_ref_resolution = resolve_semantic_value(
            object_payload,
            registry=semantic_registry,
            context="entity_manifest",
            token="parent_ref",
        )
        object_id = object_resolution.value if object_resolution.found else None
        class_ref = class_ref_resolution.value if class_ref_resolution.found else None
        derived_layer = class_layers.get(class_ref) if isinstance(class_ref, str) and class_ref else None
        resolved_layer = derived_layer if isinstance(derived_layer, str) and derived_layer else None
        if isinstance(object_id, str) and object_id and isinstance(resolved_layer, str) and resolved_layer:
            object_layer_map[object_id] = resolved_layer
    return object_layer_map
