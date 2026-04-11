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

from inspection_indexes import object_class_ref
from inspection_loader import load_capability_pack_catalog
from inspection_relations import build_dependency_graph, resolve_instance_id, typed_relation_shadow


SUMMARY_SCHEMA_VERSION = "adr0095.inspect.summary.v1"
DEPS_SCHEMA_VERSION = "adr0095.inspect.deps.v1"
INHERITANCE_SCHEMA_VERSION = "adr0095.inspect.inheritance.v1"
CAPABILITIES_SCHEMA_VERSION = "adr0095.inspect.capabilities.v1"


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
    include_typed_shadow: bool = False,
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

    body: dict[str, Any] = {
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
    }

    if include_typed_shadow:
        shadow = typed_relation_shadow(edge_labels)
        body["typed_shadow"] = {
            "schema_version": "adr0095.inspect.deps.typed-shadow.v1",
            "direct_outgoing": [
                {
                    "edge": f"{resolved}->{target}",
                    "types": shadow.get(f"{resolved}->{target}", []),
                }
                for target in direct_outgoing
            ],
            "direct_incoming": [
                {
                    "edge": f"{source}->{resolved}",
                    "types": shadow.get(f"{source}->{resolved}", []),
                }
                for source in direct_incoming
            ],
        }

    return (0, body)


def inheritance_payload(payload: dict[str, Any], *, class_ref: str | None = None) -> tuple[int, dict[str, Any]]:
    classes = payload.get("classes", {})
    if not isinstance(classes, dict):
        classes = {}

    children: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, str] = {}
    roots: list[str] = []
    for cls_id, class_payload in classes.items():
        if not isinstance(class_payload, dict):
            roots.append(cls_id)
            continue
        parent = class_payload.get("parent_class")
        if isinstance(parent, str) and parent:
            children[parent].append(cls_id)
            parents[cls_id] = parent
        else:
            roots.append(cls_id)

    for parent in children:
        children[parent].sort()
    roots.sort()

    if class_ref is None:
        return (
            0,
            {
                "schema_version": INHERITANCE_SCHEMA_VERSION,
                "command": "inheritance",
                "scope": "summary",
                "counts": {
                    "classes_total": len(classes),
                    "root_classes": len(roots),
                    "derived_classes": len(parents),
                },
                "roots": roots,
            },
        )

    if class_ref not in classes:
        return (
            2,
            {
                "schema_version": INHERITANCE_SCHEMA_VERSION,
                "command": "inheritance",
                "scope": "class",
                "error": {
                    "code": "unknown_class_reference",
                    "message": f"Unknown class reference: {class_ref}",
                    "class_ref": class_ref,
                },
            },
        )

    ancestors: list[str] = []
    cursor = class_ref
    while cursor in parents:
        parent = parents[cursor]
        ancestors.append(parent)
        cursor = parent

    descendants: list[str] = []
    queue: deque[str] = deque(children.get(class_ref, []))
    while queue:
        node = queue.popleft()
        descendants.append(node)
        queue.extend(children.get(node, []))

    return (
        0,
        {
            "schema_version": INHERITANCE_SCHEMA_VERSION,
            "command": "inheritance",
            "scope": "class",
            "class_ref": class_ref,
            "ancestors": ancestors,
            "direct_children": children.get(class_ref, []),
            "all_descendants": descendants,
        },
    )


def capabilities_payload(
    payload: dict[str, Any],
    *,
    effective_path: Path,
    class_ref: str | None = None,
    object_id: str | None = None,
) -> tuple[int, dict[str, Any]]:
    classes = payload.get("classes", {})
    objects = payload.get("objects", {})
    if not isinstance(classes, dict):
        classes = {}
    if not isinstance(objects, dict):
        objects = {}

    packs_catalog, _ = load_capability_pack_catalog(payload, effective_path=effective_path)

    class_required: dict[str, list[str]] = {}
    class_optional: dict[str, list[str]] = {}
    class_packs: dict[str, list[str]] = {}
    class_objects: dict[str, list[str]] = defaultdict(list)
    object_caps: dict[str, list[str]] = {}
    object_packs: dict[str, list[str]] = {}

    for cls_id, class_payload in classes.items():
        if not isinstance(class_payload, dict):
            continue
        required = sorted(
            {item for item in (class_payload.get("required_capabilities") or []) if isinstance(item, str) and item}
        )
        optional = sorted(
            {item for item in (class_payload.get("optional_capabilities") or []) if isinstance(item, str) and item}
        )
        packs = sorted({item for item in (class_payload.get("capability_packs") or []) if isinstance(item, str) and item})
        if required:
            class_required[cls_id] = required
        if optional:
            class_optional[cls_id] = optional
        if packs:
            class_packs[cls_id] = packs

    for obj_id, object_payload in objects.items():
        if not isinstance(object_payload, dict):
            continue
        cls = object_class_ref(object_payload)
        if isinstance(cls, str):
            class_objects[cls].append(obj_id)
        enabled_caps = sorted(
            {item for item in (object_payload.get("enabled_capabilities") or []) if isinstance(item, str) and item}
        )
        enabled_packs = sorted({item for item in (object_payload.get("enabled_packs") or []) if isinstance(item, str) and item})
        if enabled_caps:
            object_caps[obj_id] = enabled_caps
        if enabled_packs:
            object_packs[obj_id] = enabled_packs

    if class_ref is not None:
        if class_ref not in classes:
            return (
                2,
                {
                    "schema_version": CAPABILITIES_SCHEMA_VERSION,
                    "command": "capabilities",
                    "scope": "class",
                    "error": {
                        "code": "unknown_class_reference",
                        "message": f"Unknown class reference: {class_ref}",
                        "class_ref": class_ref,
                    },
                },
            )
        packs = class_packs.get(class_ref, [])
        return (
            0,
            {
                "schema_version": CAPABILITIES_SCHEMA_VERSION,
                "command": "capabilities",
                "scope": "class",
                "class_ref": class_ref,
                "required_capabilities": class_required.get(class_ref, []),
                "optional_capabilities": class_optional.get(class_ref, []),
                "capability_packs": [
                    {"pack_id": pack_id, "status": "ok" if pack_id in packs_catalog else "missing_catalog"}
                    for pack_id in packs
                ],
                "bound_objects": sorted(class_objects.get(class_ref, [])),
            },
        )

    if object_id is not None:
        object_payload = objects.get(object_id)
        if not isinstance(object_payload, dict):
            return (
                2,
                {
                    "schema_version": CAPABILITIES_SCHEMA_VERSION,
                    "command": "capabilities",
                    "scope": "object",
                    "error": {
                        "code": "unknown_object_reference",
                        "message": f"Unknown object reference: {object_id}",
                        "object_id": object_id,
                    },
                },
            )

        cls = object_class_ref(object_payload)
        return (
            0,
            {
                "schema_version": CAPABILITIES_SCHEMA_VERSION,
                "command": "capabilities",
                "scope": "object",
                "object_id": object_id,
                "class_ref": cls if isinstance(cls, str) else None,
                "enabled_capabilities": object_caps.get(object_id, []),
                "enabled_packs": [
                    {"pack_id": pack_id, "status": "ok" if pack_id in packs_catalog else "missing_catalog"}
                    for pack_id in object_packs.get(object_id, [])
                ],
                "class_required_capabilities": class_required.get(cls, []) if isinstance(cls, str) else [],
                "class_optional_capabilities": class_optional.get(cls, []) if isinstance(cls, str) else [],
            },
        )

    return (
        0,
        {
            "schema_version": CAPABILITIES_SCHEMA_VERSION,
            "command": "capabilities",
            "scope": "summary",
            "counts": {
                "classes_total": len(classes),
                "classes_with_required_capabilities": len(class_required),
                "classes_with_optional_capabilities": len(class_optional),
                "classes_with_capability_packs": len(class_packs),
                "objects_total": len(objects),
                "objects_with_enabled_capabilities": len(object_caps),
                "objects_with_enabled_packs": len(object_packs),
                "catalog_packs": len(packs_catalog),
            },
            "class_capability_intents": [
                {
                    "class_ref": cls_id,
                    "required_capabilities": len(class_required.get(cls_id, [])),
                    "optional_capabilities": len(class_optional.get(cls_id, [])),
                    "capability_packs": len(class_packs.get(cls_id, [])),
                }
                for cls_id in sorted({*class_required.keys(), *class_optional.keys(), *class_packs.keys()})
            ],
            "object_capability_activations": [
                {
                    "object_id": obj_id,
                    "class_ref": object_class_ref(objects.get(obj_id, {}))
                    if isinstance(objects.get(obj_id), dict)
                    else None,
                    "enabled_capabilities": len(object_caps.get(obj_id, [])),
                    "enabled_packs": len(object_packs.get(obj_id, [])),
                }
                for obj_id in sorted({*object_caps.keys(), *object_packs.keys()})
            ],
            "pack_catalog": [
                {
                    "pack_id": pack_id,
                    "class_ref": packs_catalog[pack_id].get("class_ref"),
                    "capabilities": len(packs_catalog[pack_id].get("capabilities", []))
                    if isinstance(packs_catalog[pack_id].get("capabilities"), list)
                    else 0,
                }
                for pack_id in sorted(packs_catalog)
            ],
        },
    )
