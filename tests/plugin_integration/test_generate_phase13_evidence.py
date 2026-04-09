#!/usr/bin/env python3
"""Integration checks for ADR0076 Phase 13 evidence generator utility."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "topology-tools" / "utils" / "generate-phase13-evidence.py"


def test_generate_phase13_evidence_dry_run_writes_expected_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "phase13"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(output_dir),
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr

    expected = {
        "verify-lock.txt",
        "compile.txt",
        "compatibility.txt",
        "audit-entrypoints.txt",
        "cutover-readiness.txt",
        "summary.json",
    }
    actual = {path.name for path in output_dir.glob("*") if path.is_file()}
    assert expected.issubset(actual)

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    checks = summary.get("checks", [])
    assert isinstance(checks, list)
    assert len(checks) == 5
    assert all(isinstance(item, dict) and int(item.get("return_code", 1)) == 0 for item in checks)

