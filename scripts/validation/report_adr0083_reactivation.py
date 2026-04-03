#!/usr/bin/env python3
"""Report ADR0083 reactivation readiness snapshot."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_register_statuses(register_path: Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for line in register_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ["):
            continue
        columns = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(columns) != 6:
            continue
        link_col = columns[0]
        if not link_col.startswith("[") or "](" not in link_col:
            continue
        number = link_col[1:5]
        if not number.isdigit():
            continue
        status = columns[2].strip()
        statuses[number] = status
    return statuses


def _count_yaml_files(root: Path, *, prefix: str) -> int:
    if not root.exists() or not root.is_dir():
        return 0
    return sum(1 for path in root.glob("*.yaml") if path.name.startswith(prefix))


def _trigger_snapshot(repo_root: Path, project_id: str) -> dict[str, Any]:
    alerts_threshold = 50
    services_threshold = 30
    instances_root = repo_root / "projects" / project_id / "topology" / "instances"
    alerts_root = instances_root / "L6-observability" / "observability"
    services_root = instances_root / "L5-application" / "services"
    alerts_count = _count_yaml_files(alerts_root, prefix="alert-")
    services_count = _count_yaml_files(services_root, prefix="svc-")
    alerts_triggered = alerts_count > alerts_threshold
    services_triggered = services_count > services_threshold
    return {
        "alerts_threshold": alerts_threshold,
        "services_threshold": services_threshold,
        "alerts_count": alerts_count,
        "services_count": services_count,
        "alerts_triggered": alerts_triggered,
        "services_triggered": services_triggered,
        "gate": "triggered" if alerts_triggered or services_triggered else "ok",
    }


def _is_wsl() -> bool:
    release = platform.release().lower()
    version = platform.version().lower()
    return "microsoft" in release or "microsoft" in version or "wsl" in release


def _has_paramiko() -> bool:
    try:
        import paramiko  # noqa: F401

        return True
    except Exception:
        return False


def _build_report(*, repo_root: Path, project_id: str, require_paramiko: bool) -> dict[str, Any]:
    register_statuses = _parse_register_statuses(repo_root / "adr" / "REGISTER.md")
    status_0083 = register_statuses.get("0083", "")
    status_0084 = register_statuses.get("0084", "")
    status_0085 = register_statuses.get("0085", "")
    adr_status_ok = (
        status_0083.lower().startswith("proposed")
        and status_0084.lower().startswith("accepted")
        and status_0085.lower().startswith("accepted")
    )

    required_files = [
        "scripts/orchestration/deploy/init-node.py",
        "schemas/initialization-contract.schema.json",
        "adr/0083-analysis/CUTOVER-CHECKLIST.md",
        "adr/0083-analysis/REACTIVATION-PACK.md",
    ]
    missing_files = [item for item in required_files if not (repo_root / item).exists()]
    scaffold_ok = not missing_files

    trigger = _trigger_snapshot(repo_root, project_id)
    trigger_ok = trigger["gate"] == "ok"

    platform_name = platform.system()
    is_wsl = _is_wsl()
    paramiko_installed = _has_paramiko()

    blockers: list[str] = []
    if not adr_status_ok:
        blockers.append("ADR status baseline mismatch (expected: 0083=Proposed, 0084=Accepted, 0085=Accepted).")
    if not scaffold_ok:
        blockers.append(f"Missing scaffold files: {', '.join(missing_files)}")
    if not trigger_ok:
        blockers.append("ADR0047 trigger is active (alerts/services threshold exceeded).")
    if require_paramiko and not paramiko_installed:
        blockers.append("Paramiko is required by this readiness profile but is not installed in current interpreter.")

    ready = len(blockers) == 0
    return {
        "project_id": project_id,
        "adr_status": {
            "0083": status_0083,
            "0084": status_0084,
            "0085": status_0085,
            "ok": adr_status_ok,
        },
        "scaffold": {"required_files": required_files, "missing_files": missing_files, "ok": scaffold_ok},
        "environment": {
            "platform": platform_name,
            "is_wsl": is_wsl,
            "paramiko_installed": paramiko_installed,
            "require_paramiko": require_paramiko,
        },
        "trigger_snapshot": trigger,
        "ready_for_reactivation": ready,
        "blocking_issues": blockers,
        "recommended_commands": [
            "task validate:adr-consistency",
            "task validate:adr0047-trigger-gate",
            "task ci:python-checks-core",
            "task bundle:create INJECT_SECRETS=true",
            "task deploy:init-reactivation-smoke BUNDLE=<bundle_id>",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report ADR0083 reactivation readiness snapshot.")
    parser.add_argument("--project-id", default="home-lab", help="Project id under projects/<id>/...")
    parser.add_argument(
        "--require-paramiko",
        action="store_true",
        help="Treat missing paramiko as blocking issue (for password-based SSH bootstrap profiles).",
    )
    parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="Exit with code 1 when readiness is not satisfied.",
    )
    parser.add_argument("--output-json", default="", help="Optional path to write JSON report.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = _repo_root()
    report = _build_report(
        repo_root=repo_root,
        project_id=args.project_id,
        require_paramiko=bool(args.require_paramiko),
    )

    if args.output_json:
        output_path = Path(args.output_json)
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=True))
    if args.fail_on_not_ready and not report["ready_for_reactivation"]:
        print("ERROR: ADR0083 reactivation readiness is not satisfied.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
