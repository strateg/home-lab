"""ADR0094 AI sandbox helpers."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

_ENV_SECRET_PATTERNS = (
    re.compile(r".*SECRET.*", re.IGNORECASE),
    re.compile(r".*TOKEN.*", re.IGNORECASE),
    re.compile(r".*PASSWORD.*", re.IGNORECASE),
    re.compile(r".*CREDENTIAL.*", re.IGNORECASE),
    re.compile(r"^SOPS_.*", re.IGNORECASE),
    re.compile(r"^AGE_.*", re.IGNORECASE),
)


def resolve_ai_sandbox_root(*, repo_root: Path, project_id: str) -> Path:
    return (repo_root.resolve() / ".work" / "ai-sandbox" / project_id.strip()).resolve()


def create_ai_sandbox_session(*, repo_root: Path, project_id: str, request_id: str) -> Path:
    token = request_id.strip()
    if not token:
        raise ValueError("request_id must be non-empty")
    root = resolve_ai_sandbox_root(repo_root=repo_root, project_id=project_id)
    session = (root / token).resolve()
    if not str(session).startswith(str(root)):
        raise ValueError("sandbox session path escapes sandbox root")
    session.mkdir(parents=True, exist_ok=True)
    return session


def ensure_relative_sandbox_path(*, sandbox_session: Path, relative_path: str) -> Path:
    candidate = (sandbox_session.resolve() / relative_path.strip()).resolve()
    if not str(candidate).startswith(str(sandbox_session.resolve())):
        raise ValueError("sandbox path escapes session root")
    return candidate


def get_sandbox_usage(*, sandbox_session: Path) -> dict[str, int]:
    files = 0
    bytes_total = 0
    for path in sandbox_session.rglob("*"):
        if not path.is_file():
            continue
        files += 1
        bytes_total += int(path.stat().st_size)
    return {"files": files, "bytes": bytes_total}


def enforce_sandbox_resource_limits(
    *,
    sandbox_session: Path,
    max_files: int,
    max_bytes: int,
) -> dict[str, int]:
    if max_files < 1:
        raise ValueError("max_files must be >= 1")
    if max_bytes < 1:
        raise ValueError("max_bytes must be >= 1")
    usage = get_sandbox_usage(sandbox_session=sandbox_session)
    if usage["files"] > max_files:
        raise ValueError(f"sandbox file count exceeded: {usage['files']} > {max_files}")
    if usage["bytes"] > max_bytes:
        raise ValueError(f"sandbox size exceeded: {usage['bytes']} > {max_bytes}")
    return usage


def cleanup_ai_sandbox_sessions(
    *,
    repo_root: Path,
    project_id: str,
    retain_days: int,
    now_utc: datetime | None = None,
) -> list[Path]:
    if retain_days < 1:
        raise ValueError("retain_days must be >= 1")
    current = now_utc or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=retain_days)
    root = resolve_ai_sandbox_root(repo_root=repo_root, project_id=project_id)
    if not root.exists() or not root.is_dir():
        return []

    removed: list[Path] = []
    for session in sorted(root.iterdir(), key=lambda item: item.name):
        if not session.is_dir():
            continue
        mtime = datetime.fromtimestamp(session.stat().st_mtime, tz=timezone.utc)
        if mtime >= cutoff:
            continue
        for nested in sorted(session.rglob("*"), reverse=True):
            if nested.is_file() or nested.is_symlink():
                nested.unlink(missing_ok=True)
            elif nested.is_dir():
                nested.rmdir()
        session.rmdir()
        removed.append(session)
    return removed


def sanitize_environment(env: Mapping[str, str] | None = None) -> tuple[dict[str, str], list[str]]:
    source = dict(os.environ if env is None else env)
    sanitized: dict[str, str] = {}
    removed: list[str] = []
    for key, value in source.items():
        if any(pattern.fullmatch(key) for pattern in _ENV_SECRET_PATTERNS):
            removed.append(key)
            continue
        sanitized[str(key)] = str(value)
    removed.sort()
    return sanitized, removed
