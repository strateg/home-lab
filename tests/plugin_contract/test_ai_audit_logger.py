#!/usr/bin/env python3
"""Contract checks for ADR0094 AI audit logger."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.ai_audit import (  # noqa: E402
    AiAuditLogger,
    EVENT_TYPES,
    cleanup_ai_audit_logs,
    resolve_ai_audit_log_path,
    verify_ai_audit_log_integrity,
)


def test_resolve_ai_audit_log_path_points_to_ai_audit_tree(tmp_path: Path) -> None:
    path = resolve_ai_audit_log_path(repo_root=tmp_path, project_id="home-lab", date_utc="2026-04-07")
    expected = tmp_path / ".work" / "ai-audit" / "home-lab" / "2026-04-07" / "ai-advisory-audit.jsonl"
    assert path == expected.resolve()


def test_ai_audit_logger_writes_jsonl_for_all_defined_events(tmp_path: Path) -> None:
    logger = AiAuditLogger(repo_root=tmp_path, project_id="home-lab", request_id="req-1", date_utc="2026-04-07")
    for event_type in sorted(EVENT_TYPES):
        logger.log_event(
            event_type=event_type,
            payload={"ok": True},
            input_hash="sha256-" + ("a" * 64),
        )

    lines = logger.log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(EVENT_TYPES)
    parsed = [json.loads(line) for line in lines]
    events = [row["event_type"] for row in parsed]
    assert sorted(events) == sorted(EVENT_TYPES)
    assert all(row.get("input_hash", "").startswith("sha256-") for row in parsed)


def test_ai_audit_logger_integrity_verification_detects_tampering(tmp_path: Path) -> None:
    logger = AiAuditLogger(repo_root=tmp_path, project_id="home-lab", request_id="req-2", date_utc="2026-04-07")
    logger.log_event(event_type="ai_request_sent", payload={"step": 1})
    logger.log_event(event_type="ai_response_received", payload={"step": 2})
    ok, reason = verify_ai_audit_log_integrity(logger.log_path)
    assert ok is True
    assert reason == ""

    rows = [json.loads(line) for line in logger.log_path.read_text(encoding="utf-8").splitlines()]
    rows[1]["payload"] = {"step": 999}
    logger.log_path.write_text(
        "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    ok2, reason2 = verify_ai_audit_log_integrity(logger.log_path)
    assert ok2 is False
    assert "event hash mismatch" in reason2


def test_cleanup_ai_audit_logs_removes_only_expired_days(tmp_path: Path) -> None:
    project_id = "home-lab"
    old_day = tmp_path / ".work" / "ai-audit" / project_id / "2026-03-01"
    keep_day = tmp_path / ".work" / "ai-audit" / project_id / "2026-04-06"
    old_day.mkdir(parents=True, exist_ok=True)
    keep_day.mkdir(parents=True, exist_ok=True)
    (old_day / "ai-advisory-audit.jsonl").write_text("{}", encoding="utf-8")
    (keep_day / "ai-advisory-audit.jsonl").write_text("{}", encoding="utf-8")

    removed = cleanup_ai_audit_logs(
        repo_root=tmp_path,
        project_id=project_id,
        retain_days=3,
        now_utc=date(2026, 4, 7),
    )

    assert [path.name for path in removed] == ["2026-03-01"]
    assert old_day.exists() is False
    assert keep_day.exists() is True
