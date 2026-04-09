#!/usr/bin/env python3
"""Integration checks for cutover Go/No-Go validator utility."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "topology-tools" / "utils" / "validate-cutover-go-no-go.py"


def test_validate_cutover_go_no_go_returns_go_for_green_payload(tmp_path: Path) -> None:
    split_summary = tmp_path / "split-rehearsal.json"
    split_summary.write_text(
        json.dumps(
            {
                "soho_contract_checks": {"ok": True, "critical_e794x": []},
                "operator_readiness_parity_check": {"ok": True},
            }
        ),
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "checks": [
                    {"name": "verify_lock", "return_code": 0},
                    {
                        "name": "split_rehearsal",
                        "return_code": 0,
                        "command": ["python", "run-split-rehearsal.py", "--summary-path", str(split_summary)],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT), "--summary-path", str(summary)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    payload = json.loads(run.stdout.strip())
    assert payload["decision"] == "GO"


def test_validate_cutover_go_no_go_returns_no_go_for_critical_e794x(tmp_path: Path) -> None:
    split_summary = tmp_path / "split-rehearsal.json"
    split_summary.write_text(
        json.dumps(
            {
                "soho_contract_checks": {"ok": False, "critical_e794x": ["E7944"]},
                "operator_readiness_parity_check": {"ok": True},
            }
        ),
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "name": "split_rehearsal",
                        "return_code": 0,
                        "command": ["python", "run-split-rehearsal.py", "--summary-path", str(split_summary)],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT), "--summary-path", str(summary)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 1, run.stdout + "\n" + run.stderr
    payload = json.loads(run.stdout.strip())
    assert payload["decision"] == "NO-GO"
