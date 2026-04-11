#!/usr/bin/env python3
"""Machine-readable JSON payload builders for inspection commands."""

from __future__ import annotations

import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_relations import build_dependency_graph, resolve_instance_id


SUMMARY_SCHEMA_VERSION = "adr0095.inspect.summary.v1"
DEPS_SCHEMA_VERSION = "adr0095.inspect.deps.v1"


def summary_payload(payload: dict[str, Any], instances: list[dict[str, Any]]) -> dict[str, Any]:
    classes = payload.get("classes", {})
    objects = payload.get("objects", {})
    groups = payload.get("instances", {})
    group_counts: dict[str, int] = {}
    if isinstance(groups, dict):
        for group_name in sorted(groups):
            group_items = groups[group_name]
            group_counts[group_name] = len(group_items) if isinstance(group_items, list) else 0

    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "command": "summary",
        "counts": {
            "classes": len(classes) if isinstance(classes, dict) else 0,
            "objects": len(objects) if isinstance(objects, dict) else 0,
            "instances": len(instances),
            "instance_groups": len(groups) if isinstance(groups, dict) else 0,
        },
        "instance_group_counts": group_counts,
    }


def deps_payload(
    instances: list[dict[str, Any]],
    *,
    instance_ref: str,
    max_depth: int,
) -> tuple[int, dict[str, Any]]:
    resolved = resolve_instance_id(instances, instance_ref)
    if resolved is None:
        return (
            2,
            {
                "schema_version": DEPS_SCHEMA_VERSION,
                "command": "deps",
                "error": {
                    "code": "unknown_instance_reference",
                    "message": f"Unknown instance reference: {instance_ref}",
                    "instance_ref": instance_ref,
                },
            },
        )

    edges, unresolved, edge_labels = build_dependency_graph(instances)
    incoming: dict[str, set[str]] = defaultdict(set)
    for source, targets in edges.items():
        for target in targets:
            incoming[target].add(source)

    direct_outgoing = sorted(edges.get(resolved, set()))
    direct_incoming = sorted(incoming.get(resolved, set()))

    transitive_outgoing: list[dict[str, Any]] = []
    visited: set[str] = {resolved}
    queue: deque[tuple[str, int]] = deque((node, 1) for node in direct_outgoing)
    while queue:
        node, depth = queue.popleft()
        if node in visited or depth > max_depth:
            continue
        visited.add(node)
        transitive_outgoing.append({"instance_id": node, "depth": depth})
        for nxt in sorted(edges.get(node, set())):
            queue.append((nxt, depth + 1))

    return (
        0,
        {
            "schema_version": DEPS_SCHEMA_VERSION,
            "command": "deps",
            "resolved_instance_id": resolved,
            "instance_ref": instance_ref,
            "max_depth": max_depth,
            "direct_outgoing": [
                {
                    "instance_id": target,
                    "labels": sorted(set(edge_labels.get(f"{resolved}->{target}", []))),
                }
                for target in direct_outgoing
            ],
            "direct_incoming": [
                {
                    "instance_id": source,
                    "labels": sorted(set(edge_labels.get(f"{source}->{resolved}", []))),
                }
                for source in direct_incoming
            ],
            "transitive_outgoing": transitive_outgoing,
            "unresolved_refs": sorted(set(unresolved.get(resolved, []))),
        },
    )
