#!/usr/bin/env python3
"""Contract checks for ADR0069 compiled model metadata."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _detect_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "topology-tools").is_dir() or (candidate / "v5" / "topology-tools").is_dir():
            return candidate
    return current.parents[3]


def _tools_root(repo_root: Path) -> Path:
    extracted = repo_root / "topology-tools"
    if extracted.is_dir():
        return extracted
    return repo_root / "v5" / "topology-tools"


def _load_compiler_module():
    repo_root = _detect_repo_root()
    module_path = _tools_root(repo_root) / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_module_contract", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _compiler(mod):
    test_output_dir = mod.REPO_ROOT / "v5-build" / "test-compiled-contract"
    return mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=test_output_dir / "effective-topology.json",
        diagnostics_json=test_output_dir / "diagnostics.json",
        diagnostics_txt=test_output_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        enable_plugins=True,
    )


def test_compiled_model_contract_accepts_supported_payload():
    mod = _load_compiler_module()
    compiler = _compiler(mod)

    payload = {
        "compiled_model_version": "1.0",
        "compiled_at": "2026-03-11T00:00:00+00:00",
        "compiler_pipeline_version": "adr0069-ws2",
        "source_manifest_digest": "abc",
    }
    assert compiler._validate_compiled_model_contract(payload) is True
    assert compiler._diagnostics == []


def test_compiled_model_contract_rejects_incompatible_or_missing_metadata():
    mod = _load_compiler_module()
    compiler = _compiler(mod)

    payload = {
        "compiled_model_version": "2.0",
        "compiled_at": "",
        "compiler_pipeline_version": "adr0069-ws2",
    }
    assert compiler._validate_compiled_model_contract(payload) is False
    assert any(d.code == "E6903" for d in compiler._diagnostics)
