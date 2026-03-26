#!/usr/bin/env python3
"""Checks that strict ADR0080 data-bus migration has no W800x leftovers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_contract_warning_free", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_with_contract_warnings(mod, *, profile: str, output_root: Path) -> dict:
    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=output_root / "effective-topology.json",
        diagnostics_json=output_root / "diagnostics.json",
        diagnostics_txt=output_root / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        runtime_profile=profile,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
        plugin_contract_warnings=True,
        stages=[mod.Stage.DISCOVER, mod.Stage.COMPILE, mod.Stage.VALIDATE, mod.Stage.GENERATE],
    )
    compiler._verify_framework_lock = lambda **kwargs: True  # type: ignore[method-assign]
    compiler.run()
    return json.loads((output_root / "diagnostics.json").read_text(encoding="utf-8"))


def test_contract_warning_free_production_and_modeled(tmp_path: Path):
    mod = _load_compiler_module()
    root = mod.REPO_ROOT / "build" / "test-contract-warning-free" / tmp_path.name
    for profile in ("production", "modeled"):
        payload = _run_with_contract_warnings(mod, profile=profile, output_root=root / profile)
        warning_codes = {
            str(item.get("code"))
            for item in payload.get("diagnostics", [])
            if isinstance(item, dict) and str(item.get("severity")) == "warning"
        }
        assert not any(code.startswith("W800") for code in warning_codes)
