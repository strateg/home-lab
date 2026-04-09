#!/usr/bin/env python3
"""Integration checks for split rehearsal utility."""

from __future__ import annotations

import json
import subprocess
import sys
import importlib.util
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
    assert "soho_contract_checks" in payload
    assert "operator_readiness_parity_check" in payload
    steps = payload.get("steps", [])
    assert isinstance(steps, list)
    assert len(steps) == 5
    assert all(isinstance(item, dict) and int(item.get("return_code", 1)) == 0 for item in steps)


def test_evaluate_soho_artifacts_reports_complete_contract(tmp_path: Path) -> None:
    generated = tmp_path / "generated-artifacts" / "home-lab" / "product"
    handover = generated / "handover"
    reports = generated / "reports"
    handover.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    required_handover = (
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
    required_reports = (
        "health-report.json",
        "drift-report.json",
        "backup-status.json",
        "restore-readiness.json",
    )
    for name in required_handover:
        (handover / name).write_text("x\n", encoding="utf-8")
    for name in required_reports:
        (reports / name).write_text("{}\n", encoding="utf-8")

    (reports / "operator-readiness.json").write_text(
        json.dumps(
            {
                "status": "green",
                "evidence": {
                    "greenfield-first-install": "complete",
                    "brownfield-adoption": "complete",
                    "router-replacement": "complete",
                    "secret-rotation": "complete",
                    "scheduled-update": "complete",
                    "failed-update-rollback": "complete",
                    "backup-and-restore": "complete",
                    "operator-handover": "complete",
                },
            }
        ),
        encoding="utf-8",
    )
    (reports / "support-bundle-manifest.json").write_text(
        json.dumps({"completeness_state": "complete"}),
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location("split_rehearsal", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]

    checks = module._evaluate_soho_artifacts(tmp_path / "generated-artifacts")  # noqa: SLF001
    assert checks["ok"] is True


def test_compare_operator_readiness_payloads_detects_status_mismatch() -> None:
    spec = importlib.util.spec_from_file_location("split_rehearsal", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]

    comparison = module._compare_operator_readiness_payloads(  # noqa: SLF001
        extracted_payload={"status": "yellow", "evidence": {"backup-and-restore": "partial"}},
        baseline_payload={"status": "green", "evidence": {"backup-and-restore": "complete"}},
    )
    assert comparison["ok"] is False
    assert comparison["extracted_status"] == "yellow"
    assert comparison["baseline_status"] == "green"
