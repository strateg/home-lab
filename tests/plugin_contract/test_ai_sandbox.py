#!/usr/bin/env python3
"""Contract checks for ADR0094 AI sandbox helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.ai_sandbox import (  # noqa: E402
    create_ai_sandbox_session,
    ensure_relative_sandbox_path,
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

