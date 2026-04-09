#!/usr/bin/env python3
"""Integration checks for acceptance quality-gate runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "acceptance" / "run_quality_gates.py"


def test_acceptance_quality_gate_runner_passes_for_current_tucs() -> None:
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--root", "acceptance-testing"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert result.returncode == 0, combined
    assert "TUC-0001-router-data-channel-mikrotik-glinet" in combined
    assert "TUC-0004-soho-readiness-evidence" in combined

