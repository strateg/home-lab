#!/usr/bin/env python3
"""ADR0090 product:doctor status resolver from machine-readable evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def resolve_product_doctor_status(*, repo_root: Path, project_id: str) -> dict[str, Any]:
    operator_path = repo_root / "generated" / project_id / "product" / "reports" / "operator-readiness.json"
    profile_state_path = repo_root / "build" / "diagnostics" / "product-profile-state.json"

    operator_payload = _read_json(operator_path)
    if isinstance(operator_payload, dict):
        raw_status = str(operator_payload.get("status", "")).strip().lower()
        if raw_status in {"green", "yellow", "red"}:
            return {
                "schema_version": "1.0",
                "generated_at": _now(),
                "project_id": project_id,
                "status": raw_status,
                "source": "operator-readiness",
                "source_path": str(operator_path),
                "details": {
                    "evidence": operator_payload.get("evidence", {}),
                    "diagnostics": operator_payload.get("diagnostics", []),
                },
            }

    profile_payload = _read_json(profile_state_path)
    if isinstance(profile_payload, dict):
        raw_status = str(profile_payload.get("status", "")).strip().lower()
        if raw_status in {"green", "yellow", "red"}:
            return {
                "schema_version": "1.0",
                "generated_at": _now(),
                "project_id": project_id,
                "status": raw_status,
                "source": "product-profile-state",
                "source_path": str(profile_state_path),
                "details": {
                    "migration_state": profile_payload.get("migration_state", ""),
                    "diagnostics": profile_payload.get("diagnostics", []),
                },
            }

    return {
        "schema_version": "1.0",
        "generated_at": _now(),
        "project_id": project_id,
        "status": "red",
        "source": "none",
        "source_path": "",
        "details": {
            "reason": "no machine-readable readiness evidence found",
            "searched": [
                str(operator_path),
                str(profile_state_path),
            ],
        },
    }


def write_snapshot(*, repo_root: Path, snapshot: dict[str, Any]) -> Path:
    out_dir = repo_root / "build" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "product-doctor.json"
    output_path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve product doctor status from machine-readable evidence.")
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--project-id", default="home-lab")
    parser.add_argument("--fail-on-red", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    project_id = str(args.project_id).strip() or "home-lab"

    snapshot = resolve_product_doctor_status(repo_root=repo_root, project_id=project_id)
    output_path = write_snapshot(repo_root=repo_root, snapshot=snapshot)

    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "source": snapshot["source"],
                "snapshot_path": str(output_path),
            },
            ensure_ascii=True,
        )
    )

    if args.fail_on_red and snapshot["status"] == "red":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
