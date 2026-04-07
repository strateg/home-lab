"""ADR0094 AI sandbox helpers."""

from __future__ import annotations

import os
import re
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

