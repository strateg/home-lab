#!/usr/bin/env python3
"""Inspect compiled topology (classes, objects, instances, and instance dependencies)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

REF_KEY_PATTERN = re.compile(r".*(_ref|_refs)$")


def _load_effective(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"effective topology not found: {path}. Run `task validate:default` first.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid effective topology payload type: {type(payload).__name__}")
    return payload


def _flatten_instances(payload: dict[str, Any]) -> list[dict[str, Any]]:
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


def _source_aliases(instances: list[dict[str, Any]]) -> dict[str, str]:
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


def _iter_refs(data: Any, prefix: str = "") -> list[tuple[str, Any]]:
    matches: list[tuple[str, Any]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if REF_KEY_PATTERN.fullmatch(key):
                matches.append((path, value))
            matches.extend(_iter_refs(value, path))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            path = f"{prefix}[{index}]"
            matches.extend(_iter_refs(value, path))
    return matches


def _normalize_ref_values(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        values = [value for value in raw if isinstance(value, str)]
        return values
    return []


def _build_dependency_graph(
    instances: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, list[str]], dict[str, list[str]]]:
    aliases = _source_aliases(instances)
    edges: dict[str, set[str]] = defaultdict(set)
    unresolved: dict[str, list[str]] = defaultdict(list)
    edge_labels: dict[str, list[str]] = defaultdict(list)

    for item in instances:
        instance_id = item.get("instance_id")
        if not isinstance(instance_id, str):
            continue

        scan_roots = [item.get("instance_data"), item.get("instance")]
        for root in scan_roots:
            for path, raw_value in _iter_refs(root):
                for raw_ref in _normalize_ref_values(raw_value):
                    mapped = aliases.get(raw_ref)
                    if mapped is None:
                        unresolved[instance_id].append(raw_ref)
                        continue
                    if mapped == instance_id:
                        continue
                    edges[instance_id].add(mapped)
                    edge_labels[f"{instance_id}->{mapped}"].append(path)

    return edges, unresolved, edge_labels


def _resolve_instance_id(instances: list[dict[str, Any]], value: str) -> str | None:
    aliases = _source_aliases(instances)
    return aliases.get(value)


def _print_summary(payload: dict[str, Any], instances: list[dict[str, Any]]) -> None:
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


def _print_classes_tree(payload: dict[str, Any]) -> None:
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


def _print_objects_by_class(payload: dict[str, Any]) -> None:
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
    for class_ref in sorted(grouped):
        values = sorted(grouped[class_ref])
        print(f"- {class_ref} ({len(values)})")
        for object_id in values:
            print(f"  - {object_id}")


def _print_instances_tree(instances: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in instances:
        layer = item.get("layer", "unknown")
        grouped[str(layer)].append(item)

    print("Instances by Layer")
    print("==================")
    for layer in sorted(grouped):
        rows = grouped[layer]
        print(f"- {layer} ({len(rows)})")
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


def _print_search(instances: list[dict[str, Any]], query: str) -> None:
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


def _print_deps(instances: list[dict[str, Any]], instance_ref: str, max_depth: int) -> int:
    resolved = _resolve_instance_id(instances, instance_ref)
    if resolved is None:
        print(f"Unknown instance reference: {instance_ref}")
        return 2

    edges, unresolved, edge_labels = _build_dependency_graph(instances)
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

    return 0


def _write_dot(instances: list[dict[str, Any]], output: Path) -> None:
    edges, unresolved, _ = _build_dependency_graph(instances)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = ["digraph instance_deps {", '  rankdir="LR";']
    for item in sorted(instances, key=lambda row: str(row.get("instance_id", ""))):
        instance_id = item.get("instance_id")
        if isinstance(instance_id, str):
            lines.append(f'  "{instance_id}";')
    for source in sorted(edges):
        for target in sorted(edges[source]):
            lines.append(f'  "{source}" -> "{target}";')
    for source in sorted(unresolved):
        for ref in sorted(set(unresolved[source])):
            lines.append(f'  "{source}" -> "unresolved::{ref}" [style=dashed];')
            lines.append(f'  "unresolved::{ref}" [shape=box, color=gray];')
    lines.append("}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote dependency graph: {output}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect compiled topology artifacts.")
    parser.add_argument(
        "--effective",
        default="build/effective-topology.json",
        help="Path to effective topology JSON (default: build/effective-topology.json)",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("summary", help="Print high-level topology summary.")
    subparsers.add_parser("classes", help="Print class hierarchy tree.")
    subparsers.add_parser("objects", help="Print objects grouped by class.")
    subparsers.add_parser("instances", help="Print instances grouped by layer.")

    search_parser = subparsers.add_parser("search", help="Search instances by regex pattern.")
    search_parser.add_argument("--query", required=True, help="Regex query.")

    deps_parser = subparsers.add_parser("deps", help="Show dependency graph around one instance.")
    deps_parser.add_argument("--instance", required=True, help="Instance reference (instance_id or source_id).")
    deps_parser.add_argument("--max-depth", type=int, default=3, help="Max transitive depth (default: 3).")

    dot_parser = subparsers.add_parser("deps-dot", help="Write full instance dependency graph to Graphviz DOT.")
    dot_parser.add_argument(
        "--output",
        default="build/diagnostics/topology-instance-deps.dot",
        help="DOT output path (default: build/diagnostics/topology-instance-deps.dot)",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    command = args.command or "summary"
    payload = _load_effective(Path(args.effective))
    instances = _flatten_instances(payload)

    if command == "summary":
        _print_summary(payload, instances)
        return 0
    if command == "classes":
        _print_classes_tree(payload)
        return 0
    if command == "objects":
        _print_objects_by_class(payload)
        return 0
    if command == "instances":
        _print_instances_tree(instances)
        return 0
    if command == "search":
        _print_search(instances, args.query)
        return 0
    if command == "deps":
        return _print_deps(instances, args.instance, max_depth=max(args.max_depth, 1))
    if command == "deps-dot":
        _write_dot(instances, Path(args.output))
        return 0

    print(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"[inspect][error] {error}", file=sys.stderr)
        raise SystemExit(2) from error
