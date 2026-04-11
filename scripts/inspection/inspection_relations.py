#!/usr/bin/env python3
"""Dependency relation helpers for topology inspection."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_indexes import source_aliases


REF_KEY_PATTERN = re.compile(r".*(_ref|_refs)$")


def iter_refs(data: Any, prefix: str = "") -> list[tuple[str, Any]]:
    matches: list[tuple[str, Any]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if REF_KEY_PATTERN.fullmatch(key):
                matches.append((path, value))
            matches.extend(iter_refs(value, path))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            path = f"{prefix}[{index}]"
            matches.extend(iter_refs(value, path))
    return matches


def normalize_ref_values(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [value for value in raw if isinstance(value, str)]
    return []


def build_dependency_graph(
    instances: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, list[str]], dict[str, list[str]]]:
    aliases = source_aliases(instances)
    edges: dict[str, set[str]] = defaultdict(set)
    unresolved: dict[str, list[str]] = defaultdict(list)
    edge_labels: dict[str, list[str]] = defaultdict(list)

    for item in instances:
        instance_id = item.get("instance_id")
        if not isinstance(instance_id, str):
            continue

        scan_roots = [item.get("instance_data"), item.get("instance")]
        for root in scan_roots:
            for path, raw_value in iter_refs(root):
                for raw_ref in normalize_ref_values(raw_value):
                    mapped = aliases.get(raw_ref)
                    if mapped is None:
                        unresolved[instance_id].append(raw_ref)
                        continue
                    if mapped == instance_id:
                        continue
                    edges[instance_id].add(mapped)
                    edge_labels[f"{instance_id}->{mapped}"].append(path)

    return edges, unresolved, edge_labels


def resolve_instance_id(instances: list[dict[str, Any]], value: str) -> str | None:
    aliases = source_aliases(instances)
    return aliases.get(value)
