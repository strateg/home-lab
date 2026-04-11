#!/usr/bin/env python3
"""Human-readable rendering helpers for topology inspection."""

from __future__ import annotations

import json
import re
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


def print_summary(payload: dict[str, Any], instances: list[dict[str, Any]]) -> None:
    classes = payload.get("classes", {})
    objects = payload.get("objects", {})
    groups = payload.get("instances", {})
    print("Topology Inspection Summary")
    print("==========================")
    print(f"classes: {len(classes) if isinstance(classes, dict) else 0}")
    print(f"objects: {len(objects) if isinstance(objects, dict) else 0}")
    print(f"instances: {len(instances)}")
    print(f"instance groups: {len(groups) if isinstance(groups, dict) else 0}")
    if isinstance(groups, dict):
        for group_name in sorted(groups):
            size = len(groups[group_name]) if isinstance(groups[group_name], list) else 0
            print(f"  - {group_name}: {size}")


def print_capability_packs(payload: dict[str, Any], *, effective_path: Path) -> None:
    classes = payload.get("classes", {})
    objects = payload.get("objects", {})
    if not isinstance(classes, dict):
        classes = {}
    if not isinstance(objects, dict):
        objects = {}

    packs_catalog, packs_path = load_capability_pack_catalog(payload, effective_path=effective_path)

    class_pack_refs: dict[str, list[str]] = {}
    for class_id, class_payload in classes.items():
        if not isinstance(class_payload, dict):
            continue
        pack_refs = class_payload.get("capability_packs", []) or []
        if not isinstance(pack_refs, list):
            continue
        normalized = [value for value in pack_refs if isinstance(value, str) and value]
        if normalized:
            class_pack_refs[class_id] = sorted(set(normalized))

    class_objects: dict[str, list[str]] = defaultdict(list)
    object_enabled_packs: dict[str, list[str]] = {}
    for object_id, object_payload in objects.items():
        if not isinstance(object_payload, dict):
            continue
        class_ref = object_class_ref(object_payload)
        if isinstance(class_ref, str):
            class_objects[class_ref].append(object_id)
        enabled_packs = object_payload.get("enabled_packs", []) or []
        if isinstance(enabled_packs, list):
            normalized = sorted({value for value in enabled_packs if isinstance(value, str) and value})
            if normalized:
                object_enabled_packs[object_id] = normalized

    object_pack_usage: dict[str, list[str]] = defaultdict(list)
    object_pack_usage_by_class: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for object_id, packs in object_enabled_packs.items():
        object_payload = objects.get(object_id, {})
        class_ref = object_class_ref(object_payload) if isinstance(object_payload, dict) else None
        for pack_id in packs:
            object_pack_usage[pack_id].append(object_id)
            if isinstance(class_ref, str):
                object_pack_usage_by_class[class_ref][pack_id].append(object_id)

    missing_class_pack_refs = sorted(
        {
            pack_id
            for refs in class_pack_refs.values()
            for pack_id in refs
            if pack_id not in packs_catalog
        }
    )
    missing_object_pack_refs = sorted({pack_id for pack_id in object_pack_usage if pack_id not in packs_catalog})

    print("Capability Packs Inspection")
    print("===========================")
    print(f"catalog path: {packs_path}")
    print(f"catalog packs: {len(packs_catalog)}")
    print(f"classes with capability_packs: {len(class_pack_refs)}")
    print(f"objects with enabled_packs: {len(object_enabled_packs)}")

    print("\nPack Catalog")
    print("------------")
    for pack_id in sorted(packs_catalog):
        pack_payload = packs_catalog[pack_id]
        class_ref = pack_payload.get("class_ref", "-")
        capabilities = pack_payload.get("capabilities", [])
        capability_count = len(capabilities) if isinstance(capabilities, list) else 0
        used_by = sorted(object_pack_usage.get(pack_id, []))
        print(f"- {pack_id} (class_ref={class_ref}, capabilities={capability_count}, used_by_objects={len(used_by)})")
        if used_by:
            print(f"  objects: {', '.join(used_by)}")

    print("\nClass -> Pack Dependencies")
    print("--------------------------")
    for class_id in sorted(class_pack_refs):
        packs = class_pack_refs[class_id]
        bound_objects = sorted(class_objects.get(class_id, []))
        print(f"- {class_id} (declared_packs={len(packs)}, objects={len(bound_objects)})")
        if bound_objects:
            print(f"  object_ids: {', '.join(bound_objects)}")
        for pack_id in packs:
            status = "ok" if pack_id in packs_catalog else "missing_catalog"
            consumers = sorted(object_pack_usage_by_class.get(class_id, {}).get(pack_id, []))
            print(f"  - {pack_id} [{status}] (enabled_by_objects={len(consumers)})")
            if consumers:
                print(f"    objects: {', '.join(consumers)}")

    out_of_contract: list[str] = []
    for object_id, packs in sorted(object_enabled_packs.items()):
        object_payload = objects.get(object_id, {})
        if not isinstance(object_payload, dict):
            continue
        class_ref = object_class_ref(object_payload)
        if not isinstance(class_ref, str):
            continue
        declared = set(class_pack_refs.get(class_ref, []))
        for pack_id in packs:
            if pack_id not in declared:
                out_of_contract.append(f"{object_id}:{pack_id} (class={class_ref})")

    print("\nContract Warnings")
    print("-----------------")
    if not missing_class_pack_refs and not missing_object_pack_refs and not out_of_contract:
        print("none")
        return
    if missing_class_pack_refs:
        print(f"- class capability_packs missing in catalog: {', '.join(missing_class_pack_refs)}")
    if missing_object_pack_refs:
        print(f"- object enabled_packs missing in catalog: {', '.join(missing_object_pack_refs)}")
    if out_of_contract:
        print("- object enabled_packs not declared by its class capability_packs:")
        for row in out_of_contract:
            print(f"  - {row}")


def print_capabilities(
    payload: dict[str, Any],
    *,
    effective_path: Path,
    class_ref: str | None = None,
    object_id: str | None = None,
) -> int:
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

    object_caps: dict[str, list[str]] = {}
    object_packs: dict[str, list[str]] = {}
    class_objects: dict[str, list[str]] = defaultdict(list)
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
            print(f"Unknown class reference: {class_ref}")
            return 2
        print(f"Capabilities for class: {class_ref}")
        print("================================")
        required = class_required.get(class_ref, [])
        optional = class_optional.get(class_ref, [])
        packs = class_packs.get(class_ref, [])
        print("Required capabilities:")
        if not required:
            print("  - none")
        else:
            for row in required:
                print(f"  - {row}")
        print("Optional capabilities:")
        if not optional:
            print("  - none")
        else:
            for row in optional:
                print(f"  - {row}")
        print("Capability packs:")
        if not packs:
            print("  - none")
        else:
            for row in packs:
                status = "ok" if row in packs_catalog else "missing_catalog"
                print(f"  - {row} [{status}]")
        print("Bound objects:")
        bound = sorted(class_objects.get(class_ref, []))
        if not bound:
            print("  - none")
        else:
            for row in bound:
                print(f"  - {row}")
        return 0

    if object_id is not None:
        object_payload = objects.get(object_id)
        if not isinstance(object_payload, dict):
            print(f"Unknown object reference: {object_id}")
            return 2
        cls = object_class_ref(object_payload)
        print(f"Capabilities for object: {object_id}")
        print("================================")
        print(f"class: {cls if isinstance(cls, str) else '-'}")
        print("Enabled capabilities:")
        caps = object_caps.get(object_id, [])
        if not caps:
            print("  - none")
        else:
            for row in caps:
                print(f"  - {row}")
        print("Enabled packs:")
        packs = object_packs.get(object_id, [])
        if not packs:
            print("  - none")
        else:
            for row in packs:
                status = "ok" if row in packs_catalog else "missing_catalog"
                print(f"  - {row} [{status}]")
        if isinstance(cls, str):
            print("Class required capabilities:")
            for row in class_required.get(cls, []) or ["none"]:
                print(f"  - {row}")
            print("Class optional capabilities:")
            for row in class_optional.get(cls, []) or ["none"]:
                print(f"  - {row}")
        return 0

    print("Capability Relation Summary")
    print("===========================")
    print(f"classes total: {len(classes)}")
    print(f"classes with required_capabilities: {len(class_required)}")
    print(f"classes with optional_capabilities: {len(class_optional)}")
    print(f"classes with capability_packs: {len(class_packs)}")
    print(f"objects total: {len(objects)}")
    print(f"objects with enabled_capabilities: {len(object_caps)}")
    print(f"objects with enabled_packs: {len(object_packs)}")
    print(f"catalog packs: {len(packs_catalog)}")

    print("\nClass Capability Intents")
    print("------------------------")
    for cls_id in sorted({*class_required.keys(), *class_optional.keys(), *class_packs.keys()}):
        req = len(class_required.get(cls_id, []))
        opt = len(class_optional.get(cls_id, []))
        packs = len(class_packs.get(cls_id, []))
        print(f"- {cls_id} (required={req}, optional={opt}, packs={packs})")

    print("\nObject Capability Activations")
    print("-----------------------------")
    for obj_id in sorted({*object_caps.keys(), *object_packs.keys()}):
        caps = len(object_caps.get(obj_id, []))
        packs = len(object_packs.get(obj_id, []))
        cls = object_class_ref(objects.get(obj_id, {})) if isinstance(objects.get(obj_id), dict) else "-"
        print(f"- {obj_id} (class={cls}, enabled_capabilities={caps}, enabled_packs={packs})")

    print("\nPack Capability Catalog")
    print("-----------------------")
    for pack_id in sorted(packs_catalog):
        row = packs_catalog[pack_id]
        cls = row.get("class_ref", "-")
        caps = row.get("capabilities", [])
        cap_count = len(caps) if isinstance(caps, list) else 0
        print(f"- {pack_id} (class_ref={cls}, capabilities={cap_count})")

    return 0


def print_classes_tree(payload: dict[str, Any]) -> None:
    classes = payload.get("classes", {})
    if not isinstance(classes, dict):
        print("No classes found.")
        return

    children: dict[str, list[str]] = defaultdict(list)
    roots: list[str] = []
    for class_id, class_payload in classes.items():
        if not isinstance(class_payload, dict):
            roots.append(class_id)
            continue
        parent = class_payload.get("parent_class")
        if isinstance(parent, str) and parent:
            children[parent].append(class_id)
        else:
            roots.append(class_id)

    for parent in children:
        children[parent].sort()
    roots.sort()

    print("Class Tree")
    print("==========")

    def walk(node: str, depth: int) -> None:
        print(f"{'  ' * depth}- {node}")
        for child in children.get(node, []):
            walk(child, depth + 1)

    for root in roots:
        walk(root, 0)


def print_inheritance(payload: dict[str, Any], class_ref: str | None = None) -> int:
    classes = payload.get("classes", {})
    if not isinstance(classes, dict):
        print("No classes found.")
        return 0

    children: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, str] = {}
    roots: list[str] = []
    for class_id, class_payload in classes.items():
        if not isinstance(class_payload, dict):
            roots.append(class_id)
            continue
        parent = class_payload.get("parent_class")
        if isinstance(parent, str) and parent:
            children[parent].append(class_id)
            parents[class_id] = parent
        else:
            roots.append(class_id)

    for parent_id in children:
        children[parent_id].sort()
    roots.sort()

    if class_ref is None:
        print("Class Inheritance Summary")
        print("=========================")
        print(f"classes total: {len(classes)}")
        print(f"root classes: {len(roots)}")
        print(f"derived classes: {len(parents)}")
        if roots:
            print("Roots:")
            for row in roots:
                print(f"  - {row}")
        return 0

    if class_ref not in classes:
        print(f"Unknown class reference: {class_ref}")
        return 2

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

    print(f"Class inheritance for: {class_ref}")
    print("====================================")
    print("Ancestors:")
    if not ancestors:
        print("  - none")
    else:
        for row in ancestors:
            print(f"  - {row}")

    direct_children = children.get(class_ref, [])
    print("Direct children:")
    if not direct_children:
        print("  - none")
    else:
        for row in direct_children:
            print(f"  - {row}")

    print("All descendants:")
    if not descendants:
        print("  - none")
    else:
        for row in descendants:
            print(f"  - {row}")

    return 0


def print_objects_by_class(payload: dict[str, Any], *, detailed: bool = False) -> None:
    objects = payload.get("objects", {})
    if not isinstance(objects, dict):
        print("No objects found.")
        return

    grouped: dict[str, list[str]] = defaultdict(list)
    for object_id, object_payload in objects.items():
        class_ref = "unbound"
        if isinstance(object_payload, dict):
            class_ref = object_payload.get("materializes_class") or object_payload.get("extends_class") or "unbound"
        grouped[str(class_ref)].append(object_id)

    print("Objects by Class")
    print("================")
    print(f"total objects: {len(objects)}")
    for class_ref in sorted(grouped):
        values = sorted(grouped[class_ref])
        print(f"- {class_ref} ({len(values)})")
        if detailed:
            for object_id in values:
                print(f"  - {object_id}")


def print_instances_tree(instances: list[dict[str, Any]], *, detailed: bool = False) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in instances:
        layer = item.get("layer", "unknown")
        grouped[str(layer)].append(item)

    print("Instances by Layer")
    print("==================")
    print(f"total instances: {len(instances)}")
    for layer in sorted(grouped):
        rows = grouped[layer]
        print(f"- {layer} ({len(rows)})")
        if detailed:
            for item in sorted(rows, key=lambda row: str(row.get("instance_id", ""))):
                instance_id = item.get("instance_id", "unknown")
                source_id = item.get("source_id", "-")
                meta = item.get("instance", {})
                materializes_object = "-"
                materializes_class = "-"
                if isinstance(meta, dict):
                    materializes_object = meta.get("materializes_object", "-")
                    materializes_class = meta.get("materializes_class", "-")
                print(f"  - {instance_id} (source={source_id}, object={materializes_object}, class={materializes_class})")


def print_search(instances: list[dict[str, Any]], query: str) -> None:
    pattern = re.compile(query, re.IGNORECASE)
    matches: list[dict[str, Any]] = []
    for item in instances:
        text = json.dumps(
            {
                "instance_id": item.get("instance_id"),
                "source_id": item.get("source_id"),
                "layer": item.get("layer"),
                "instance_data": item.get("instance_data", {}),
            },
            ensure_ascii=True,
        )
        if pattern.search(text):
            matches.append(item)

    print(f"Search matches for pattern: {query}")
    print("==================================")
    if not matches:
        print("No matches.")
        return
    for item in sorted(matches, key=lambda row: str(row.get("instance_id", ""))):
        print(f"- {item.get('instance_id')} (source={item.get('source_id')}, layer={item.get('layer')})")


def print_deps(
    instances: list[dict[str, Any]],
    instance_ref: str,
    max_depth: int,
    *,
    typed_shadow: bool = False,
) -> int:
    resolved = resolve_instance_id(instances, instance_ref)
    if resolved is None:
        print(f"Unknown instance reference: {instance_ref}")
        return 2

    edges, unresolved, edge_labels = build_dependency_graph(instances)
    incoming: dict[str, set[str]] = defaultdict(set)
    for source, targets in edges.items():
        for target in targets:
            incoming[target].add(source)

    print(f"Dependencies for: {resolved}")
    print("==============================")
    direct_outgoing = sorted(edges.get(resolved, set()))
    direct_incoming = sorted(incoming.get(resolved, set()))

    print("Outgoing (direct):")
    if not direct_outgoing:
        print("  - none")
    for target in direct_outgoing:
        labels = ", ".join(sorted(set(edge_labels.get(f"{resolved}->{target}", []))))
        print(f"  - {target} [{labels}]")

    print("Incoming (direct):")
    if not direct_incoming:
        print("  - none")
    for source in direct_incoming:
        labels = ", ".join(sorted(set(edge_labels.get(f"{source}->{resolved}", []))))
        print(f"  - {source} [{labels}]")

    print(f"Transitive outgoing (depth <= {max_depth}):")
    visited: set[str] = {resolved}
    queue: deque[tuple[str, int]] = deque((node, 1) for node in direct_outgoing)
    while queue:
        node, depth = queue.popleft()
        if node in visited or depth > max_depth:
            continue
        visited.add(node)
        print(f"  - depth={depth} {node}")
        for nxt in sorted(edges.get(node, set())):
            queue.append((nxt, depth + 1))

    missing = sorted(set(unresolved.get(resolved, [])))
    print("Unresolved refs:")
    if not missing:
        print("  - none")
    for ref in missing:
        print(f"  - {ref}")

    if typed_shadow:
        shadow = typed_relation_shadow(edge_labels)
        print("Typed relation shadow (non-authoritative):")
        has_rows = False
        for target in direct_outgoing:
            edge_key = f"{resolved}->{target}"
            types = shadow.get(edge_key, [])
            if types:
                has_rows = True
                print(f"  - outgoing {edge_key}: {', '.join(types)}")
        for source in direct_incoming:
            edge_key = f"{source}->{resolved}"
            types = shadow.get(edge_key, [])
            if types:
                has_rows = True
                print(f"  - incoming {edge_key}: {', '.join(types)}")
        if not has_rows:
            print("  - none")

    return 0
