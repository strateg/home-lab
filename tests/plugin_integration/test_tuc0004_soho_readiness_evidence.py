#!/usr/bin/env python3
"""Integration checks for TUC-0004 SOHO readiness evidence and handover gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "topology-tools" / "compile-topology.py"
TOPOLOGY = REPO_ROOT / "topology" / "topology.yaml"
TUC_ROOT = REPO_ROOT / "acceptance-testing" / "TUC-0004-soho-readiness-evidence"
QUALITY_GATE = TUC_ROOT / "quality-gate.py"
ADR0091_D3_DOMAINS = {
    "greenfield-first-install",
    "brownfield-adoption",
    "router-replacement",
    "secret-rotation",
    "scheduled-update",
    "failed-update-rollback",
    "backup-and-restore",
    "operator-handover",
}
MANDATORY_HANDOVER_FILES = {
    "SYSTEM-SUMMARY.md",
    "NETWORK-SUMMARY.md",
    "ACCESS-RUNBOOK.md",
    "BACKUP-RUNBOOK.md",
    "RESTORE-RUNBOOK.md",
    "UPDATE-RUNBOOK.md",
    "INCIDENT-CHECKLIST.md",
    "ASSET-INVENTORY.csv",
    "CHANGELOG-SNAPSHOT.md",
}
MANDATORY_REPORT_FILES = {
    "health-report.json",
    "drift-report.json",
    "backup-status.json",
    "restore-readiness.json",
    "operator-readiness.json",
    "support-bundle-manifest.json",
}


def _run_compile(workdir: Path) -> tuple[int, str]:
    workdir = workdir.resolve()
    generated_root = workdir / "generated"
    output_json = workdir / "effective.json"
    diagnostics_json = workdir / "diagnostics.json"
    diagnostics_txt = workdir / "diagnostics.txt"
    cmd = [
        "python3",
        str(COMPILER),
        "--topology",
        str(TOPOLOGY.relative_to(REPO_ROOT).as_posix()),
        "--secrets-mode",
        "passthrough",
        "--artifacts-root",
        str(generated_root.relative_to(REPO_ROOT).as_posix()),
        "--output-json",
        str(output_json.relative_to(REPO_ROOT).as_posix()),
        "--diagnostics-json",
        str(diagnostics_json.relative_to(REPO_ROOT).as_posix()),
        "--diagnostics-txt",
        str(diagnostics_txt.relative_to(REPO_ROOT).as_posix()),
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    return completed.returncode, completed.stdout + "\n" + completed.stderr


def test_tuc0004_quality_gate_passes() -> None:
    result = subprocess.run([sys.executable, str(QUALITY_GATE)], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_tuc0004_compile_emits_mandatory_handover_and_reports(tmp_path: Path) -> None:
    workdir = REPO_ROOT / "build" / "test-tuc0004" / f"{tmp_path.name}-compile"
    workdir.mkdir(parents=True, exist_ok=True)

    code, output = _run_compile(workdir)
    assert code == 0, output

    handover_dir = workdir / "generated" / "home-lab" / "product" / "handover"
    reports_dir = workdir / "generated" / "home-lab" / "product" / "reports"
    assert handover_dir.exists()
    assert reports_dir.exists()

    handover_files = {path.name for path in handover_dir.iterdir() if path.is_file()}
    report_files = {path.name for path in reports_dir.iterdir() if path.is_file()}
    assert MANDATORY_HANDOVER_FILES.issubset(handover_files)
    assert MANDATORY_REPORT_FILES.issubset(report_files)


def test_tuc0004_operator_readiness_contains_all_adr0091_domains(tmp_path: Path) -> None:
    workdir = REPO_ROOT / "build" / "test-tuc0004" / f"{tmp_path.name}-readiness"
    workdir.mkdir(parents=True, exist_ok=True)

    code, output = _run_compile(workdir)
    assert code == 0, output

    operator_path = workdir / "generated" / "home-lab" / "product" / "reports" / "operator-readiness.json"
    manifest_path = workdir / "generated" / "home-lab" / "product" / "reports" / "support-bundle-manifest.json"
    operator_payload = json.loads(operator_path.read_text(encoding="utf-8"))
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    evidence = operator_payload.get("evidence", {})
    assert isinstance(evidence, dict)
    assert ADR0091_D3_DOMAINS.issubset(set(evidence.keys()))
    assert operator_payload.get("status") in {"green", "yellow", "red"}
    assert manifest_payload.get("completeness_state") in {"missing", "partial", "complete"}

