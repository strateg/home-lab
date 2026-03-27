#!/usr/bin/env python3
"""Tests for workspace layout validation script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validation" / "validate_workspace_layout.py"


def test_workspace_layout_validator_passes_without_legacy_roots(tmp_path: Path) -> None:
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert "Workspace layout: OK" in run.stdout


def test_workspace_layout_validator_fails_when_legacy_root_present(tmp_path: Path) -> None:
    (tmp_path / "v5").mkdir(parents=True, exist_ok=True)
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 1
    assert "Workspace layout: FAIL" in run.stdout
