#!/usr/bin/env python3
"""Export helpers for topology inspection outputs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_relations import build_dependency_graph


def write_dot(instances: list[dict[str, Any]], output: Path) -> None:
    edges, unresolved, _ = build_dependency_graph(instances)
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
