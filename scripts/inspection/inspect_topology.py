#!/usr/bin/env python3
"""Inspect compiled topology (classes, objects, instances, and instance dependencies)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_export import write_dot as _write_dot  # noqa: E402
from inspection_indexes import flatten_instances as _flatten_instances  # noqa: E402
from inspection_json import deps_payload as _deps_payload  # noqa: E402
from inspection_json import capabilities_payload as _capabilities_payload  # noqa: E402
from inspection_json import inheritance_payload as _inheritance_payload  # noqa: E402
from inspection_json import summary_payload as _summary_payload  # noqa: E402
from inspection_loader import load_effective as _load_effective  # noqa: E402
from inspection_presenters import (  # noqa: E402
    print_capabilities as _print_capabilities,
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
    summary_parser = subparsers.add_parser("summary", help="Print high-level topology summary.")
    add_effective_arg(summary_parser)
    summary_parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON.")
    add_effective_arg(subparsers.add_parser("classes", help="Print class hierarchy tree."))
    inheritance_parser = subparsers.add_parser("inheritance", help="Inspect class inheritance and lineage.")
    add_effective_arg(inheritance_parser)
    inheritance_parser.add_argument("--class", dest="class_ref", help="Class reference for focused lineage.")
    inheritance_parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON.")
    objects_parser = subparsers.add_parser("objects", help="Print objects grouped by class.")
    add_effective_arg(objects_parser)
    objects_parser.add_argument("--detailed", action="store_true", help="Print detailed object rows.")

    instances_parser = subparsers.add_parser("instances", help="Print instances grouped by layer.")
    add_effective_arg(instances_parser)
    instances_parser.add_argument("--detailed", action="store_true", help="Print detailed instance rows.")

    search_parser = subparsers.add_parser("search", help="Search instances by regex pattern.")
    add_effective_arg(search_parser)
    search_parser.add_argument("--query", required=True, help="Regex query.")

    deps_parser = subparsers.add_parser("deps", help="Show dependency graph around one instance.")
    add_effective_arg(deps_parser)
    deps_parser.add_argument("--instance", required=True, help="Instance reference (instance_id or source_id).")
    deps_parser.add_argument("--max-depth", type=int, default=3, help="Max transitive depth (default: 3).")
    deps_parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON.")

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
    capabilities_parser = subparsers.add_parser(
        "capabilities",
        help="Inspect capability relations across classes, objects, and capability packs.",
    )
    add_effective_arg(capabilities_parser)
    scope = capabilities_parser.add_mutually_exclusive_group()
    scope.add_argument("--class", dest="class_ref", help="Focused class capability view.")
    scope.add_argument("--object", dest="object_id", help="Focused object capability view.")
    capabilities_parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON.")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    command = args.command or "summary"
    payload = _load_effective(Path(args.effective))
    instances = _flatten_instances(payload)

    if command == "summary":
        if bool(getattr(args, "as_json", False)):
            print(json.dumps(_summary_payload(payload, instances), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        _print_summary(payload, instances)
        return 0
    if command == "classes":
        _print_classes_tree(payload)
        return 0
    if command == "inheritance":
        if bool(getattr(args, "as_json", False)):
            code, body = _inheritance_payload(payload, class_ref=args.class_ref)
            print(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True))
            return code
        return _print_inheritance(payload, args.class_ref)
    if command == "objects":
        _print_objects_by_class(payload, detailed=bool(args.detailed))
        return 0
    if command == "instances":
        _print_instances_tree(instances, detailed=bool(args.detailed))
        return 0
    if command == "search":
        _print_search(instances, args.query)
        return 0
    if command == "deps":
        if bool(getattr(args, "as_json", False)):
            code, body = _deps_payload(instances, instance_ref=args.instance, max_depth=max(args.max_depth, 1))
            print(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True))
            return code
        return _print_deps(instances, args.instance, max_depth=max(args.max_depth, 1))
    if command == "deps-dot":
        _write_dot(instances, Path(args.output))
        return 0
    if command == "capability-packs":
        _print_capability_packs(payload, effective_path=Path(args.effective))
        return 0
    if command == "capabilities":
        if bool(getattr(args, "as_json", False)):
            code, body = _capabilities_payload(
                payload,
                effective_path=Path(args.effective),
                class_ref=args.class_ref,
                object_id=args.object_id,
            )
            print(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True))
            return code
        return _print_capabilities(
            payload,
            effective_path=Path(args.effective),
            class_ref=args.class_ref,
            object_id=args.object_id,
        )

    print(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"[inspect][error] {error}", file=sys.stderr)
        raise SystemExit(2) from error
