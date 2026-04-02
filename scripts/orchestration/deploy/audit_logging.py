"""
ADR 0083 scaffold: structured init-node logging.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_FILE_NAME = "init-node-audit.jsonl"


def resolve_deploy_log_dir(*, repo_root: Path, project_id: str) -> Path:
    return (repo_root / ".work" / "deploy-state" / project_id / "logs").resolve()


def resolve_init_node_log_path(*, repo_root: Path, project_id: str) -> Path:
    return (resolve_deploy_log_dir(repo_root=repo_root, project_id=project_id) / LOG_FILE_NAME).resolve()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class LogEvent:
    timestamp: str
    level: str
    event: str
    project_id: str
    node: str
    mechanism: str
    status: str
    message: str
    error_code: str
    details: dict[str, Any]


class InitNodeLogger:
    def __init__(self, *, repo_root: Path, project_id: str, console: bool = True) -> None:
        self.repo_root = repo_root.resolve()
        self.project_id = project_id.strip() or "home-lab"
        self.console = console
        self.log_path = resolve_init_node_log_path(repo_root=self.repo_root, project_id=self.project_id)

    def info(
        self,
        *,
        event: str,
        message: str,
        node: str = "",
        mechanism: str = "",
        status: str = "",
        error_code: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        self._emit(
            LogEvent(
                timestamp=utc_now(),
                level="info",
                event=event,
                project_id=self.project_id,
                node=node,
                mechanism=mechanism,
                status=status,
                message=message,
                error_code=error_code,
                details=details or {},
            )
        )

    def warning(
        self,
        *,
        event: str,
        message: str,
        node: str = "",
        mechanism: str = "",
        status: str = "",
        error_code: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        self._emit(
            LogEvent(
                timestamp=utc_now(),
                level="warning",
                event=event,
                project_id=self.project_id,
                node=node,
                mechanism=mechanism,
                status=status,
                message=message,
                error_code=error_code,
                details=details or {},
            )
        )

    def error(
        self,
        *,
        event: str,
        message: str,
        node: str = "",
        mechanism: str = "",
        status: str = "",
        error_code: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        self._emit(
            LogEvent(
                timestamp=utc_now(),
                level="error",
                event=event,
                project_id=self.project_id,
                node=node,
                mechanism=mechanism,
                status=status,
                message=message,
                error_code=error_code,
                details=details or {},
            )
        )

    def _emit(self, event: LogEvent) -> None:
        payload = {
            "timestamp": event.timestamp,
            "level": event.level,
            "event": event.event,
            "project_id": event.project_id,
            "node": event.node,
            "mechanism": event.mechanism,
            "status": event.status,
            "message": event.message,
            "error_code": event.error_code,
            "details": event.details,
        }
        self._append_jsonl(payload)
        if self.console:
            node_suffix = f" node={event.node}" if event.node else ""
            status_suffix = f" status={event.status}" if event.status else ""
            code_suffix = f" code={event.error_code}" if event.error_code else ""
            print(
                f"[init-node][{event.level}] {event.event}{node_suffix}{status_suffix}{code_suffix}: {event.message}",
                file=sys.stderr,
            )

    def _append_jsonl(self, payload: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True) + "\n"
        self.log_path.open("a", encoding="utf-8").write(line)
