#!/usr/bin/env python3
"""Regression checks for plugin-first compiler cutover behavior (ADR 0069)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "topology" / "topology.yaml"


def test_plugin_first_compile_succeeds(compiled_diagnostics: dict[str, Any]) -> None:
    """Plugin-first compile with plugins enabled should succeed.

    H1.2: Uses session-scoped compile fixture instead of independent subprocess.
    """
    diagnostics = compiled_diagnostics.get("diagnostics", [])
    assert any(d.get("code") == "I4001" for d in diagnostics), "Missing I4001 diagnostic"
    assert any(d.get("code") == "I6901" for d in diagnostics), "Missing I6901 diagnostic"


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
