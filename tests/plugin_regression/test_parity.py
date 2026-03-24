#!/usr/bin/env python3
"""Regression checks for plugin-first compiler cutover behavior (ADR 0069)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "topology" / "topology.yaml"


def _run_compile(tmp_path: Path, *, pipeline_mode: str = "plugin-first") -> tuple[int, Path, Path]:
    suffix = "plugins"
    artifacts_dir = REPO_ROOT / "build" / "test-artifacts" / tmp_path.name
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
        "--pipeline-mode",
        pipeline_mode,
        "--strict-model-lock",
    ]
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode, output_json, diagnostics_json


def test_plugin_first_compile_succeeds(tmp_path: Path) -> None:
    """Plugin-first compile with plugins enabled should succeed."""
    exit_code, output_json, diagnostics_json = _run_compile(tmp_path)
    assert exit_code == 0
    assert output_json.exists(), f"Missing output JSON: {output_json}"
    assert diagnostics_json.exists(), f"Missing diagnostics JSON: {diagnostics_json}"

    report = json.loads(diagnostics_json.read_text(encoding="utf-8"))
    diagnostics = report.get("diagnostics", [])
    assert any(d.get("code") == "I4001" for d in diagnostics)
    assert any(d.get("code") == "I6901" for d in diagnostics)


def test_disable_plugins_flag_is_rejected(tmp_path: Path) -> None:
    """CLI no longer supports --disable-plugins after plugin-first cutover."""
    artifacts_dir = REPO_ROOT / "build" / "test-artifacts" / tmp_path.name
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_json = artifacts_dir / "effective-invalid-flag.json"
    diagnostics_json = artifacts_dir / "report-invalid-flag.json"
    diagnostics_txt = artifacts_dir / "report-invalid-flag.txt"

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
        "--disable-plugins",
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)

    assert completed.returncode != 0
    assert "unrecognized arguments: --disable-plugins" in completed.stderr
