"""Strict YAML loading helpers for runtime compile/validate/generate paths."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class _StrictMappingLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects duplicate mapping keys."""


def _construct_mapping_no_duplicates(
    loader: _StrictMappingLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as exc:  # pragma: no cover - parity with PyYAML error path
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found unhashable key ({key})",
                key_node.start_mark,
            ) from exc
        if key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key ({key!r})",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_StrictMappingLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_duplicates,
)


_AT_KEY_PATTERN = re.compile(r"(^[ \t-]*)(@[^:\s]+)(\s*:)", re.MULTILINE)


def _quote_at_prefixed_keys(content: str) -> str:
    """Normalize @prefixed YAML keys into quoted keys for parser compatibility."""

    def _replace(match: re.Match[str]) -> str:
        prefix = match.group(1)
        key = match.group(2)
        suffix = match.group(3)
        return f'{prefix}"{key}"{suffix}'

    return _AT_KEY_PATTERN.sub(_replace, content)


def load_yaml_text(content: str) -> Any:
    """Load YAML text with duplicate-key rejection."""
    try:
        return yaml.load(content, Loader=_StrictMappingLoader)
    except yaml.YAMLError as exc:
        if "cannot start any token" not in str(exc) or "character '@'" not in str(exc):
            raise
        normalized = _quote_at_prefixed_keys(content)
        return yaml.load(normalized, Loader=_StrictMappingLoader)


def load_yaml_file(path: Path) -> Any:
    """Load YAML from file with duplicate-key rejection."""
    return load_yaml_text(path.read_text(encoding="utf-8"))
