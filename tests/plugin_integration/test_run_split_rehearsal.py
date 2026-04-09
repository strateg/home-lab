#!/usr/bin/env python3
"""Integration checks for split rehearsal utility."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "topology-tools" / "utils" / "run-split-rehearsal.py"


def test_run_split_rehearsal_dry_run_emits_summary(tmp_path: Path) -> None:
    summary_path = tmp_path / "split-rehearsal.json"
    workspace_root = tmp_path / "workspace"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(REPO_ROOT),
            "--workspace-root",
            str(workspace_root),
            "--summary-path",
            str(summary_path),
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert summary_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    steps = payload.get("steps", [])
    assert isinstance(steps, list)
    assert len(steps) == 5
    assert all(isinstance(item, dict) and int(item.get("return_code", 1)) == 0 for item in steps)
