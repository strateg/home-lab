#!/usr/bin/env python3
"""Report ADR0047 trigger metrics for observability modularization escalation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _count_yaml_files(root: Path, *, prefix: str) -> int:
    if not root.exists() or not root.is_dir():
        return 0
    return sum(1 for path in root.glob("*.yaml") if path.name.startswith(prefix))


def _resolve_group_root(instances_root: Path, *, group: str, legacy_bucket: str) -> Path:
    canonical = instances_root / group
    if canonical.exists():
        return canonical
    legacy = instances_root / legacy_bucket / group
    return legacy


def _build_report(
    repo_root: Path,
    *,
    alert_threshold: int,
    service_threshold: int,
    project_id: str,
) -> dict[str, Any]:
    instances_root = repo_root / "projects" / project_id / "topology" / "instances"
    alerts_root = _resolve_group_root(instances_root, group="observability", legacy_bucket="L6-observability")
    services_root = _resolve_group_root(instances_root, group="services", legacy_bucket="L5-application")

    alerts_count = _count_yaml_files(alerts_root, prefix="alert-")
    services_count = _count_yaml_files(services_root, prefix="svc-")
    alerts_triggered = alerts_count > alert_threshold
    services_triggered = services_count > service_threshold
    gate = "triggered" if alerts_triggered or services_triggered else "ok"

    return {
        "project_id": project_id,
        "alerts_threshold": alert_threshold,
        "services_threshold": service_threshold,
        "alerts_count": alerts_count,
        "services_count": services_count,
        "alerts_triggered": alerts_triggered,
        "services_triggered": services_triggered,
        "gate": gate,
        "alerts_root": str(alerts_root.relative_to(repo_root).as_posix()),
        "services_root": str(services_root.relative_to(repo_root).as_posix()),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report ADR0047 trigger metrics.")
    parser.add_argument("--project-id", default="home-lab", help="Project id under projects/<id>/...")
    parser.add_argument(
        "--alerts-threshold",
        type=int,
        default=50,
        help="Trigger threshold for alerts count (default: 50).",
    )
    parser.add_argument(
        "--services-threshold",
        type=int,
        default=30,
        help="Trigger threshold for services count (default: 30).",
    )
    parser.add_argument(
        "--fail-on-trigger",
        action="store_true",
        help="Exit with code 1 when ADR0047 trigger condition is reached.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write JSON report.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = _repo_root()
    report = _build_report(
        repo_root,
        alert_threshold=args.alerts_threshold,
        service_threshold=args.services_threshold,
        project_id=args.project_id,
    )

    if args.output_json:
        output_path = Path(args.output_json)
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=True))
    if args.fail_on_trigger and report["gate"] == "triggered":
        print(
            "ERROR: ADR0047 trigger reached "
            f"(alerts={report['alerts_count']}>{report['alerts_threshold']} "
            f"or services={report['services_count']}>{report['services_threshold']})."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
