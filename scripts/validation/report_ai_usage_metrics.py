#!/usr/bin/env python3
"""Report opt-in ADR0094 AI usage metrics from local audit logs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_audit_logs(root: Path, project_id: str) -> list[Path]:
    project_root = root / ".work" / "ai-audit" / project_id
    if not project_root.exists() or not project_root.is_dir():
        return []
    return sorted(project_root.rglob("ai-advisory-audit.jsonl"))


def _safe_load_json_lines(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _build_metrics(repo_root: Path, project_id: str) -> dict[str, Any]:
    logs = _iter_audit_logs(repo_root, project_id)
    event_counter: Counter[str] = Counter()
    request_ids: set[str] = set()
    per_day_requests: Counter[str] = Counter()

    for log in logs:
        rows = _safe_load_json_lines(log)
        day_token = log.parent.name
        day_seen: set[str] = set()
        for row in rows:
            event_type = row.get("event_type")
            if isinstance(event_type, str) and event_type.strip():
                event_counter[event_type.strip()] += 1
            request_id = row.get("request_id")
            if isinstance(request_id, str) and request_id.strip():
                token = request_id.strip()
                request_ids.add(token)
                day_seen.add(token)
        per_day_requests[day_token] += len(day_seen)

    return {
        "schema_version": 1,
        "project_id": project_id,
        "audit_log_files": len(logs),
        "unique_requests": len(request_ids),
        "event_counts": dict(sorted(event_counter.items())),
        "daily_request_counts": dict(sorted(per_day_requests.items())),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report ADR0094 AI usage metrics from audit logs.")
    parser.add_argument("--project-id", default="home-lab", help="Project id under .work/ai-audit/<project-id>/...")
    parser.add_argument("--output-json", default="", help="Optional path to write metrics JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = _repo_root()
    metrics = _build_metrics(repo_root, args.project_id)

    if args.output_json:
        output_path = Path(args.output_json)
        if not output_path.is_absolute():
            output_path = repo_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
