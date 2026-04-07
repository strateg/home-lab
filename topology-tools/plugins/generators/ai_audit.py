"""ADR0094 AI audit logger utilities."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LOG_FILE_NAME = "ai-advisory-audit.jsonl"
EVENT_TYPES = {
    "ai_request_sent",
    "ai_response_received",
    "candidate_validation_result",
    "human_approval_decision",
    "candidate_promotion_result",
    "rollback_result",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _event_hash(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return f"sha256-{digest}"


def resolve_ai_audit_log_path(*, repo_root: Path, project_id: str, date_utc: str) -> Path:
    return (repo_root / ".work" / "ai-audit" / project_id / date_utc / LOG_FILE_NAME).resolve()


def cleanup_ai_audit_logs(
    *,
    repo_root: Path,
    project_id: str,
    retain_days: int,
    now_utc: date | None = None,
) -> list[Path]:
    if retain_days < 1:
        raise ValueError("retain_days must be >= 1")
    today = now_utc or datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=retain_days - 1)
    project_root = (repo_root.resolve() / ".work" / "ai-audit" / project_id.strip()).resolve()
    if not project_root.exists() or not project_root.is_dir():
        return []

    removed: list[Path] = []
    for child in sorted(project_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        try:
            day = datetime.strptime(child.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day < cutoff:
            for nested in sorted(child.rglob("*"), reverse=True):
                if nested.is_file() or nested.is_symlink():
                    nested.unlink(missing_ok=True)
                elif nested.is_dir():
                    nested.rmdir()
            child.rmdir()
            removed.append(child)
    return removed


class AiAuditLogger:
    def __init__(
        self,
        *,
        repo_root: Path,
        project_id: str,
        request_id: str,
        date_utc: str | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.project_id = project_id.strip() or "home-lab"
        self.request_id = request_id.strip()
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        self.date_utc = date_utc or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.log_path = resolve_ai_audit_log_path(
            repo_root=self.repo_root,
            project_id=self.project_id,
            date_utc=self.date_utc,
        )
        self._last_hash = self._read_last_hash()

    def _read_last_hash(self) -> str:
        if not self.log_path.exists():
            return ""
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return ""
        try:
            payload = json.loads(lines[-1])
        except Exception:
            return ""
        value = payload.get("event_hash")
        return value if isinstance(value, str) else ""

    def log_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        input_hash: str = "",
        output_hash: str = "",
    ) -> dict[str, Any]:
        token = event_type.strip()
        if token not in EVENT_TYPES:
            raise ValueError(f"unsupported event_type '{event_type}'")

        event_payload = {
            "schema_version": 1,
            "timestamp": _utc_now(),
            "project_id": self.project_id,
            "request_id": self.request_id,
            "event_type": token,
            "input_hash": input_hash.strip(),
            "output_hash": output_hash.strip(),
            "payload": payload or {},
            "prev_event_hash": self._last_hash,
        }
        event_payload["event_hash"] = _event_hash(event_payload)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event_payload, ensure_ascii=True) + "\n")
        self._last_hash = str(event_payload["event_hash"])
        return event_payload


def verify_ai_audit_log_integrity(log_path: Path) -> tuple[bool, str]:
    if not log_path.exists():
        return False, "log file does not exist"
    previous_hash = ""
    for index, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            payload = json.loads(line)
        except Exception as exc:
            return False, f"line {index}: invalid JSON ({exc})"
        event_type = payload.get("event_type")
        if not isinstance(event_type, str) or event_type not in EVENT_TYPES:
            return False, f"line {index}: unknown event_type"
        prev_hash = payload.get("prev_event_hash")
        if not isinstance(prev_hash, str) or prev_hash != previous_hash:
            return False, f"line {index}: hash chain mismatch"
        actual_hash = payload.get("event_hash")
        if not isinstance(actual_hash, str):
            return False, f"line {index}: missing event_hash"
        material = dict(payload)
        material.pop("event_hash", None)
        expected_hash = _event_hash(material)
        if actual_hash != expected_hash:
            return False, f"line {index}: event hash mismatch"
        previous_hash = actual_hash
    return True, ""
