#!/usr/bin/env python3
"""Validate ADR0091 product handover package completeness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_REQUIRED_HANDOVER = (
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

_REQUIRED_REPORTS = (
    "health-report.json",
    "drift-report.json",
    "backup-status.json",
    "restore-readiness.json",
    "operator-readiness.json",
    "support-bundle-manifest.json",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _has_critical_soho_diagnostic(operator_readiness: dict | None) -> bool:
    if not isinstance(operator_readiness, dict):
        return False
    diagnostics = operator_readiness.get("diagnostics")
    if not isinstance(diagnostics, list):
        return False
    for row in diagnostics:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code", "")).strip()
        severity = str(row.get("severity", "")).strip().lower()
        if severity == "error" and code.startswith("E794"):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate product handover/report package completeness.")
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--project-id", default="home-lab")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--allow-critical-readiness", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    project_id = str(args.project_id).strip() or "home-lab"

    handover_root = repo_root / "generated" / project_id / "product" / "handover"
    reports_root = repo_root / "generated" / project_id / "product" / "reports"

    missing: list[str] = []
    for name in _REQUIRED_HANDOVER:
        if not (handover_root / name).exists():
            missing.append(f"handover/{name}")
    for name in _REQUIRED_REPORTS:
        if not (reports_root / name).exists():
            missing.append(f"reports/{name}")

    manifest_path = reports_root / "support-bundle-manifest.json"
    manifest = _load_json(manifest_path)
    operator_readiness_path = reports_root / "operator-readiness.json"
    operator_readiness = _load_json(operator_readiness_path)
    completeness = "unknown"
    if isinstance(manifest, dict):
        raw = manifest.get("completeness_state")
        if isinstance(raw, str):
            completeness = raw

    payload = {
        "project_id": project_id,
        "handover_root": str(handover_root),
        "reports_root": str(reports_root),
        "missing": missing,
        "completeness_state": completeness,
        "critical_readiness_error": _has_critical_soho_diagnostic(operator_readiness),
    }
    print(json.dumps(payload, ensure_ascii=True))

    if missing:
        return 2
    if args.require_complete and completeness != "complete":
        return 3
    if not args.allow_critical_readiness and payload["critical_readiness_error"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
