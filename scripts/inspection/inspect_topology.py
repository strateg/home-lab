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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_indexes import (  # noqa: E402
    flatten_instances as _flatten_instances,
    object_class_ref as _object_class_ref,
    source_aliases as _source_aliases,
)
from inspection_loader import (  # noqa: E402
    load_capability_pack_catalog as _load_capability_pack_catalog,
    load_effective as _load_effective,
)

REF_KEY_PATTERN = re.compile(r".*(_ref|_refs)$")

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


def _print_capability_packs(payload: dict[str, Any], *, effective_path: Path) -> None:
    classes = payload.get("classes", {})
    objects = payload.get("objects", {})
    if not isinstance(classes, dict):
        classes = {}
    if not isinstance(objects, dict):
        objects = {}

    packs_catalog, packs_path = _load_capability_pack_catalog(payload, effective_path=effective_path)

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
        class_ref = _object_class_ref(object_payload)
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
        class_ref = _object_class_ref(object_payload) if isinstance(object_payload, dict) else None
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
        class_ref = _object_class_ref(object_payload)
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
    def add_effective_arg(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--effective",
            default="build/effective-topology.json",
            help="Path to effective topology JSON (default: build/effective-topology.json)",
        )

    add_effective_arg(parser)

    subparsers = parser.add_subparsers(dest="command")
    add_effective_arg(subparsers.add_parser("summary", help="Print high-level topology summary."))
    add_effective_arg(subparsers.add_parser("classes", help="Print class hierarchy tree."))
    add_effective_arg(subparsers.add_parser("objects", help="Print objects grouped by class."))
    add_effective_arg(subparsers.add_parser("instances", help="Print instances grouped by layer."))

    search_parser = subparsers.add_parser("search", help="Search instances by regex pattern.")
    add_effective_arg(search_parser)
    search_parser.add_argument("--query", required=True, help="Regex query.")

    deps_parser = subparsers.add_parser("deps", help="Show dependency graph around one instance.")
    add_effective_arg(deps_parser)
    deps_parser.add_argument("--instance", required=True, help="Instance reference (instance_id or source_id).")
    deps_parser.add_argument("--max-depth", type=int, default=3, help="Max transitive depth (default: 3).")

    dot_parser = subparsers.add_parser("deps-dot", help="Write full instance dependency graph to Graphviz DOT.")
    add_effective_arg(dot_parser)
    dot_parser.add_argument(
        "--output",
        default="build/diagnostics/topology-instance-deps.dot",
        help="DOT output path (default: build/diagnostics/topology-instance-deps.dot)",
    )
    capability_parser = subparsers.add_parser(
        "capability-packs",
        help="Inspect capability packs and class/object dependency bindings.",
    )
    add_effective_arg(capability_parser)

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
    if command == "capability-packs":
        _print_capability_packs(payload, effective_path=Path(args.effective))
        return 0

    print(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"[inspect][error] {error}", file=sys.stderr)
        raise SystemExit(2) from error
