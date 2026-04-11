#!/usr/bin/env python3
"""Normalized index helpers for topology inspection flows."""

from __future__ import annotations

from typing import Any


def flatten_instances(payload: dict[str, Any]) -> list[dict[str, Any]]:
    grouped = payload.get("instances", {})
    if not isinstance(grouped, dict):
        return []
    items: list[dict[str, Any]] = []
    for group_name, group_items in grouped.items():
        if not isinstance(group_items, list):
            continue
        for item in group_items:
            if isinstance(item, dict):
                item_copy = dict(item)
                item_copy["_group"] = group_name
                items.append(item_copy)
    return items


def source_aliases(instances: list[dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for item in instances:
        instance_id = item.get("instance_id")
        if not isinstance(instance_id, str):
            continue
        aliases[instance_id] = instance_id
        source_id = item.get("source_id")
        if isinstance(source_id, str) and source_id:
            aliases[source_id] = instance_id
        if instance_id.startswith("inst.") and len(instance_id) > len("inst."):
            aliases[instance_id[len("inst.") :]] = instance_id
    return aliases


def filter_instances(
    instances: list[dict[str, Any]],
    *,
    layer: str | None = None,
    group: str | None = None,
) -> list[dict[str, Any]]:
    if not layer and not group:
        return list(instances)
    filtered: list[dict[str, Any]] = []
    for item in instances:
        if layer and str(item.get("layer", "")) != layer:
            continue
        if group and str(item.get("_group", "")) != group:
            continue
        filtered.append(item)
    return filtered


def object_class_ref(object_payload: dict[str, Any]) -> str | None:
    for key in ("materializes_class", "class_ref", "extends_class"):
        value = object_payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None
