#!/usr/bin/env python3
"""Extracted-mode product contract checks for ADR0076 WS1.2."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_SCRIPT = REPO_ROOT / "scripts" / "orchestration" / "product" / "doctor.py"
HANDOVER_SCRIPT = REPO_ROOT / "scripts" / "orchestration" / "product" / "handover_check.py"

_REQUIRED_HANDOVER_FILES = (
    "SYSTEM-SUMMARY.md",
    "NETWORK-SUMMARY.md",
    "ACCESS-RUNBOOK.md",
    "BACKUP-RUNBOOK.md",
    "RESTORE-RUNBOOK.md",
    "UPDATE-RUNBOOK.md",
    "INCIDENT-CHECKLIST.md",
    "ASSET-INVENTORY.csv",
    "CHANGELOG-SNAPSHOT.md",
)
_REQUIRED_REPORT_FILES = (
    "health-report.json",
    "drift-report.json",
    "backup-status.json",
    "restore-readiness.json",
)


def _seed_extracted_product_artifacts(root: Path, *, project_id: str = "home-lab") -> None:
    handover_root = root / "generated" / project_id / "product" / "handover"
    reports_root = root / "generated" / project_id / "product" / "reports"
    handover_root.mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)

    for name in _REQUIRED_HANDOVER_FILES:
        (handover_root / name).write_text("placeholder\n", encoding="utf-8")
    for name in _REQUIRED_REPORT_FILES:
        (reports_root / name).write_text("{}\n", encoding="utf-8")

    (reports_root / "operator-readiness.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "project_id": project_id,
                "status": "green",
                "evidence": {"operator-handover": "complete"},
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    (reports_root / "support-bundle-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "timestamp": "2026-04-09T00:00:00+00:00",
                "project_id": project_id,
                "artifacts": {"handover": {}, "reports": {}},
                "completeness_state": "complete",
            }
        ),
        encoding="utf-8",
    )


def test_extracted_mode_product_doctor_reads_machine_evidence(tmp_path: Path) -> None:
    extracted_project_root = tmp_path / "project-extracted"
    _seed_extracted_product_artifacts(extracted_project_root)

    run = subprocess.run(
        [
            sys.executable,
            str(DOCTOR_SCRIPT),
            "--repo-root",
            str(extracted_project_root),
            "--project-id",
            "home-lab",
            "--fail-on-red",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr

    snapshot_path = extracted_project_root / "build" / "diagnostics" / "product-doctor.json"
    assert snapshot_path.exists()
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["status"] == "green"
    assert payload["source"] == "operator-readiness"


def test_extracted_mode_product_handover_gate_enforces_completeness(tmp_path: Path) -> None:
    extracted_project_root = tmp_path / "project-extracted"
    _seed_extracted_product_artifacts(extracted_project_root)

    ok = subprocess.run(
        [
            sys.executable,
            str(HANDOVER_SCRIPT),
            "--repo-root",
            str(extracted_project_root),
            "--project-id",
            "home-lab",
            "--require-complete",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout + "\n" + ok.stderr

    (extracted_project_root / "generated" / "home-lab" / "product" / "handover" / "SYSTEM-SUMMARY.md").unlink()
    broken = subprocess.run(
        [
            sys.executable,
            str(HANDOVER_SCRIPT),
            "--repo-root",
            str(extracted_project_root),
            "--project-id",
            "home-lab",
            "--require-complete",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert broken.returncode != 0
