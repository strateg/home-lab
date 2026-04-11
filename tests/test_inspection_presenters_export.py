#!/usr/bin/env python3
"""Unit-level contract checks for inspection presenter/export helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSPECTION_DIR = REPO_ROOT / "scripts" / "inspection"


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_presenters_print_deps_returns_2_for_unknown_instance(capsys) -> None:
    presenters = _load_module(INSPECTION_DIR / "inspection_presenters.py", "inspection_presenters_unknown")
    instances = [{"instance_id": "inst.router", "source_id": "rtr-main"}]

    code = presenters.print_deps(instances, "missing-instance", max_depth=3)

    assert code == 2
    assert "Unknown instance reference: missing-instance" in capsys.readouterr().out


def test_presenters_print_search_reports_no_matches(capsys) -> None:
    presenters = _load_module(INSPECTION_DIR / "inspection_presenters.py", "inspection_presenters_search")
    instances = [{"instance_id": "inst.router", "source_id": "rtr-main", "layer": "L3", "instance_data": {}}]

    presenters.print_search(instances, "does-not-exist")

    out = capsys.readouterr().out
    assert "Search matches for pattern: does-not-exist" in out
    assert "No matches." in out


def test_export_write_dot_writes_edges_and_unresolved_nodes(tmp_path: Path, capsys) -> None:
    export = _load_module(INSPECTION_DIR / "inspection_export.py", "inspection_export_contract")
    instances = [
        {
            "instance_id": "inst.router",
            "source_id": "rtr-main",
            "instance_data": {
                "service_ref": "svc-api",
                "broken_ref": "missing.ref",
            },
            "instance": {},
        },
        {
            "instance_id": "inst.service.api",
            "source_id": "svc-api",
            "instance_data": {},
            "instance": {},
        },
    ]
    output = tmp_path / "build" / "deps.dot"

    export.write_dot(instances, output)

    out = capsys.readouterr().out
    assert f"Wrote dependency graph: {output}" in out
    dot = output.read_text(encoding="utf-8")
    assert '"inst.router" -> "inst.service.api";' in dot
    assert '"inst.router" -> "unresolved::missing.ref" [style=dashed];' in dot
