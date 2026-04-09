#!/usr/bin/env python3
"""Tests for ADR0091 handover package completeness checker."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "orchestration" / "product" / "handover_check.py"


def _module():
    spec = importlib.util.spec_from_file_location("product_handover_check", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _seed_complete_package(root: Path, project_id: str) -> None:
    handover_root = root / "generated" / project_id / "product" / "handover"
    reports_root = root / "generated" / project_id / "product" / "reports"
    handover_root.mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)

    handover_files = (
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
    report_files = (
        "health-report.json",
        "drift-report.json",
        "backup-status.json",
        "restore-readiness.json",
    )
    for name in handover_files:
        (handover_root / name).write_text("placeholder\n", encoding="utf-8")
    for name in report_files:
        (reports_root / name).write_text("{}\n", encoding="utf-8")

    (reports_root / "operator-readiness.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "project_id": project_id,
                "status": "green",
                "evidence": {},
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


def test_handover_check_passes_on_complete_package(tmp_path: Path) -> None:
    module = _module()
    _seed_complete_package(tmp_path, "home-lab")

    manifest = module._load_json(  # noqa: SLF001 - intentional helper coverage
        tmp_path / "generated" / "home-lab" / "product" / "reports" / "support-bundle-manifest.json"
    )
    assert isinstance(manifest, dict)
    assert manifest.get("completeness_state") == "complete"
    result = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--repo-root",
            str(tmp_path),
            "--project-id",
            "home-lab",
            "--require-complete",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


def test_handover_check_detects_missing_files(tmp_path: Path) -> None:
    module = _module()
    _seed_complete_package(tmp_path, "home-lab")
    missing = tmp_path / "generated" / "home-lab" / "product" / "handover" / "SYSTEM-SUMMARY.md"
    missing.unlink()

    handover_root = tmp_path / "generated" / "home-lab" / "product" / "handover"
    assert not (handover_root / "SYSTEM-SUMMARY.md").exists()

    # sanity: helper still loads manifest; task should fail via missing file list in runtime execution
    manifest = module._load_json(  # noqa: SLF001 - intentional helper coverage
        tmp_path / "generated" / "home-lab" / "product" / "reports" / "support-bundle-manifest.json"
    )
    assert isinstance(manifest, dict)
    result = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--repo-root",
            str(tmp_path),
            "--project-id",
            "home-lab",
            "--require-complete",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_handover_check_blocks_critical_readiness_diagnostics(tmp_path: Path) -> None:
    _seed_complete_package(tmp_path, "home-lab")
    operator_path = tmp_path / "generated" / "home-lab" / "product" / "reports" / "operator-readiness.json"
    operator_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "project_id": "home-lab",
                "status": "red",
                "evidence": {"backup-and-restore": "missing"},
                "diagnostics": [
                    {
                        "code": "E7944",
                        "severity": "error",
                        "message": "restore readiness evidence missing",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--repo-root",
            str(tmp_path),
            "--project-id",
            "home-lab",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 4

    bypass = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--repo-root",
            str(tmp_path),
            "--project-id",
            "home-lab",
            "--allow-critical-readiness",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bypass.returncode == 0
