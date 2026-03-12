#!/usr/bin/env python3
"""Integration checks for TUC-0002 L1 power source chain modeling."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
V5_TOOLS = REPO_ROOT / "v5" / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))


def _load_compiler_module():
    module_path = REPO_ROOT / "v5" / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_module_tuc0002", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_tuc0002_compile_preserves_power_source_bindings(tmp_path: Path):
    mod = _load_compiler_module()
    out_dir = mod.REPO_ROOT / "v5-build" / "test-tuc0002" / tmp_path.name
    output_json = out_dir / "effective-topology.json"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=output_json,
        diagnostics_json=out_dir / "diagnostics.json",
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=True,
        fail_on_warning=False,
        require_new_model=False,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    exit_code = compiler.run()
    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    l1_rows = payload.get("instances", {}).get("l1_devices", [])
    by_source_id = {row.get("source_id"): row for row in l1_rows if isinstance(row, dict)}

    mikrotik = by_source_id.get("rtr-mikrotik-chateau")
    slate = by_source_id.get("rtr-slate")
    pdu = by_source_id.get("pdu-rack")
    assert isinstance(mikrotik, dict)
    assert isinstance(slate, dict)
    assert isinstance(pdu, dict)

    assert mikrotik.get("instance_data", {}).get("power", {}).get("source_ref") == "pdu-rack"
    assert mikrotik.get("instance_data", {}).get("power", {}).get("outlet_ref") == "outlet_01"
    assert slate.get("instance_data", {}).get("power", {}).get("source_ref") == "pdu-rack"
    assert slate.get("instance_data", {}).get("power", {}).get("outlet_ref") == "outlet_02"
    assert pdu.get("instance_data", {}).get("power", {}).get("source_ref") == "ups-main"
