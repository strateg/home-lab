#!/usr/bin/env python3
"""Contract checks for ADR0094 AI sandbox helpers."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.ai_sandbox import (  # noqa: E402
    cleanup_ai_sandbox_sessions,
    create_ai_sandbox_session,
    enforce_sandbox_resource_limits,
    ensure_relative_sandbox_path,
    get_sandbox_usage,
    resolve_ai_sandbox_root,
    sanitize_environment,
)


def test_create_ai_sandbox_session_creates_directory(tmp_path: Path) -> None:
    session = create_ai_sandbox_session(repo_root=tmp_path, project_id="home-lab", request_id="req-1")
    expected = tmp_path / ".work" / "ai-sandbox" / "home-lab" / "req-1"
    assert session == expected.resolve()
    assert session.is_dir()


def test_ensure_relative_sandbox_path_blocks_escape(tmp_path: Path) -> None:
    session = create_ai_sandbox_session(repo_root=tmp_path, project_id="home-lab", request_id="req-2")
    inside = ensure_relative_sandbox_path(sandbox_session=session, relative_path="candidate/plan.json")
    assert str(inside).startswith(str(session))
    with pytest.raises(ValueError):
        ensure_relative_sandbox_path(sandbox_session=session, relative_path="../escape.json")


def test_sanitize_environment_removes_secret_like_keys() -> None:
    sanitized, removed = sanitize_environment(
        {
            "PATH": "/usr/bin",
            "API_TOKEN": "token",
            "DB_PASSWORD": "pw",
            "SOPS_AGE_KEY_FILE": "/tmp/key.txt",
            "NORMAL_FLAG": "1",
        }
    )
    assert "PATH" in sanitized
    assert "NORMAL_FLAG" in sanitized
    assert "API_TOKEN" not in sanitized
    assert "DB_PASSWORD" not in sanitized
    assert "SOPS_AGE_KEY_FILE" not in sanitized
    assert removed == ["API_TOKEN", "DB_PASSWORD", "SOPS_AGE_KEY_FILE"]


def test_resolve_ai_sandbox_root_path(tmp_path: Path) -> None:
    root = resolve_ai_sandbox_root(repo_root=tmp_path, project_id="home-lab")
    assert root == (tmp_path / ".work" / "ai-sandbox" / "home-lab").resolve()


def test_enforce_sandbox_resource_limits_counts_files_and_bytes(tmp_path: Path) -> None:
    session = create_ai_sandbox_session(repo_root=tmp_path, project_id="home-lab", request_id="req-3")
    path = ensure_relative_sandbox_path(sandbox_session=session, relative_path="a.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("abcd", encoding="utf-8")

    usage = get_sandbox_usage(sandbox_session=session)
    assert usage == {"files": 1, "bytes": 4}
    enforced = enforce_sandbox_resource_limits(sandbox_session=session, max_files=2, max_bytes=8)
    assert enforced == usage
    with pytest.raises(ValueError):
        enforce_sandbox_resource_limits(sandbox_session=session, max_files=0, max_bytes=8)
    with pytest.raises(ValueError):
        enforce_sandbox_resource_limits(sandbox_session=session, max_files=2, max_bytes=3)


def test_cleanup_ai_sandbox_sessions_removes_expired_by_mtime(tmp_path: Path) -> None:
    old_session = create_ai_sandbox_session(repo_root=tmp_path, project_id="home-lab", request_id="req-old")
    new_session = create_ai_sandbox_session(repo_root=tmp_path, project_id="home-lab", request_id="req-new")
    old_ts = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc).timestamp()
    new_ts = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc).timestamp()
    os.utime(old_session, (old_ts, old_ts))
    os.utime(new_session, (new_ts, new_ts))

    removed = cleanup_ai_sandbox_sessions(
        repo_root=tmp_path,
        project_id="home-lab",
        retain_days=7,
        now_utc=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
    )

    assert [path.name for path in removed] == ["req-old"]
    assert old_session.exists() is False
    assert new_session.exists() is True
