#!/usr/bin/env python3
"""Parity checks for sequential vs parallel execution across runtime profiles."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_parallel_parity", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _normalize_diag_signature(payload: dict) -> list[tuple[str, str, str, str | None]]:
    signatures: list[tuple[str, str, str, str | None]] = []
    for diag in payload.get("diagnostics", []):
        if not isinstance(diag, dict):
            continue
        signatures.append(
            (
                str(diag.get("code", "")),
                str(diag.get("severity", "")),
                str(diag.get("stage", "")),
                str(diag.get("plugin_id")) if "plugin_id" in diag else None,
            )
        )
    signatures.sort()
    return signatures


def _normalize_trace(path: Path) -> list[tuple[str, str, str, str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    normalized: list[tuple[str, str, str, str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        normalized.append(
            (
                str(item.get("event", "")),
                str(item.get("stage", "")),
                str(item.get("phase", "")),
                str(item.get("plugin_id", "")),
                str(item.get("status", "")),
            )
        )
    return normalized


def _trace_signature(
    trace: list[tuple[str, str, str, str, str]],
) -> tuple[
    list[tuple[str, str, str]],
    list[tuple[tuple[str, str, str], int]],
    list[tuple[tuple[str, str, str, str], int]],
]:
    lifecycle = [
        (event, stage, phase)
        for event, stage, phase, _plugin_id, _status in trace
        if event in {"stage_start", "phase_start", "stage_end"}
    ]
    plugin_starts = Counter(
        (stage, phase, plugin_id) for event, stage, phase, plugin_id, _status in trace if event == "plugin_start"
    )
    plugin_results = Counter(
        (stage, phase, plugin_id, status)
        for event, stage, phase, plugin_id, status in trace
        if event == "plugin_result"
    )
    return lifecycle, sorted(plugin_starts.items()), sorted(plugin_results.items())


def _normalize_effective_payload(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return payload

    def _sanitize(node):
        if isinstance(node, dict):
            sanitized = {}
            for key, value in node.items():
                if key in {"generated_at", "compiled_at", "assembled_at", "built_at"}:
                    continue
                sanitized[key] = _sanitize(value)
            return sanitized
        if isinstance(node, list):
            return [_sanitize(item) for item in node]
        return node

    return _sanitize(payload)


def _run_profile(
    mod, *, profile: str, parallel: bool, root: Path
) -> tuple[int, dict, list[tuple[str, str, str, str, str]], dict[str, list[str]], dict | None]:
    mode = "parallel" if parallel else "sequential"
    out_dir = root / profile / mode
    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=out_dir / "effective-topology.json",
        diagnostics_json=out_dir / "diagnostics.json",
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        runtime_profile=profile,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
        parallel_plugins=parallel,
        trace_execution=True,
        stages=[mod.Stage.DISCOVER, mod.Stage.COMPILE, mod.Stage.VALIDATE, mod.Stage.GENERATE],
    )
    compiler._verify_framework_lock = lambda **kwargs: True  # type: ignore[method-assign]
    exit_code = compiler.run()
    diag_payload = json.loads((out_dir / "diagnostics.json").read_text(encoding="utf-8"))
    trace_payload = _normalize_trace(out_dir / "plugin-execution-trace.json")
    published_keys = json.loads((out_dir / "plugin-published-keys.json").read_text(encoding="utf-8"))
    effective_payload = _normalize_effective_payload(out_dir / "effective-topology.json")
    return exit_code, diag_payload, trace_payload, published_keys, effective_payload


def _assert_profile_parity(profile: str, tmp_path: Path) -> None:
    mod = _load_compiler_module()
    run_root = mod.REPO_ROOT / "build" / "test-parallel-profile-parity" / tmp_path.name
    seq_code, seq_diag, seq_trace, seq_keys, seq_effective = _run_profile(
        mod,
        profile=profile,
        parallel=False,
        root=run_root,
    )
    par_code, par_diag, par_trace, par_keys, par_effective = _run_profile(
        mod,
        profile=profile,
        parallel=True,
        root=run_root,
    )

    assert seq_code == par_code
    assert seq_diag["summary"] == par_diag["summary"]
    assert _normalize_diag_signature(seq_diag) == _normalize_diag_signature(par_diag)
    assert _trace_signature(seq_trace) == _trace_signature(par_trace)
    assert seq_keys == par_keys
    assert seq_effective == par_effective


def test_parallel_profile_parity_production(tmp_path: Path):
    _assert_profile_parity("production", tmp_path)


def test_parallel_profile_parity_modeled(tmp_path: Path):
    _assert_profile_parity("modeled", tmp_path)
