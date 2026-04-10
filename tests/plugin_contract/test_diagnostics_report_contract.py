#!/usr/bin/env python3
"""Contract checks for diagnostics report schema compatibility."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema


def _detect_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "topology-tools").is_dir() or (candidate / "topology-tools").is_dir():
            return candidate
    return current.parents[2]


def _tools_root(repo_root: Path) -> Path:
    extracted = repo_root / "topology-tools"
    if extracted.is_dir():
        return extracted
    return repo_root / "topology-tools"


def _load_compiler_module():
    repo_root = _detect_repo_root()
    module_path = _tools_root(repo_root) / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_diagnostics_contract", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_diagnostics_report_matches_schema(tmp_path: Path):
    mod = _load_compiler_module()
    tools_root = Path(mod.DEFAULT_ERROR_CATALOG).parent.parent
    out_dir = tmp_path / "diagnostics-contract"
    diagnostics_path = out_dir / "diagnostics.json"
    report_txt = out_dir / "diagnostics.txt"
    effective_json = out_dir / "effective-topology.json"
    topology_path = out_dir / "topology.yaml"
    topology_path.parent.mkdir(parents=True, exist_ok=True)
    topology_path.write_text("version: 5.0.0\n", encoding="utf-8")

    diagnostics = [
        mod.CompilerDiagnostic(
            code="I4001",
            severity="info",
            stage="load",
            message="schema-contract-fixture",
            path="topology.yaml",
            confidence=1.0,
        )
    ]
    total, errors, warnings, infos = mod.write_diagnostics_report(
        diagnostics=diagnostics,
        diagnostics_json=diagnostics_path,
        diagnostics_txt=report_txt,
        topology_path=topology_path,
        error_catalog_path=Path(mod.DEFAULT_ERROR_CATALOG),
        output_json=effective_json,
        repo_root=out_dir,
        now_iso=lambda: "2026-03-20T00:00:00+00:00",
        plugin_stats={
            "loaded": 1,
            "executed": 1,
            "failed": 0,
            "by_kind": {"compiler": 1},
            "execution_order": ["base.compiler.fixture"],
        },
        plugin_manifests=["plugins.yaml"],
    )
    assert (total, errors, warnings, infos) == (1, 0, 0, 1)

    report = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    schema = json.loads((tools_root / "schemas" / "diagnostics.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)

    assert report["report_version"] == "2.0.0"
    assert "plugins" in report
    assert report["summary"]["total"] == len(report["diagnostics"])
