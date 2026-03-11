#!/usr/bin/env python3
"""Contract checks for diagnostics report schema compatibility."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "v5" / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_diagnostics_contract", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_diagnostics_report_matches_schema(tmp_path: Path):
    mod = _load_compiler_module()
    out_dir = mod.REPO_ROOT / "v5-build" / "test-diagnostics-contract" / tmp_path.name
    diagnostics_path = out_dir / "diagnostics.json"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=out_dir / "effective-topology.json",
        diagnostics_json=diagnostics_path,
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    exit_code = compiler.run()
    assert exit_code == 0

    report = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    schema = json.loads((mod.REPO_ROOT / "v5" / "topology-tools" / "schemas" / "diagnostics.schema.json").read_text())
    jsonschema.validate(report, schema)

    assert report["report_version"] == "2.0.0"
    assert "plugins" in report
    assert report["summary"]["total"] == len(report["diagnostics"])
