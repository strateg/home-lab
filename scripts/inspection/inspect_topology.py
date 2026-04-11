#!/usr/bin/env python3
"""Inspect compiled topology (classes, objects, instances, and instance dependencies)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_export import write_dot as _write_dot  # noqa: E402
from inspection_indexes import flatten_instances as _flatten_instances  # noqa: E402
from inspection_loader import load_effective as _load_effective  # noqa: E402
from inspection_presenters import (  # noqa: E402
    print_capability_packs as _print_capability_packs,
    print_classes_tree as _print_classes_tree,
    print_deps as _print_deps,
    print_inheritance as _print_inheritance,
    print_instances_tree as _print_instances_tree,
    print_objects_by_class as _print_objects_by_class,
    print_search as _print_search,
    print_summary as _print_summary,
)


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
    inheritance_parser = subparsers.add_parser("inheritance", help="Inspect class inheritance and lineage.")
    add_effective_arg(inheritance_parser)
    inheritance_parser.add_argument("--class", dest="class_ref", help="Class reference for focused lineage.")
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
    if command == "inheritance":
        return _print_inheritance(payload, args.class_ref)
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
