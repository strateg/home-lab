#!/usr/bin/env python3
"""Regression tests for plugin vs baseline compiler parity (ADR 0066)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPILER = REPO_ROOT / "v5" / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "v5" / "topology" / "topology.yaml"


def _run_compile(tmp_path: Path, *, enable_plugins: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    suffix = "plugins" if enable_plugins else "baseline"
    artifacts_dir = REPO_ROOT / "v5-build" / "test-artifacts" / tmp_path.name
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_json = artifacts_dir / f"effective-{suffix}.json"
    diagnostics_json = artifacts_dir / f"report-{suffix}.json"
    diagnostics_txt = artifacts_dir / f"report-{suffix}.txt"

    cmd = [
        sys.executable,
        str(COMPILER),
        "--topology",
        str(TOPOLOGY.relative_to(REPO_ROOT).as_posix()),
        "--output-json",
        str(output_json.relative_to(REPO_ROOT).as_posix()),
        "--diagnostics-json",
        str(diagnostics_json.relative_to(REPO_ROOT).as_posix()),
        "--diagnostics-txt",
        str(diagnostics_txt.relative_to(REPO_ROOT).as_posix()),
        "--strict-model-lock",
    ]
    if enable_plugins:
        cmd.append("--enable-plugins")

    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"Compiler failed with exit={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )

    assert output_json.exists(), f"Missing output JSON: {output_json}"
    assert diagnostics_json.exists(), f"Missing diagnostics JSON: {diagnostics_json}"

    effective = json.loads(output_json.read_text(encoding="utf-8"))
    report = json.loads(diagnostics_json.read_text(encoding="utf-8"))
    return effective, report


def _without_runtime_timestamps(payload: dict[str, Any]) -> dict[str, Any]:
    copied = dict(payload)
    copied.pop("generated_at", None)
    copied.pop("compiled_at", None)
    return copied


def test_plugin_compile_parity(tmp_path: Path) -> None:
    """Plugin-enabled compile should preserve baseline output and error count."""
    baseline_output, baseline_report = _run_compile(tmp_path, enable_plugins=False)
    plugin_output, plugin_report = _run_compile(tmp_path, enable_plugins=True)

    assert plugin_report["summary"]["errors"] == baseline_report["summary"]["errors"]
    assert _without_runtime_timestamps(plugin_output) == _without_runtime_timestamps(baseline_output)

    # Ensure plugin execution was actually enabled.
    plugin_diagnostics = plugin_report.get("diagnostics", [])
    assert any(d.get("code") == "I4001" for d in plugin_diagnostics)
