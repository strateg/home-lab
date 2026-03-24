#!/usr/bin/env python3
"""Integration test for strict runtime entrypoint audit utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "topology-tools" / "audit-strict-runtime-entrypoints.py"


def test_strict_runtime_entrypoint_audit_passes() -> None:
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(REPO_ROOT),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert "Strict runtime audit: OK" in run.stdout
