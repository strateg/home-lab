#!/usr/bin/env python3
"""Output stream checks for compiler user-facing and AI logging paths."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_output_streams", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _compiler(mod, tmp_path: Path):
    out_dir = tmp_path / "compiler-output-streams"
    return mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=out_dir / "effective-topology.json",
        diagnostics_json=out_dir / "diagnostics.json",
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )


def test_ai_advisory_recommendations_log_to_stderr(tmp_path: Path, capsys) -> None:
    mod = _load_compiler_module()
    compiler = _compiler(mod, tmp_path)

    compiler._print_advisory_recommendations(
        {
            "recommendations": [
                {
                    "path": "generated/home-lab/docs/overview.md",
                    "action": "suggest",
                    "rationale": "Improve readability",
                }
            ],
            "confidence_scores": {"generated/home-lab/docs/overview.md": 0.5},
        }
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[ai-advisory] Recommendations:" in captured.err
    assert "[ai-advisory] 1. suggest generated/home-lab/docs/overview.md (confidence=0.50)" in captured.err
    assert "[ai-advisory]    rationale: Improve readability" in captured.err


def test_compile_summary_stays_on_stdout(tmp_path: Path, capsys) -> None:
    mod = _load_compiler_module()
    compiler = _compiler(mod, tmp_path)

    compiler._print_summary(total=3, errors=0, warnings=1, infos=2, emit_effective=True)

    captured = capsys.readouterr()
    assert "Compile summary: total=3 errors=0 warnings=1 infos=2" in captured.out
    assert f"Diagnostics JSON: {compiler.diagnostics_json}" in captured.out
    assert f"Diagnostics TXT:  {compiler.diagnostics_txt}" in captured.out
    assert f"Effective JSON:   {compiler.output_json}" in captured.out
    assert captured.err == ""
